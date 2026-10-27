"""P6-5 E3 Qt real widget state and zero-side-effect preview."""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from app.project_start_wizard import ProjectStartWizard


def test_corrupt_profile_storage_is_not_silently_overwritten(tmp_path):
    from PySide6.QtCore import QSettings
    qt=QApplication.instance() or QApplication([])
    settings=QSettings(str(tmp_path/'profile.ini'),QSettings.IniFormat)
    broken='{"old_profile": unfinished'
    settings.setValue('e3/custom',broken);settings.sync()
    app=StructuralProApp(tmp_path/'db');ui=ProjectStartWizard(app,settings=settings)
    try:
        ui.kind.setCurrentIndex(ui.kind.findData('residential'))
        ui.profile_name.setText('جدید')
        assert not ui.save_profile(), 'saving a profile silently discards unreadable existing profiles'
        assert settings.value('e3/custom')==broken
        assert app.store.list()==[]
    finally:ui.close();app.store.close();qt.processEvents()


def test_e3_click_preview_modify_cancel_and_create_sqlite(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"data")
    seen=[]
    ui=ProjectStartWizard(app,on_created=seen.append)
    try:
        ui.kind.setCurrentIndex(ui.kind.findData("residential"))
        ui.project_id.setText("E3")
        ui.name.setText("پروژه آزمایشی")
        ui.floors.setValue(5)
        ui.show()
        assert app.store.list()==[]
        QTest.mouseClick(ui.preview_button,Qt.MouseButton.LeftButton)
        assert ui.create_button.isEnabled()
        assert app.store.list()==[]
        ui.floors.setValue(1)
        assert not ui.create_button.isEnabled()
        assert ui.preview_data is None
        QTest.mouseClick(ui.preview_button,Qt.MouseButton.LeftButton)
        QTest.mouseClick(ui.create_button,Qt.MouseButton.LeftButton)
        assert seen==["E3"]
        p=app.open_project("E3")
        assert len(p["floors"])==1 and not p["boq"] and not p["members"]
        assert app.store.list()[0]["id"]=="E3"
    finally:
        ui.close();app.store.close();qt.processEvents()


def test_e3_incomplete_and_reused_id_do_not_modify(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"data")
    app.create_project("موجود","P")
    digest=app.store.current_digest("P")
    ui=ProjectStartWizard(app)
    try:
        assert ui.preview() is None and not ui.create_button.isEnabled()
        ui.kind.setCurrentIndex(ui.kind.findData("industrial"))
        ui.project_id.setText("P");ui.name.setText("جدید");ui.floors.setValue(1)
        assert ui.preview() is not None
        assert ui.create() is None
        assert not ui.create_button.isEnabled()
        assert digest==app.store.current_digest("P")
    finally:
        ui.close();app.store.close();qt.processEvents()

def test_saved_user_profile_reopens_with_selected_disciplines(tmp_path):
    from PySide6.QtCore import QSettings
    qt=QApplication.instance() or QApplication([])
    settings=QSettings(str(tmp_path/"profile.ini"),QSettings.Format.IniFormat)
    app=StructuralProApp(tmp_path/"db")
    first=ProjectStartWizard(app,settings=settings)
    first.kind.setCurrentIndex(first.kind.findData("industrial"))
    first.profile_name.setText("کارخانه کوچک")
    first.profile_disciplines.setText("civil,steel,electrical")
    assert first.save_profile()
    assert app.store.list()==[]
    first.close()
    ui=ProjectStartWizard(app,settings=settings)
    try:
        ui.kind.setCurrentIndex(ui.kind.findData("custom:کارخانه کوچک"))
        ui.project_id.setText("IC");ui.name.setText("کارخانه");ui.floors.setValue(5)
        assert ui.preview()["disciplines"]==["civil","steel","electrical"]
        assert ui.create()["template_start"]["disciplines"]==["civil","steel","electrical"]
        assert ui.delete_profile()
        assert app.open_project("IC")["boq"]==[]
    finally:ui.close();app.store.close();qt.processEvents()
