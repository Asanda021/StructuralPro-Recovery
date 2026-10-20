"""Real Qt dialogs and clicks, real vector PDF and SQLite; synthetic design."""
import json
from pathlib import Path
import pytest
from PySide6.QtWidgets import QApplication,QMessageBox,QInputDialog,QFileDialog,QTabWidget
from PySide6.QtCore import Qt,QTimer,QRectF
from PySide6.QtTest import QTest
from app.graphical_takeoff import GraphicalTakeoffDialog
from test_phase2_pdf_roof import fixture
from test_roof_specialist_work import sample,KINDS

_qt=None
@pytest.fixture
def qt():
    global _qt
    _qt=QApplication.instance() or QApplication([])
    return _qt

@pytest.mark.parametrize('kind',KINDS)
def test_actual_pdf_region_to_specialist_boq(qt,tmp_path,monkeypatch,kind):
    from core.drawings.roof_region import detail_payload
    from core.takeoff.reviewed_aec import SPECS
    app,s,item,rec=fixture(tmp_path,kind);warnings=[];errors=[]
    dlg=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P');dlg.show();qt.processEvents()
    # Existing calibrated measurement is restored into the actual drawing window.
    dlg.session=s;dlg.canvas.session=s;dlg.persisted_session_id=rec['session_id'];dlg.persisted_session_revision=1
    dlg.refresh();dlg.scale_label.setText('مقیاس: 0.01 متر بر پیکسل');dlg.canvas._set_region_highlight(QRectF(100,100,400,400))
    monkeypatch.setattr(QInputDialog,'getItem',lambda *a,**k:(SPECS[kind].title,True))
    monkeypatch.setattr(QMessageBox,'warning',lambda p,t,m,*a:warnings.append(str(m)))
    monkeypatch.setattr(QMessageBox,'critical',lambda p,t,m,*a:warnings.append(str(m)))
    doc=tmp_path/'schedule.json';doc.write_text(json.dumps(detail_payload(sample(kind)),ensure_ascii=False),encoding='utf8')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *a,**k:(str(doc),''))
    def click(c,key):
        b=c[key];tabs=b.window().findChild(QTabWidget)
        if tabs:
            for i in range(tabs.count()):
                if tabs.widget(i).isAncestorOf(b):tabs.setCurrentIndex(i);break
        qt.processEvents();QTest.mouseClick(b,Qt.LeftButton);qt.processEvents()
    def journey():
        roof=qt.activeModalWidget()
        try:
            assert roof.objectName()=='RoofDetailEditor' and roof.layoutDirection()==Qt.RightToLeft
            c=roof.roof_controls;c['floor'].setText('L1');c['id'].setText('S1');click(c,'new')
            assert c['length'].text()=='4.000' or float(c['length'].text())==4
            assert not c['source'].isEnabled() and not c['kind'].isEnabled()
            c['plan'].setText('پلان مصنوعی');c['detail'].setText('دیتایل مصنوعی')
            click(c,'import_detail');click(c,'preview');assert 'محاسبه معتبر' in c['message'].text(),warnings
            assert c['summary'].columnWidth(0)>=200
            c['summary'].scrollToBottom();roof.grab().save(str(tmp_path/(kind+'-form.png')))
            click(c,'save');c['reviewer'].setText('بازبین مستقل مصنوعی');c['note'].setText('تطبیق آزمونی با جدول')
            click(c,'review');click(c,'commit')
            assert app.get_aec_system('P',kind,'L1','S1')['status']=='committed',warnings
            assert app.open_project('P')['boq']
        except Exception as exc:errors.append(repr(exc))
        finally:roof.reject()
    try:
        assert hasattr(dlg,'region_to_roof'), 'missing specialist button'
        QTimer.singleShot(40,journey);QTest.mouseClick(dlg.region_to_roof,Qt.LeftButton)
        dlg.grab().save(str(tmp_path/(kind+'-pdf.png')))
        assert not errors and not warnings,(errors,warnings)
    finally:dlg.close();app.store.close()


