"""Phase 7 P2: source-backed 2D map in real Persian Office/PDF report bundle.

This is an additive, read-only adapter over the *existing* report exporters and
the persisted reviewed takeoff-to-BOQ crosswalk. It cannot grant an engineering
approval, infer absent geometry or change approved quantities/prices.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import tempfile

from core.reports.bundle import build_bundle_manifest
from core.reports.project_report import build_report
from core.reports.source_backed_2d_overlay import link_source_backed_2d_overlay_to_boq


def _svg_png(svg: str) -> bytes:
    """Render *our validated source overlay*, not an arbitrary input SVG."""
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("نقشه برداری SVG معتبر نیست")
    image = QImage(1200, 900, QImage.Format.Format_ARGB32_Premultiplied)
    if image.isNull():
        raise RuntimeError("تصویر نقشه قابل تولید نیست")
    image.fill(QColor("#ffffff"))
    painter = QPainter(image)
    try:
        renderer.render(painter)
    finally:
        painter.end()
    output = QBuffer()
    if not output.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(output, "PNG"):
        raise RuntimeError("صدور تصویر نقشه PNG ناموفق بود")
    png = bytes(output.data())
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise RuntimeError("خروجی PNG ناقص است")
    return png


def _append_pdf_image(path: Path, png: bytes) -> None:
    import pymupdf
    with pymupdf.open(path) as doc:
        previous_pages = len(doc)
        page = doc.new_page(width=841.89, height=595.28)  # A4 landscape
        # Dedicated bounded drawing page; the existing pages and RTL headings
        # remain untouched. The source identity appears in report + manifest.
        box = pymupdf.Rect(38, 34, 804, 560)
        page.insert_image(box, stream=png, keep_proportion=True)
        if len(doc) != previous_pages + 1:
            raise RuntimeError("صفحه نقشه به PDF گزارش اضافه نشد")
        data = doc.tobytes(garbage=3, deflate=True)
    path.write_bytes(data)


def _append_docx_image(path: Path, png: bytes, source_hash: str) -> None:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches

    doc = Document(path)
    doc.add_page_break()
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    bidi = OxmlElement("w:bidi")
    bidi.set(qn("w:val"), "1")
    paragraph._p.get_or_add_pPr().append(bidi)
    paragraph.add_run("نقشه دوبعدی محدوده متره مستند، نه پلان کامل ساختمان")
    image_paragraph = doc.add_paragraph()
    image_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    image_paragraph.add_run().add_picture(BytesIO(png), width=Inches(8.4))
    doc.add_paragraph("SHA-256: " + source_hash)
    doc.save(path)


def _append_xlsx_image(path: Path, png: bytes, links: list[dict], source_hash: str) -> None:
    from openpyxl import load_workbook
    from openpyxl.drawing.image import Image
    from core.reports.exporters import style_workbook

    book = load_workbook(path)
    if "نقشه مستند" in book.sheetnames:
        raise ValueError("برگه نقشه مستند تکراری است")
    sheet = book.create_sheet("نقشه مستند")
    sheet.sheet_view.rightToLeft = True
    sheet["A1"] = "نقشه دوبعدی محدوده متره مستند (نه پلان کامل)"
    sheet["A2"] = "SHA-256 منبع"
    sheet["B2"] = source_hash
    sheet.append(["شناسه عضو", "طبقه", "ردیف BOQ", "شناسه منبع", "مقدار مستند", "واحد"])
    for link in links:
        sheet.append([
            link["member_id"], link["floor_id"], link["boq_row_id"],
            link["source_id"], link["quantity"], link["unit"],
        ])
    sheet.column_dimensions["A"].width = 32
    sheet.column_dimensions["B"].width = 70
    sheet.column_dimensions["C"].width = 24
    sheet.column_dimensions["D"].width = 60
    sheet.column_dimensions["E"].width = 24
    sheet.column_dimensions["F"].width = 18
    picture = Image(BytesIO(png))
    picture.width = 840
    picture.height = 630
    sheet.add_image(picture, f"A{max(8, len(links) + 6)}")
    style_workbook(book, "نقشه مستند متره")
    # Existing style_workbook sets print_area to occupied CELLS only. Images
    # extend below those cells, so extend the print area to include the map.
    sheet.print_area = "A1:L50"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 1
    book.save(path)


def _table_rows(snapshot: dict, links: list[dict]) -> list[dict]:
    """Report the actual persisted, one-source BOQ quantities, not SVG numbers."""
    boq = snapshot.get("boq", [])
    result = []
    for link in links:
        no = int(link["boq_row_id"].removeprefix("boq-item-no:"))
        matches = [row for row in boq if row.get("item_no") == no]
        if len(matches) != 1:
            raise ValueError("ردیف گزارش با BOQ ثبت‌شده یکتا نیست")
        row = matches[0]
        if row.get("source_ids") != [link["source_id"]]:
            raise ValueError("ردیف گزارش، منبع دیگری دارد")
        result.append({
            "item_no": row["item_no"],
            "item_code": row["item_code"],
            "description": row["description"],
            "quantity": row["quantity"],
            "unit": row["unit"],
            "source_id": link["source_id"],
            "notes": "عضو: " + link["member_id"] + " | طبقه: " + link["floor_id"],
        })
    return result


def export_verified_2d_office_bundle(
    service, *, project_id: str, session_id: str,
    expected_project_version: int, expected_session_revision: int,
    revision: str, page: int, selected_takeoff_ids: tuple[str, ...],
    destination: str | Path,
) -> dict:
    """Create a complete multi-format report bundle only for a *current* snapshot.

    Before atomic publication, re-check exact project digest, version, source
    file SHA and the entire original crosswalk. An externally changed project
    or drawing invalidates the whole staging directory; no partial publication.
    """
    target = Path(destination)
    if target.exists():
        raise FileExistsError("مسیر بسته خروجی از قبل موجود است")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.parent.is_symlink():
        raise ValueError("مسیر نمادین خروجی پذیرفته نیست")
    before_digest = service.store.current_digest(project_id)
    snapshot = service.open_project(project_id)
    if not isinstance(snapshot, dict):
        raise KeyError(project_id)
    if service.store.current_digest(project_id) != before_digest:
        raise RuntimeError("پروژه هنگام تهیه snapshot تغییر کرد")
    args = dict(
        session_id=session_id, expected_project_version=expected_project_version,
        expected_session_revision=expected_session_revision,
        revision=revision, page=page, selected_takeoff_ids=selected_takeoff_ids,
    )
    source = link_source_backed_2d_overlay_to_boq(snapshot, **args)
    linked = source["manifest"]["links"]
    rows = _table_rows(snapshot, linked)
    report = build_report(
        "گزارش نقشه و ریزمتره مستند", rows,
        metadata={
            "project_id": project_id,
            "revision": revision,
            "source_sha256": source["manifest"]["source_sha256"],
            "شناسه نشست": session_id,
            "نسخه نشست": expected_session_revision,
            "نسخه پروژه": expected_project_version,
            "توضیح": "نقشه فقط محدوده برداشت دارای هندسه معتبر را نشان می‌دهد؛ تأیید طراحی نیست",
        },
    )
    if not report.validate()["valid"]:
        raise ValueError("گزارش متره مستند با اعتبارسنجی اصلی سازگار نیست")
    png = _svg_png(source["svg"])

    with tempfile.TemporaryDirectory(prefix="structuralpro_p7_p2_", dir=target.parent) as scratch:
        stage = Path(scratch) / "package"
        stage.mkdir()
        pdf = report.export(stage / "report.pdf", "pdf")
        docx = report.export(stage / "report.docx", "docx")
        xlsx = report.export(stage / "report.xlsx", "xlsx")
        csv = report.export(stage / "report.csv", "csv")
        (stage / "overlay.svg").write_text(source["svg"], encoding="utf-8")
        (stage / "overlay.png").write_bytes(png)
        original_sha = source["manifest"]["source_sha256"]
        _append_pdf_image(pdf, png)
        _append_docx_image(docx, png, original_sha)
        _append_xlsx_image(xlsx, png, linked, original_sha)
        items = [pdf, docx, xlsx, csv, stage / "overlay.svg", stage / "overlay.png"]
        file_manifest = build_bundle_manifest(items, project_id=project_id, revision=revision)
        file_manifest.update({
            "schema": "structuralpro.phase7.source-backed-2d-office-bundle.v1",
            "snapshot_project_version": expected_project_version,
            "snapshot_session_revision": expected_session_revision,
            "snapshot_digest": before_digest,
            "overlay": deepcopy(source["manifest"]),
            "status": "source_verified_not_engineering_approval",
            "quantity_authority": False,
            "financial_mutation": False,
            "csv_image_mode": "overlay.svg and overlay.png are separate sidecars",
        })
        manifest = stage / "manifest.json"
        manifest.write_text(json.dumps(file_manifest, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        if any(not p.is_file() or p.stat().st_size == 0 for p in [*items, manifest]):
            raise RuntimeError("بسته نقشه‌دار دارای فایل خالی است")
        # Fresh retrieval and full crosswalk, not a comparison with a cached
        # build result. Verify both before and after to detect concurrent writes.
        if service.store.current_digest(project_id) != before_digest:
            raise RuntimeError("پروژه پیش از انتشار بسته تغییر کرده است")
        latest = service.open_project(project_id)
        if latest != snapshot or link_source_backed_2d_overlay_to_boq(latest, **args) != source:
            raise RuntimeError("منبع یا نسخه گزارش با داده فعلی تطبیق ندارد")
        if service.store.current_digest(project_id) != before_digest:
            raise RuntimeError("پروژه در حین انتشار تغییر کرده است")
        if target.exists():
            raise FileExistsError("مسیر خروجی حین تهیه بسته ایجاد شده است")
        os.rename(stage, target)
    return {"destination": str(target), "manifest": file_manifest}
