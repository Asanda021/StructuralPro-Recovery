"""Original revision control must compare two persisted snapshots, not itself."""
import pytest
from core.platform.application import StructuralProApp
import app.verified_search_navigation as navigation


_QT=None


@pytest.fixture(scope='module',autouse=True)
def keep_qt_application_alive():
    global _QT
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QCoreApplication,QEvent
    qt=QApplication.instance() or QApplication([])
    _QT=qt
    yield qt
    QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    qt.processEvents()


def project_with_two_versions(tmp_path):
    service=StructuralProApp(tmp_path/'db');service.create_project('Explicit revision fixture','P')
    for quantity,total in [('0.000000000000000001','10000000000000000000.00001'),('0.000000000000000002','10000000000000000000.00002')]:
        p=service.open_project('P');p['boq']=[{'id':'R1','description':'explicit fixture','quantity':quantity,'unit':'m3','total':total}]
        service.store.save('P',p,expected_digest=service.store.current_digest('P'))
    return service


def test_revision_view_uses_actual_previous_snapshot_and_exact_decimal_without_writes(tmp_path):
    service=project_with_two_versions(tmp_path);before=service.store.current_digest('P')
    try:
        assert hasattr(navigation,'stored_revision_history'), 'UI has no persisted two-snapshot handoff'
        result=navigation.stored_revision_history(service,'P')
        assert result['old_version']==2 and result['new_version']==3
        row=result['rows'][0]
        assert row['status']=='تغییریافته' and row['id']=='R1'
        assert row['old_quantity']=='0.000000000000000001'
        assert row['new_quantity']=='0.000000000000000002'
        assert row['quantity_delta']=='0.000000000000000001' and row['total_delta']=='0.00001'
        assert service.store.current_digest('P')==before
    finally:service.store.close()


@pytest.mark.parametrize('bad',['missing_project','only_one_snapshot','ambiguous_row','unit_change'])
def test_revision_view_refuses_missing_or_ambiguous_history_and_does_not_mix_units(tmp_path,bad):
    service=project_with_two_versions(tmp_path)
    try:
        if bad=='only_one_snapshot':service.create_project('Only one','Q')
        if bad in ('ambiguous_row','unit_change'):
            p=service.open_project('P')
            if bad=='ambiguous_row':p['boq'].append(dict(p['boq'][0]))
            else:p['boq'][0]['unit']='m2'
            service.store.save('P',p,expected_digest=service.store.current_digest('P'))
        before=service.store.current_digest('P')
        assert hasattr(navigation,'stored_revision_history'), 'UI has no verified snapshot handoff'
        if bad=='unit_change':
            result=navigation.stored_revision_history(service,'P');assert result['rows'][0]['quantity_delta']=='واحد ناسازگار'
        else:
            with pytest.raises(ValueError):navigation.stored_revision_history(service,{'missing_project':'missing','only_one_snapshot':'Q'}.get(bad,'P'))
        assert service.store.current_digest('P')==before
    finally:service.store.close()


def test_actual_revision_button_displays_prior_and_current_values(tmp_path):
    import os,subprocess,sys
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    code=r'''
import sys
from pathlib import Path
Path.home=classmethod(lambda cls:Path(sys.argv[1]))
from core.platform.application import StructuralProApp
s=StructuralProApp(Path(sys.argv[1])/'.structuralpro');s.create_project('Explicit history fixture','P')
for q in ['1','3']:
 p=s.open_project('P');p['boq']=[{'id':'R1','price_code':'TEST','quantity':q,'unit':'m3','total':q}]
 s.store.save('P',p,expected_digest=s.store.current_digest('P'))
before=s.store.current_digest('P');s.store.close()
from PySide6.QtWidgets import QApplication,QMainWindow,QPushButton,QTableWidget,QLineEdit
from PySide6.QtCore import QTimer
from app.main import main
original=QApplication.exec
def inspect(app):
 w=next(x for x in app.topLevelWidgets() if isinstance(x,QMainWindow))
 button=next(b for b in w.findChildren(QPushButton) if b.text()=='ساخت تاریخچه تغییرات از آخرین دو نسخه')
 panel=button.parentWidget();panel.findChild(QLineEdit).setText('P');button.click();app.processEvents()
 table=panel.findChild(QTableWidget)
 assert table.rowCount()==1
 assert table.item(0,2).text()=='1', 'history incorrectly compares the current snapshot with itself'
 assert table.item(0,3).text()=='3' and table.item(0,4).text()=='2'
 check=StructuralProApp(Path(sys.argv[1])/'.structuralpro');assert check.store.current_digest('P')==before;check.store.close()
 QTimer.singleShot(0,w.close);return original()
QApplication.exec=inspect
raise SystemExit(main())
'''
    result=subprocess.run([sys.executable,'-c',code,str(tmp_path)],cwd=root,env={**os.environ,'QT_QPA_PLATFORM':os.getenv('QT_QPA_PLATFORM','offscreen'),'STRUCTURALPRO_SMOKE':'0'},capture_output=True,text=True,timeout=90)
    assert result.returncode==0,result.stdout+result.stderr


def test_search_opens_exact_persisted_amendment_in_original_guarded_editor(tmp_path):
    from PySide6.QtWidgets import QApplication,QPlainTextEdit
    from test_manual_formula_amendments import base,proposal
    from app.project_search_panel import ProjectSearchDialog
    qt=QApplication.instance() or QApplication([]);service=base(tmp_path/'amendment-db')
    amendment=service.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='synthetic author',reason='Explicit revision search fixture')
    before=service.store.current_digest('P');opened=[]
    def navigate(route,pid,aid):
        opened.append(navigation.prepare_verified_amendment_view(service,pid,aid))
    search=ProjectSearchDialog(service,'P',initial_query=amendment['id'],on_navigate=navigate)
    try:
        assert len(search.results)==1, 'E4 does not index persisted amendment identities'
        search.list.setCurrentRow(0);assert search.open_record() is not None
        assert len(opened)==1
        view=opened[0];assert view._formula_selected=='A'
        assert view.formula_amend_id.text()==amendment['id']
        detail=view.findChild(QPlainTextEdit,'E4StoredAmendment')
        assert detail is not None and detail.isReadOnly() and amendment['id'] in detail.toPlainText()
        assert service.store.current_digest('P')==before
    finally:
        for view in opened:view.close()
        search.close();service.store.close();qt.processEvents()


def test_amendment_search_refuses_stale_selection_without_opening_form(tmp_path):
    from PySide6.QtWidgets import QApplication
    from test_manual_formula_amendments import base,proposal
    from app.project_search_panel import ProjectSearchDialog
    qt=QApplication.instance() or QApplication([]);service=base(tmp_path/'stale-db')
    amendment=service.create_manual_formula_amendment('P','A',proposal(),expected_revision=1,created_by='synthetic author',reason='Explicit stale revision fixture')
    search=ProjectSearchDialog(service,'P',initial_query=amendment['id'])
    try:
        assert len(search.results)==1, 'E4 does not index persisted amendment identities'
        search.list.setCurrentRow(0);service.add_project_floor('P','New version',level='F-new')
        before=service.store.current_digest('P')
        assert search.open_record() is None
        assert service.store.current_digest('P')==before
    finally:search.close();service.store.close();qt.processEvents()
