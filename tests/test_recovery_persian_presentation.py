"""Known display labels are Persian; engine identities and numbers stay intact."""
from core.platform.application import StructuralProApp
from core.reports.exporters import export_csv


def test_manual_preview_and_missing_geometry_use_persian_labels(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.manual_takeoff import ManualTakeoffDialog
    qt = QApplication.instance() or QApplication([])
    service = StructuralProApp(tmp_path)
    service.create_project("پروژه", "p")
    dialog = ManualTakeoffDialog(service, "p")
    dialog.floor_id.setText("اول")
    dialog.entry_text.setPlainText("ستون: تعداد=2، عرض=0.5، عمق=0.4، ارتفاع=3")
    dialog.add_button.click()
    assert dialog.table.item(0, 2).text() == "ستون"
    assert dialog.table.item(0, 3).text() == "ستون"
    dialog.entry_text.setPlainText("ستون: تعداد=2")
    dialog.add_button.click()
    missing = dialog.table.item(1, 6).text()
    assert "عرض" in missing and "عمق" in missing and "ارتفاع" in missing
    assert "width" not in missing and "column" not in dialog.status.text()
    dialog.save_button.click()
    data = service.open_project("p")
    assert data["takeoffs"][0]["item"] == "column"
    assert data["takeoffs"][0]["description"] == "ستون"
    assert len(data["takeoffs"]) == 1
    service.store.close()
    dialog.close()


def test_report_status_display_is_persian_without_mutating_source(tmp_path):
    import csv
    rows = [{"code": "0001", "status": "active", "quantity": 2.5},
            {"code": "0002", "status": "cancelled", "quantity": 1}]
    path = export_csv(rows, tmp_path / "rows.csv", columns=[("code", "کد"), ("status", "وضعیت"), ("quantity", "مقدار")])
    with path.open(encoding="utf-8-sig", newline="") as stream:
        records = list(csv.reader(stream))
    assert ["0001", "فعال", "2.5"] in records
    assert ["0002", "لغوشده", "1"] in records
    assert rows[0]["status"] == "active" and rows[1]["status"] == "cancelled"
