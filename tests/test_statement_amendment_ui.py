"""Real Qt clicks with explicitly synthetic authority, files and issued rows."""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from app.statement_amendment import StatementAmendmentDialog
from test_statement_amendment_workflow import fixture

def test_real_clicks_create_edit_review_approve_post_and_export(tmp_path,monkeypatch):
    qt=QApplication.instance() or QApplication([])
    a,docs,_,_=fixture(tmp_path);dialog=StatementAmendmentDialog(a,'P');dialog.show();qt.processEvents()
    dialog.actor.setText('writer');dialog.period.setText('1');dialog.reason.setText('داده آزمایشی صریح')
    dialog.docs.setPlainText(json.dumps(docs))
    lines=[{'price_code':'W','source_id':'wall-1','corrected_period_quantity':'4','reason':'دیتایل مصنوعی','detail_source_ref':'DETAIL-1'}]
    dialog.lines.setPlainText(json.dumps(lines))
    def click(op):QTest.mouseClick(dialog.buttons[op],Qt.LeftButton);qt.processEvents()
    click('create');assert dialog.document()['status']=='DRAFT'
    click('edit');assert dialog.document()['revision']==2
    dialog.actor.setText('writer');click('review');assert dialog.document()['status']=='DRAFT' and 'خطا' in dialog.output.toPlainText()
    for actor,op,state in [('reviewer','review','REVIEWED'),('approver','approve','APPROVED'),('approver','post','POSTED')]:
        dialog.actor.setText(actor);click(op);assert dialog.document()['status']==state,dialog.output.toPlainText()
    click('post');assert len(a.statement_amendment_summary('P',1)['posted_amendment_ids'])==1
    from PySide6.QtWidgets import QFileDialog,QPushButton
    for fmt in ('pdf','xlsx','csv'):
        path=tmp_path/('amendment.'+fmt)
        monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,path=path,**kw:(str(path),''))
        QTest.mouseClick(dialog.findChild(QPushButton,'AmendmentExport_'+fmt),Qt.LeftButton);qt.processEvents()
        assert path.is_file() and path.stat().st_size>100,dialog.output.toPlainText()
    dialog.close();a.store.close()

def test_missing_policy_and_concurrent_refresh_are_explicit(tmp_path):
    qt=QApplication.instance() or QApplication([])
    a,docs,_,_=fixture(tmp_path);a.create_project('فاقد مجوز','U')
    blocked=StatementAmendmentDialog(a,'U');assert 'BLOCKED' in blocked.output.toPlainText();blocked.close()
    dialog=StatementAmendmentDialog(a,'P');dialog.actor.setText('writer');dialog.period.setText('1');dialog.reason.setText('دیتایل')
    dialog.docs.setPlainText(json.dumps(docs));dialog.lines.setPlainText(json.dumps([{'price_code':'W','source_id':'wall-1','corrected_period_quantity':'4','reason':'دیتایل','detail_source_ref':'DETAIL-1'}]))
    a.add_project_cost('P','مصالح',25)
    dialog.buttons['create'].click();assert 'نسخه پروژه تغییر' in dialog.output.toPlainText() and not a.statement_amendments('P')
    dialog.buttons['refresh'].click();dialog.buttons['create'].click();assert len(a.statement_amendments('P'))==1
    dialog.close();a.store.close()