def test_calibration_ui_has_no_assumed_dimensions(qt,tmp_path,monkeypatch):
    app,s,item,rec=fixture(tmp_path);dlg=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P')
    calls=[]
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:(calls.append((args,kwargs)) or ('',False)))
    QTest.mouseClick(dlg.calibrate,Qt.LeftButton)
    assert len(calls)==1 and not calls[0][1].get('text')
    dlg.close();app.store.close()


def test_opening_button_updates_same_row_and_undo(qt,tmp_path,monkeypatch):
    app,s,item,rec=fixture(tmp_path);dlg=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P')
    dlg.session=s;dlg.canvas.session=s;dlg.refresh();dlg.show();qt.processEvents();QTest.mouseClick(dlg.table.viewport(),Qt.LeftButton,pos=dlg.table.visualItemRect(dlg.table.item(0,0)).center())
    dlg.canvas._set_region_highlight(QRectF(200,200,100,100))
    monkeypatch.setattr(QInputDialog,'getText',lambda *a,**k:('مدرک بازشو مصنوعی',True))
    try:
        assert hasattr(dlg,'opening_button')
        QTest.mouseClick(dlg.opening_button,Qt.LeftButton);qt.processEvents()
        assert len(s.items)==1 and s.find(item.id).quantity==15
        QTest.mouseClick(dlg.undo,Qt.LeftButton);assert s.find(item.id).quantity==16
        QTest.mouseClick(dlg.redo,Qt.LeftButton);assert s.find(item.id).quantity==15
    finally:dlg.close();app.store.close()


def test_fresh_multi_page_pdf_calibration_and_mouse_region(qt,tmp_path):
    from PySide6.QtWidgets import QDialogButtonBox
    from PySide6.QtCore import QPointF
    app,_,_,_=fixture(tmp_path);dlg=GraphicalTakeoffDialog(pdf_path=str(tmp_path/'plan.pdf'),app_service=app,project_id='P')
    dlg.resize(1600,1200);dlg.show();qt.processEvents();errors=[]
    def answer(value,next_value=None):
        widget=qt.activeModalWidget()
        try:
            assert isinstance(widget,QInputDialog);widget.setTextValue(value)
            if next_value:QTimer.singleShot(30,lambda:answer(next_value))
            box=widget.findChild(QDialogButtonBox);QTest.mouseClick(box.button(QDialogButtonBox.Ok),Qt.LeftButton)
        except Exception as exc:errors.append(repr(exc));widget.reject()
    try:
        assert dlg.engine.page_count==2
        QTimer.singleShot(30,lambda:answer('400','4'));QTest.mouseClick(dlg.calibrate,Qt.LeftButton)
        assert not errors and dlg.session.calibration.meters_per_pixel==.01
        QTest.mouseClick(dlg.next,Qt.LeftButton);assert dlg.page==2 and dlg.session.calibration is None
        QTest.mouseClick(dlg.prev,Qt.LeftButton);assert dlg.page==1 and dlg.session.calibration.meters_per_pixel==.01
        dlg.canvas.resetTransform();qt.processEvents()
        QTest.mouseClick(dlg.select_region,Qt.LeftButton)
        a=dlg.canvas.mapFromScene(QPointF(100,100));b=dlg.canvas.mapFromScene(QPointF(500,500));v=dlg.canvas.viewport()
        QTest.mousePress(v,Qt.LeftButton,pos=a);QTest.mouseMove(v,b,20);QTest.mouseRelease(v,Qt.LeftButton,pos=b)
        r=dlg.canvas._selected_region_rect
        assert r and r.width()==400 and r.height()==400
        before=QRectF(r);QTest.mouseClick(dlg.zoom_window,Qt.LeftButton)
        QTest.mousePress(v,Qt.LeftButton,pos=a);QTest.mouseMove(v,b,20);QTest.mouseRelease(v,Qt.LeftButton,pos=b)
        assert dlg.canvas._selected_region_rect==before
        dlg.grab().save(str(tmp_path/'fresh-pdf-native-calibration.png'))
        assert dlg.session.items==[] # navigation and selection do not commit anything
    finally:dlg.close();app.store.close()
