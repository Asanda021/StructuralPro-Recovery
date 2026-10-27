"""E4 Qt real browse and CAS invalidation, no BOQ mutation."""
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from core.platform.application import StructuralProApp
from app.project_search_panel import ProjectSearchDialog


def test_search_live_member_and_stale_fails_closed(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه اصلی","P")
    app.add_project_floor("P","طبقه ۲",level="F2")
    app.add_project_member("P","M12","F2","column")
    before=app.store.current_digest("P")
    navigated=[]
    panel=ProjectSearchDialog(app,"P",initial_query="M12",
                              on_navigate=lambda *args:navigated.append(args))
    try:
        assert panel.list.count()>=1
        panel.list.setCurrentRow(0)
        QTest.mouseClick(panel.open_button,Qt.MouseButton.LeftButton)
        assert '"M12"' in panel.detail.toPlainText()
        assert navigated==[("projects","P","M12")]
        assert app.store.current_digest("P")==before
        app.add_project_floor("P","طبقه ۳",level="F3")
        assert panel.open_record() is None
        assert not panel.open_button.isEnabled()
        assert app.open_project("P")["boq"]==[]
    finally:
        panel.close();app.store.close();qt.processEvents()


def test_search_does_not_read_other_project(tmp_path):
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"app")
    app.create_project("پروژه یک","P1")
    app.create_project("پروژه محرمانه","P2")
    dialog=ProjectSearchDialog(app,"P1",initial_query="محرمانه")
    try:
        assert dialog.list.count()==0
        assert dialog.open_record() is None
        assert app.open_project("P2")["name"]=="پروژه محرمانه"
    finally:
        dialog.close();app.store.close();qt.processEvents()

def test_boq_navigation_selects_exact_stored_row_without_financial_recalc(tmp_path):
    from PySide6.QtWidgets import QApplication,QTableWidget
    from app.project_search_panel import display_verified_boq_row
    qt=QApplication.instance() or QApplication([])
    table=QTableWidget(0,6)
    project={"id":"P","boq":[
        {"row_id":"B1","description":"دیوار","quantity":"13.00","unit":"m2"},
        {"row_id":"B2","description":"سقف","quantity":"2.50","unit":"m3"},
    ]}
    before=repr(project)
    assert display_verified_boq_row(project,"B2",table)==1
    assert table.currentRow()==1
    assert table.item(1,1).text()=="سقف"
    assert table.item(1,2).text()=="2.50"
    assert table.item(1,5).text()=="بدون مبلغ مصوب"
    assert repr(project)==before
    table.close();qt.processEvents()


def test_boq_duplicate_identity_refused_without_changing_table(tmp_path):
    import pytest
    from PySide6.QtWidgets import QApplication,QTableWidget
    from app.project_search_panel import display_verified_boq_row
    qt=QApplication.instance() or QApplication([])
    table=QTableWidget(0,6)
    project={"id":"P","boq":[{"row_id":"B1","description":"الف"},
                             {"row_id":"B1","description":"ب"}]}
    with pytest.raises(ValueError):
        display_verified_boq_row(project,"B1",table)
    assert table.rowCount()==0
    table.close();qt.processEvents()
