"""Actual Qt button journey for U-Boot/Cobiax, run offscreen with synthetic evidence.

The tests use a real modal editor and real button clicks. They are not Windows
acceptance; no dummy exec/save substitutes for product handlers are installed.
"""
import pytest
from test_void_former_roofs_20261016 import sample,KINDS
from core.platform.application import StructuralProApp


@pytest.mark.parametrize("kind",KINDS)
def test_real_void_former_form_preview_save_review_boq(tmp_path,kind,monkeypatch):
    from PySide6.QtWidgets import QApplication,QMessageBox,QTabWidget,QScrollArea
    from PySide6.QtCore import Qt,QTimer
    from PySide6.QtTest import QTest
    from app.roof_detail_editor import (
        open_roof_editor,fill_table,REGIONS,DEDUCTIONS,
        VOID_FORMERS,STEEL,FACES,PROPS,
    )
    global _qt
    _qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path/"db")
    app.create_project("پروژه آزمون مصنوعی","P")
    fixture=sample(kind)
    warnings=[];failures=[];clicked=[]
    monkeypatch.setattr(
        QMessageBox,"warning",lambda parent,title,message,*args:warnings.append(str(message))
    )

    def click(dlg,button,name):
        tabs=dlg.findChild(QTabWidget)
        for i in range(tabs.count()):
            if tabs.widget(i).isAncestorOf(button):
                tabs.setCurrentIndex(i)
                break
        _qt.processEvents()
        p=button
        while p is not None:
            if isinstance(p,QScrollArea):
                p.ensureWidgetVisible(button)
            p=p.parentWidget()
        _qt.processEvents()
        QTest.mouseClick(button,Qt.LeftButton)
        _qt.processEvents()
        clicked.append(name)

    def run():
        dlg=_qt.activeModalWidget();c=dlg.roof_controls
        try:
            c["id"].setText("S1")
            click(dlg,c["new"],"new")
            assert c["void_formers"].isEnabled()
            assert not c["pieces"].isEnabled()
            g=fixture["roof_detail"]["geometry"]
            for key in ("unit","shape","repeat_scope"):
                c[key].setCurrentIndex(c[key].findData(g[key]))
            for key in ("length","width","depth","count","topping_thickness","bottom_thickness"):
                c[key].setText(g[key])
            for key,value in [
                ("building","B1"),("source",fixture["source"]["source_id"]),
                ("plan",fixture["source"]["plan_ref"]),("detail",fixture["source"]["detail_ref"]),
                ("geometry_ref",g["source_ref"]),("geometry_approver",g["approved_by"]),
                ("deductions_ref","عدم بازشو مصنوعی"),("pieces_ref","عدم کاربرد قطعات دیگر"),
            ]:
                c[key].setText(value)
            rd=fixture["roof_detail"]
            fill_table(c["regions"],REGIONS,rd["regions"])
            fill_table(c["deductions"],DEDUCTIONS,[])
            fill_table(c["void_formers"],VOID_FORMERS,rd["void_formers"])
            for group,part in rd["rebars"].items():
                c["bar_group"].setCurrentIndex(c["bar_group"].findData(group))
                c["bar_status"].setCurrentIndex(c["bar_status"].findData(part["status"]))
                for key,value in [
                    ("bar_approver",part.get("approved_by","")),
                    ("bar_ref",part.get("source_ref","")),
                    ("bar_reason",part.get("reason","")),
                ]:
                    c[key].setText(value)
                fill_table(c["bars"],STEEL,part.get("series",[]))
                click(dlg,c["store_bar"],"store_bar")
            for key,cols,field in [
                ("formwork",FACES,"faces"),("shoring",PROPS,"props"),
            ]:
                part=rd[key]
                c[key+"_status"].setCurrentIndex(c[key+"_status"].findData(part["status"]))
                for suffix,source in [
                    ("approver","approved_by"),("ref","source_ref"),("reason","reason"),
                ]:
                    c[key+"_"+suffix].setText(part.get(source,""))
                fill_table(c[key],cols,part.get(field,[]))
            click(dlg,c["preview"],"preview")
            assert "محاسبه معتبر" in c["message"].text(),(c["message"].text(),warnings)
            click(dlg,c["save"],"save")
            record=app.get_aec_system("P",kind,"L1","S1")
            assert record["revision"]==1 and len(record["data"]["roof_detail"]["void_formers"])==1
            c["reviewer"].setText("بازبین مصنوعی مستقل")
            c["note"].setText("کنترل واحد، جانمایی و حجم گواهی مصنوعی")
            click(dlg,c["review"],"review")
            assert app.get_aec_system("P",kind,"L1","S1")["revision"]==2
            click(dlg,c["commit"],"commit")
            assert app.get_aec_system("P",kind,"L1","S1")["status"]=="committed"
            assert app.open_project("P")["boq"]
            assert not warnings,warnings
            assert len(clicked)>=10
        except Exception as e:
            failures.append(repr(e))
        finally:
            dlg.reject()

    QTimer.singleShot(50,run)
    open_roof_editor(app,project_id="P",floor_id="L1",kind=kind)
    app.store.close()
    assert not failures,failures
