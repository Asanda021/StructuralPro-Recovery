"""Actual source-only Qt and Office/PDF acceptance; no build or release.

Linux results explicitly remain Linux results. Windows Office compatibility
and owner visual acceptance require review on the actual Windows applications.
"""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
import unicodedata
import zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def probe(output: Path) -> dict:
    if sys.platform != "win32":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    elif os.environ.get("QT_QPA_PLATFORM", "").lower() in {"offscreen", "minimal"}:
        raise RuntimeError("Windows visible desktop probe cannot run offscreen")
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QMessageBox
    from app.manual_takeoff import ManualTakeoffDialog
    from core.platform.application import StructuralProApp
    from core.reports import build_report
    import pymupdf
    from openpyxl import load_workbook

    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    with tempfile.TemporaryDirectory(prefix="structuralpro_probe_") as d:
        service = StructuralProApp(d)
        service.create_project("پروژه پذیرش رابط فارسی", "UI-QA")
        dialog = ManualTakeoffDialog(service, "UI-QA")
        dialog.show()
        app.processEvents()
        assert dialog.layoutDirection() == Qt.LayoutDirection.RightToLeft
        assert "متره" in dialog.windowTitle()
        assert "پیش‌نمایش" in dialog.add_button.text()
        warnings = []
        timer = QTimer()
        def dismiss_actual_warning():
            modal = app.activeModalWidget()
            if isinstance(modal, QMessageBox):
                warnings.append(modal.text())
                modal.accept()
        timer.timeout.connect(dismiss_actual_warning)
        timer.start(10)
        # Click the real connected button: missing floor opens a real Persian warning.
        QTest.mouseClick(dialog.add_button, Qt.MouseButton.LeftButton)
        timer.stop()
        assert warnings and "طبقه" in warnings[0]
        dialog.floor_id.setText("طبقه اول")
        dialog.entry_text.setPlainText("ستون: تعداد=2، عرض=0.5، عمق=0.4، ارتفاع=3")
        QTest.mouseClick(dialog.add_button, Qt.MouseButton.LeftButton)
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0,4).text()==str(dialog.workbench.records[0].quantity)
        assert abs(float(dialog.table.item(0,4).text())-1.2)<1e-12
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        assert "ذخیره شد" in dialog.status.text()
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        assert "قبلاً ذخیره" in dialog.status.text()
        # Incomplete geometry remains a visible draft and is never persisted.
        dialog.entry_text.setPlainText("ستون: تعداد=2")
        QTest.mouseClick(dialog.add_button, Qt.MouseButton.LeftButton)
        assert "ناقص" in dialog.status.text()
        QTest.mouseClick(dialog.save_button, Qt.MouseButton.LeftButton)
        assert dialog.grab().save(str(output / "manual_preview_save.png"))
        dialog.close();dialog.deleteLater()
        from PySide6.QtCore import QCoreApplication,QEvent
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
        service.store.close()
        reopened = StructuralProApp(d)
        project = reopened.open_project("UI-QA")
        assert len(project["takeoffs"]) == 1
        row = project["takeoffs"][0]
        assert abs(row["quantities"][0]["amount"] - 1.2) < 1e-12
        assert row["revision"] == 1 and row["source_id"].startswith("manual-workbench:")
        assert {x["event"] for x in project["_manual_takeoff_audit"]} >= {"preview_added", "rows_saved"}
        assert reopened.store.db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        reopened.store.close()

    # Explicit synthetic rows: independent arithmetic reference sum(1..120)/10=726.
    rows = [{"item_no": i, "item_code": f"{i:04d}", "description": f"کاشی کف ردیف {i}",
             "quantity": i / 10, "unit": "m2", "unit_price": 1,
             "total": i / 10, "status": "active", "source_id": f"QA-{i}"}
            for i in range(1, 121)]
    total = sum(range(1, 121)) / 10
    assert total == 726
    report = build_report("پروژه پذیرش گزارش فارسی", rows,
                          {"base": total, "grand_total": total, "line_count": 120})
    assert report.validate()["valid"]
    paths = {fmt: report.export(output / ("persian_quantities." + fmt), fmt)
             for fmt in ("csv", "xlsx", "docx", "pdf")}
    with paths["csv"].open(encoding="utf-8-sig", newline="") as f:
        csv_rows = list(csv.reader(f))
    assert any("0001" in r for r in csv_rows)
    workbook = load_workbook(paths["xlsx"])
    sheet = workbook["ریز متره"]
    assert sheet.sheet_view.rightToLeft
    values = list(sheet.values)
    assert any("0001" in r for r in values)
    header = next(r for r in values if "مقدار" in r and "شرح" in r)
    quantity_column = header.index("مقدار")
    detail = [r for r in values if "m2" in r]
    assert len(detail) == 120
    assert all("فعال" in row for row in detail)
    assert abs(sum(r[quantity_column] for r in detail) - total) < 1e-9
    assert workbook["خلاصه"].sheet_view.rightToLeft
    workbook.close()
    with zipfile.ZipFile(paths["docx"]) as z:
        document = ET.fromstring(z.read("word/document.xml"))
        ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        assert document.findall(".//w:bidiVisual", ns)
        assert document.findall(".//w:bidi", ns)
        texts = [x.text for x in document.findall(".//w:t", ns)]
        assert "0001" in texts and "کاشی کف ردیف 1" in texts
        assert "فعال" in texts and "active" not in texts
    pdf = pymupdf.open(paths["pdf"])
    assert len(pdf) >= 2
    page_text = []
    for i, page in enumerate(pdf):
        text = page.get_text()
        assert text.strip()
        # PDF extraction returns logical character order; normalize Persian
        # presentation forms instead of confusing them with visual glyph order.
        assert "شرح" in unicodedata.normalize("NFKC", text)
        assert "فعال" in unicodedata.normalize("NFKC", text)
        page_text.append(text)
        page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(output / f"pdf_page_{i+1:02d}.png")
    assert "0001" in "\n".join(page_text) and "0120" in "\n".join(page_text)
    (output / "pdf_extracted_text.txt").write_text("\n\n".join(page_text), encoding="utf-8")
    count = len(pdf)
    pdf.close()
    result = {"platform": sys.platform, "qt_preview_save_reopen": True,
              "actual_validation_warning": warnings, "duplicate_save_prevented": True,
              "incomplete_geometry_not_persisted": True, "sqlite_integrity": "ok",
              "export_rows": 120, "independent_quantity_sum": total,
              "pdf_pages_rendered": count, "xlsx_numeric_sum": total,
              "docx_rtl": True, "windows_office_visual_acceptance": "PENDING",
              "windows_acceptance": "NOT_CLAIMED", "owner_visual_review": "PENDING"}
    (output / "ui_exports.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(probe(args.out_dir), ensure_ascii=False))
