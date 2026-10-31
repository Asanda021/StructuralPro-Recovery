"""P8 P2: Windows ctime-only drift versus real source tampering."""
from hashlib import sha256
from pathlib import Path
import pytest
from core.reports.custom_batch import _verify_source_files


def source_fixture(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.7\nSynthetic source\n%%EOF")
    digest = sha256(source.read_bytes()).hexdigest()
    return source, {"takeoffs": [{"domain": "drawing", "drawing_session_id": "S1"}],
                    "drawing_sessions": {"S1": {"drawing_source": str(source),
                                               "source_sha256": digest}}}


def test_real_untouched_source_passes(tmp_path):
    source, record = source_fixture(tmp_path)
    before = source.read_bytes()
    _verify_source_files(record, require_pricebook=False)
    assert source.read_bytes() == before


def test_windows_ctime_only_drift_does_not_trigger_false_source_error(tmp_path, monkeypatch):
    source, record = source_fixture(tmp_path)
    real = Path.stat
    class MetadataOnly:
        def __init__(self, s): self._s = s
        def __getattr__(self, key):
            return self._s.st_ctime_ns + 1000000000 if key == "st_ctime_ns" else getattr(self._s, key)
    def drifting(path, *args, **kwargs):
        data = real(path, *args, **kwargs)
        return MetadataOnly(data) if path == source else data
    monkeypatch.setattr(Path, "stat", drifting)
    _verify_source_files(record, require_pricebook=False)


@pytest.mark.parametrize("kind", ("longer", "same_size", "replace", "missing"))
def test_real_content_mutation_rejected(tmp_path, kind):
    source, record = source_fixture(tmp_path)
    original = source.read_bytes()
    if kind == "longer": source.write_bytes(original + b"X")
    elif kind == "same_size": source.write_bytes(original[:-4] + b"FAKE")
    elif kind == "replace":
        temp = tmp_path / "replacement"
        temp.write_bytes(b"X" + original[1:])
        temp.replace(source)
    else: source.unlink()
    with pytest.raises(ValueError, match="منبع"):
        _verify_source_files(record, require_pricebook=False)


@pytest.mark.parametrize("key", ("st_ino", "st_size", "st_mtime_ns"))
def test_file_identity_size_and_mtime_drift_still_rejected(tmp_path, monkeypatch, key):
    source, record = source_fixture(tmp_path)
    real = Path.stat
    class Modified:
        def __init__(self, s): self._s = s
        def __getattr__(self, name):
            return getattr(self._s, name) + 1 if name == key else getattr(self._s, name)
    def changed(path, *args, **kwargs):
        s = real(path, *args, **kwargs)
        return Modified(s) if path == source else s
    monkeypatch.setattr(Path, "stat", changed)
    with pytest.raises(ValueError, match="منبع"):
        _verify_source_files(record, require_pricebook=False)


def test_mid_verification_real_byte_rewrite_rejected(tmp_path, monkeypatch):
    source, record = source_fixture(tmp_path)
    real = Path.stat
    changed = [False]
    def mutate_before_path_stat(path, *args, **kwargs):
        if path == source and not changed[0]:
            changed[0] = True
            data = source.read_bytes()
            source.write_bytes(data[:-4] + b"FAKE")
        return real(path, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", mutate_before_path_stat)
    with pytest.raises(ValueError, match="منبع"):
        _verify_source_files(record, require_pricebook=False)
    assert changed[0]


def test_pricebook_integrity_is_still_checked(tmp_path):
    source, record = source_fixture(tmp_path)
    price = tmp_path / "rate.csv"
    price.write_bytes(b"code,price\nA,100\n")
    record["user_pricebook_review"] = {"path": str(price),
                                         "sha256": sha256(price.read_bytes()).hexdigest()}
    _verify_source_files(record, require_pricebook=True)
    price.write_bytes(price.read_bytes() + b"X")
    with pytest.raises(ValueError, match="منبع"):
        _verify_source_files(record, require_pricebook=True)
