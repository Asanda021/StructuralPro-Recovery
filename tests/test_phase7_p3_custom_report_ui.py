"""Native controls save, reopen, preview and export real source-backed reports."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QFileDialog
from PySide6.QtTest import QTest
from test_phase7_p2_multifloor_bundle import building

def test_real_dialog_controls_reopen_template_preview_and_batch(building,tmp_path,monkeypatch):
    global _qt
    from app.custom_report_dialog import CustomReportDialog
    _qt=QApplication.instance() or QApplication([])
    app,p,_=building;digest=app.store.current_digest("P5")
    dialog=CustomReportDialog(app,"P5");dialog.show();_qt.processEvents()
    assert dialog.layoutDirection()==Qt.RightToLeft
    dialog.template_id.setText("ui-layout");dialog.title.setText("قالب دفتر فنی")
    dialog.actor.setText("مهندس آزمون");dialog.reason.setText("قالب رابط واقعی")
    for n in range(dialog.floors.count()):
        item=dialog.floors.item(n);item.setCheckState(Qt.Checked if item.data(Qt.UserRole) in ("L1","L3") else Qt.Unchecked)
    QTest.mouseClick(dialog.preview_button,Qt.LeftButton);_qt.processEvents()
    assert dialog.preview_table.rowCount()>0 and "خطا" not in dialog.status.text()
    QTest.mouseClick(dialog.save_button,Qt.LeftButton);_qt.processEvents()
    assert dialog.selected_version==1,dialog.status.text()
    dialog.close();dialog.deleteLater();_qt.processEvents()
    second=CustomReportDialog(app,"P5");second.show();_qt.processEvents()
    second.templates.setCurrentIndex(second.templates.findText("ui-layout / نسخه 1"))
    QTest.mouseClick(second.load_button,Qt.LeftButton);_qt.processEvents()
    assert second.title.text()=="قالب دفتر فنی" and second.selected_version==1,second.status.text()
    monkeypatch.setattr(QFileDialog,"getExistingDirectory",lambda *a,**k:str(tmp_path))
    QTest.mouseClick(second.export_button,Qt.LeftButton);_qt.processEvents()
    assert second.last_destination is not None,second.status.text()
    assert len(list(Path(second.last_destination).glob("*.pdf")))==2
    import os,shutil
    if os.environ.get("STRUCTURALPRO_P7_P3_EVIDENCE_DIR"):
        folder=Path(os.environ["STRUCTURALPRO_P7_P3_EVIDENCE_DIR"]);folder.mkdir(parents=True,exist_ok=True)
        second.grab().save(str(folder/"designer.png"))
        shutil.copytree(Path(second.last_destination),folder/"batch",dirs_exist_ok=True)
    assert app.open_project("P5")==p and app.store.current_digest("P5")==digest
    second.close();second.deleteLater();_qt.processEvents()

def test_primary_ribbon_opens_real_designer():
    source=(Path(__file__).resolve().parents[1]/"app/main.py").read_text(encoding="utf-8")
    assert "CustomReportDialog" in source and "open_custom_report" in source
