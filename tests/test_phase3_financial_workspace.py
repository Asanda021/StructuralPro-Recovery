from PySide6.QtWidgets import QApplication,QLineEdit,QPushButton,QLabel,QComboBox,QTabWidget
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from test_statement_amendment_workflow import fixture


def test_real_workspace_registers_budget_and_rejects_duplicate(tmp_path):
    from app.financial_workspace import FinancialWorkspace
    a,docs,_,_=fixture(tmp_path);qt=QApplication.instance() or QApplication([])
    w=FinancialWorkspace(a,'P');w.show();w.findChild(QTabWidget).setCurrentIndex(1);qt.processEvents()
    fields={'FinanceActor':'writer','FinanceReference':'B-QT','FinanceAmount':'900','FinanceDate':'2026-10-23','FinanceParty':'آزمون','FinanceDescription':'بودجه آزمایشی','FinanceProof':docs[0]['path'],'FinanceSHA':docs[0]['sha256']}
    for name,value in fields.items():w.findChild(QLineEdit,name).setText(value)
    w.findChild(QComboBox,'FinanceKind').setCurrentIndex(0)
    QTest.mouseClick(w.findChild(QPushButton,'FinanceCreate'),Qt.LeftButton)
    assert a.open_project('P')['financial_records'][0]['status']=='DRAFT'
    assert w.records.rowCount()==1,w.status.text()
    qt.processEvents()
    QTest.mouseClick(w.records.viewport(),Qt.LeftButton,pos=w.records.visualItemRect(w.records.item(0,0)).center())
    w.findChild(QLineEdit,'FinanceActor').setText('reviewer')
    QTest.mouseClick(w.findChild(QPushButton,'FinanceReview'),Qt.LeftButton)
    assert a.open_project('P')['financial_records'][0]['status']=='REVIEWED',w.status.text()
    qt.processEvents()
    QTest.mouseClick(w.records.viewport(),Qt.LeftButton,pos=w.records.visualItemRect(w.records.item(0,0)).center())
    w.findChild(QLineEdit,'FinanceActor').setText('approver')
    QTest.mouseClick(w.findChild(QPushButton,'FinanceApprove'),Qt.LeftButton)
    qt.processEvents()
    QTest.mouseClick(w.records.viewport(),Qt.LeftButton,pos=w.records.visualItemRect(w.records.item(0,0)).center())
    QTest.mouseClick(w.findChild(QPushButton,'FinancePost'),Qt.LeftButton)
    assert a.verified_financial_snapshot('P')['budget']==900,w.findChild(QLabel,'FinanceStatus').text()
    before=a.store.current_digest('P')
    w.findChild(QLineEdit,'FinanceActor').setText('writer')
    QTest.mouseClick(w.findChild(QPushButton,'FinanceCreate'),Qt.LeftButton)
    assert a.store.current_digest('P')==before
    assert 'خطا' in w.findChild(QLabel,'FinanceStatus').text()
    w.close();a.store.close()


def test_statement_lifecycle_real_clicks(tmp_path,monkeypatch):
    from app.financial_workspace import FinancialWorkspace
    from test_phase3_statement_ledger_completion import setup_workflow
    a,docs,_,_=fixture(tmp_path);setup_workflow(a,docs)
    qt=QApplication.instance() or QApplication([]);w=FinancialWorkspace(a,'P');w.show();qt.processEvents()
    for name,value in [('FinanceActor','writer'),('FinanceDate','2026-10-23'),('FinanceStatementReference','S-QT'),('FinanceQuantities','W=1')]:w.findChild(QLineEdit,name).setText(value)
    QTest.mouseClick(w.findChild(QPushButton,'StatementCreate'),Qt.LeftButton)
    for name,actor in [('StatementReview','reviewer'),('StatementApprove','approver'),('StatementIssue','approver')]:
        qt.processEvents();QTest.mouseClick(w.statements.viewport(),Qt.LeftButton,pos=w.statements.visualItemRect(w.statements.item(0,0)).center())
        w.findChild(QLineEdit,'FinanceActor').setText(actor);QTest.mouseClick(w.findChild(QPushButton,name),Qt.LeftButton)
    assert a.open_project('P')['statement_workflow'][0]['status']=='ISSUED',w.status.text()
    assert len(a.statement_periods('P'))==3
    from PySide6.QtWidgets import QFileDialog
    target=tmp_path/'clicked-statement.pdf'
    monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,**kwargs:(str(target),'PDF'))
    qt.processEvents();QTest.mouseClick(w.statements.viewport(),Qt.LeftButton,pos=w.statements.visualItemRect(w.statements.item(0,0)).center())
    QTest.mouseClick(w.findChild(QPushButton,'StatementExport'),Qt.LeftButton)
    assert target.stat().st_size>100,w.status.text()
    w.close();a.store.close()


def test_workspace_exposes_real_statement_export_and_amendment(tmp_path):
    from app.financial_workspace import FinancialWorkspace
    a,docs,_,_=fixture(tmp_path);qt=QApplication.instance() or QApplication([]);w=FinancialWorkspace(a,'P')
    assert w.findChild(QPushButton,'StatementExport') is not None
    assert w.findChild(QPushButton,'StatementAmendment') is not None
    w.close();a.store.close()


def test_financial_workspace_process_exits_without_native_corruption(tmp_path):
    import subprocess,sys,os
    from test_phase3_statement_ledger_completion import posted,setup_workflow,issue
    a,docs,_,_=fixture(tmp_path);setup_workflow(a,docs);issue(a,'S-NATIVE','1');posted(a,'budget','B-NATIVE','1000');a.store.close()
    code=f'''from core.platform.application import StructuralProApp
from PySide6.QtWidgets import QApplication
from app.financial_workspace import FinancialWorkspace
qt=QApplication([])
a=StructuralProApp({str(tmp_path/'db')!r})
w=FinancialWorkspace(a,'P');w.show();qt.processEvents();w.grab().save({str(tmp_path/'native.png')!r});w.close();del w;qt.processEvents();a.store.close()
'''
    p=subprocess.run([sys.executable,'-X','faulthandler','-c',code],capture_output=True,text=True,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},timeout=30)
    assert p.returncode==0,p.stderr
