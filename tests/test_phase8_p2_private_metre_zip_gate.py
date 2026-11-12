"""P8P2: local source ZIP path to production metre reconciler. No user files in CI."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile, ZipInfo

from openpyxl import Workbook
import pytest

from core.drawings.legacy_metre_cad_package import inspect_legacy_metre_package
from core.platform.application import StructuralProApp


def workbook(kind):
    out = BytesIO()
    wb = Workbook()
    sheet = wb.active
    if kind == "metre":
        sheet.title = "S_6_1 "
        sheet["A1"] = "فرم متره"
        sheet["A2"] = "فصل ششم - قالب بندي"
        sheet["B3"] = "شرح عمليات"
        sheet["L3"] = "قیمت"
        sheet["M3"] = "قیمت کل"
        sheet["B5"] = "کنار پی A"
        sheet["I5"] = 7.2
        sheet["L5"] = 42900
        sheet["M5"] = 1
    else:
        sheet.title = "خلاصه صورت وضعيت"
        sheet["B2"] = "شماره فصل فهرست بها"
        sheet["D8"] = 308880
        sheet["G8"] = 309000
    wb.save(out)
    wb.close()
    return out.getvalue()


def package(tmp_path, *, mutate=None):
    p = tmp_path / "user-original.zip"
    payload = {
        "metre-(www.icivil.ir)/riz metre.xlsx": workbook("metre"),
        "metre-(www.icivil.ir)/gozaresh nahaei.xlsx": workbook("summary"),
        "metre-(www.icivil.ir)/naghshe ha.dwg": b"AC1018" + b"example-source-not-a-valid-CAD-drawing",
    }
    if mutate:
        mutate(payload)
    with ZipFile(p, "w") as z:
        for name, content in payload.items():
            z.writestr(name, content)
        z.writestr("metre-(www.icivil.ir)/site.url", "not run")
    return p


def test_app_reads_legacy_dwg_and_metre_zip_but_never_certifies_missing_geometry(tmp_path):
    p = package(tmp_path)
    app = StructuralProApp(tmp_path / "app")
    try:
        app.create_project("audit remains read only", "p")
        digest = app.store.current_digest("p")
        result = app.audit_legacy_metre_zip(p)
        assert result["package"]["original_dwg_header"] == "AC1018"
        assert result["package"]["zip_sha256"] == sha256(p.read_bytes()).hexdigest()
        assert result["package"]["sources"]["naghshe ha.dwg"]["sha256"] == sha256(
            b"AC1018" + b"example-source-not-a-valid-CAD-drawing").hexdigest()
        assert result["priced_rows"] == 1 and result["metre_sheets"] == 1
        assert result["rows"][0]["key"] == "S_6_1!5"
        assert result["cad"]["status"].startswith("BLOCKED_")
        assert result["cad"]["verified_rows"] == 0
        assert result["boq_rows_committed"] == 0
        assert not result["prices_approved"]
        assert result["release"] == "NO_GO"
        assert app.store.current_digest("p") == digest
        assert app.open_project("p")["boq"] == []
    finally:
        app.store.close()


@pytest.mark.parametrize("path", ["../naghshe ha.dwg", "/tmp/naghshe ha.dwg", "C:/naghshe ha.dwg",
                                  "metre/../../naghshe ha.dwg"])
def test_zip_traversal_or_absolute_member_rejected(tmp_path, path):
    p = package(tmp_path)
    with ZipFile(p, "a") as z:
        z.writestr(path, b"AC1018" + b"x")
    with pytest.raises(ValueError, match="unsafe member"):
        inspect_legacy_metre_package(p)


def test_zip_duplicate_dwg_basename_rejected(tmp_path):
    p = package(tmp_path)
    with ZipFile(p, "a") as z:
        z.writestr("second/naghshe ha.dwg", b"AC1018" + b"duplicate")
    with pytest.raises(ValueError, match="Duplicate source"):
        inspect_legacy_metre_package(p)


def test_zip_missing_required_workbook_rejected(tmp_path):
    def remove(payload):
        payload.pop("metre-(www.icivil.ir)/gozaresh nahaei.xlsx")
    p = package(tmp_path, mutate=remove)
    with pytest.raises(ValueError, match="must contain"):
        inspect_legacy_metre_package(p)


def test_zip_unrecognized_dwg_header_rejected(tmp_path):
    def bad(payload):
        payload["metre-(www.icivil.ir)/naghshe ha.dwg"] = b"not-dwg" * 12
    with pytest.raises(ValueError, match="AutoCAD signature"):
        inspect_legacy_metre_package(package(tmp_path, mutate=bad))


def test_zip_path_swapped_between_digest_and_parser_does_not_change_audited_source(tmp_path, monkeypatch):
    """A replaced-and-restored ZIP must not contaminate an original-hash receipt.

    No private data: both archives and the temporary XLSX rows are synthetic.
    The parser must consume the first hashed byte snapshot, not reopen a path.
    """
    import os
    import core.drawings.legacy_metre_cad_package as zip_module
    from openpyxl import load_workbook

    source = package(tmp_path)
    original_bytes = source.read_bytes()
    original_sha = sha256(original_bytes).hexdigest()
    with ZipFile(BytesIO(original_bytes)) as archive:
        parts = {info.filename: archive.read(info) for info in archive.infolist()
                 if not info.is_dir()}

    alternate_book = load_workbook(BytesIO(parts["metre-(www.icivil.ir)/riz metre.xlsx"]))
    alternate_book.active["I5"] = 999
    out = BytesIO()
    alternate_book.save(out)
    alternate_book.close()
    parts["metre-(www.icivil.ir)/riz metre.xlsx"] = out.getvalue()
    alternate_path = tmp_path / "alternate.zip"
    with ZipFile(alternate_path, "w") as archive:
        for name, data in parts.items():
            archive.writestr(name, data)

    saved_path = tmp_path / "original-saved.zip"
    saved_path.write_bytes(original_bytes)
    original_read = Path.read_bytes
    observed = {"swapped": False, "restored": False, "opened_hashed_snapshot": False}

    def swap_after_first_hash_read(path):
        data = original_read(path)
        if path == source and not observed["swapped"]:
            os.replace(alternate_path, source)
            observed["swapped"] = True
        return data

    original_zipfile = ZipFile

    def restore_original_at_zip_open(file, *args, **kwargs):
        # This is the exact gap in the old implementation: its ZipFile(path)
        # opens the substituted file descriptor before the original returns.
        opened = original_zipfile(file, *args, **kwargs)
        if observed["swapped"] and not observed["restored"]:
            observed["opened_hashed_snapshot"] = isinstance(file, BytesIO)
            os.replace(saved_path, source)
            observed["restored"] = True
        return opened

    monkeypatch.setattr(Path, "read_bytes", swap_after_first_hash_read)
    monkeypatch.setattr(zip_module, "ZipFile", restore_original_at_zip_open)

    report = inspect_legacy_metre_package(source)
    assert observed == {
        "swapped": True, "restored": True, "opened_hashed_snapshot": True,
    }
    assert report["package"]["zip_sha256"] == original_sha
    assert report["rows"][0]["quantity"] == "7.2"
    assert report["cad"]["verified_rows"] == 0
    assert report["boq_rows_committed"] == 0
    assert report["release"] == "NO_GO"
