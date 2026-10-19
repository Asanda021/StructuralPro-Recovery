"""Real SQLite / QTest integration of existing nonfinancial contracts."""
from copy import deepcopy
from hashlib import sha256
import json
import importlib
import pytest
from core.platform.application import StructuralProApp

CASES = [
 ('test_column_joint_preflight_phase1','sample'),
 ('test_column_joint_beam_panel_phase1','case'),
 ('test_column_joint_bar_crosswalk_phase1','prepared'),
 ('test_column_joint_rebar_completion_phase1','setup'),
 ('test_column_joint_footing_tie_phase1','fixture'),
 ('test_column_joint_starter_development_phase1','setup'),
 ('test_column_joint_interface_surface_phase1','setup'),
 ('test_phase1_234_audits_20261019','material_setup'),
 ('test_phase1_multi_member_overlap','three'),
 ('test_phase1_five_domain_claims_20261019','setup'),
]

def scenario(tmp_path, case):
 module, name = case
 m=importlib.import_module(module)
 if name=='sample':
  p=m.sample_project(); d=m.sample_doc(p)
 elif module=='test_phase1_five_domain_claims_20261019':p,d=m.setup()
 else:p,d=getattr(m,name)(tmp_path)[:2]
 a=StructuralProApp(tmp_path/'db');a.create_project('پروژه مصنوعی','P')
 stored=a.open_project('P');stored.update(deepcopy(p));a.store.save('P',stored)
 file=tmp_path/'audit.json';file.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
 return a,d,file,sha256(file.read_bytes()).hexdigest()

@pytest.mark.parametrize('case',CASES)
def test_service_runs_existing_contract_on_actual_sqlite(tmp_path,case):
 a,d,p,h=scenario(tmp_path,case)
 try:
  before=a.open_project('P');token=a.store.current_digest('P')
  r=a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
  assert r['audit']['policy']==d['policy']
  assert r['rows']==[] and r['ready_for_boq'] is False and r['commit_allowed'] is False
  assert r['snapshot_digest']==token and r['source_sha256']==h
  assert a.open_project('P')==before
  p.write_text('{}')
  with pytest.raises(ValueError):a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 finally:a.store.close()

@pytest.mark.parametrize('case',CASES)
def test_real_aec_menu_file_click_and_contract_result(tmp_path,monkeypatch,case):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QFileDialog,QMessageBox
 from app.reviewed_aec_manual_editor import open_reviewed_aec_editor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 a,d,p,h=scenario(tmp_path,case);before=a.open_project('P');errors=[]
 monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *_:(str(p),''))
 monkeypatch.setattr(QMessageBox,'warning',lambda *_:None)
 def parent_click():
  parent=_qt.activeModalWidget()
  def child_click():
   child=_qt.activeModalWidget()
   try:
    c=child.handoff_controls
    assert child.layoutDirection()==Qt.RightToLeft
    QTest.mouseClick(c['load'],Qt.LeftButton);QTest.mouseClick(c['preview'],Qt.LeftButton)
    assert c['result'] is not None, c['message'].text()
    assert c['result']['audit']['policy']==d['policy']
    assert 'مسدود' in c['message'].text() and c['rows'].rowCount()==0
    assert c['details'].isReadOnly() and c['details'].toPlainText()
    # Replacing the evidence after a successful preview must clear that result.
    p.write_text('{}');QTest.mouseClick(c['preview'],Qt.LeftButton)
    assert c['result'] is None and not c['details'].toPlainText()
    assert 'خطا' in c['message'].text()
   except Exception as exc:errors.append(repr(exc))
   finally:child.reject()
  QTimer.singleShot(20,child_click)
  QTest.mouseClick(parent.structural_handoff_button,Qt.LeftButton);parent.reject()
 QTimer.singleShot(20,parent_click)
 open_reviewed_aec_editor(a,project_id='P',floor_id='L1')
 assert a.open_project('P')==before
 a.store.close();assert not errors,errors

@pytest.mark.parametrize('change',['snapshot','source'])
def test_concurrent_change_rejects_preview(tmp_path,monkeypatch,change):
 from core.takeoff import phase1_shared_materials_audit as engine
 a,d,p,h=scenario(tmp_path,CASES[7]);b=StructuralProApp(tmp_path/'db')
 real=engine.audit
 def concurrent(project,doc):
  out=real(project,doc)
  if change=='snapshot':
   current=b.open_project('P');current['metadata']['concurrent']='other connection';b.store.save('P',current)
  else:p.write_text('{}')
  return out
 monkeypatch.setattr(engine,'audit',concurrent)
 try:
  with pytest.raises((ValueError,RuntimeError)):
   a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
 finally:b.store.close();a.store.close()


def test_unknown_contract_never_dispatches_or_writes(tmp_path):
 a,d,p,h=scenario(tmp_path,CASES[0]);before=a.open_project('P');d['policy']='arbitrary.module'
 try:
  with pytest.raises(ValueError):a.preview_structural_handoff('P',d,source_path=p,source_sha256=h)
  assert a.open_project('P')==before
 finally:a.store.close()


def test_74_family_structure_preserves_scope_and_never_claims_acceptance():
 from pathlib import Path
 root=Path(__file__).resolve().parents[1]
 new=json.loads((root/'docs/acceptance/phase1_package1_74_family_evidence_20261019.json').read_text())
 old=json.loads((root/'docs/acceptance/phase1_85_family_evidence_refresh_20261018.json').read_text())
 assert {r['code'] for r in new['rows']}=={r['code'] for r in old['rows'] if r['primary_phase']==1}
 assert len(new['rows'])==74
 for row in new['rows']:
  assert row['fully_accepted'] is False and row['windows']=='pending_real_windows'
  assert all(k in row for k in ('contract','controller','real_form','sqlite','revision_cas','boq','report','qt','commit_test_evidence'))


def test_pile_unsaved_close_warns_and_cancel_preserves_input(tmp_path):
 from PySide6.QtCore import QTimer,Qt
 from PySide6.QtTest import QTest
 from PySide6.QtWidgets import QApplication,QMessageBox
 from app.bored_pile_detail_editor import open_bored_pile_editor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');errors=[];seen=[]
 def run():
  dlg=_qt.activeModalWidget();c=dlg.pile_controls
  try:
   c['group'].setFocus();QTest.keyClicks(c['group'],'UNSAVED')
   def answer(button):
    box=_qt.activeModalWidget()
    if isinstance(box,QMessageBox):
     seen.append(box.text());QTest.mouseClick(box.button(button),Qt.LeftButton)
   # Safety timeout closes the dialog if the warning is absent; the assertion still fails.
   QTimer.singleShot(20,lambda:answer(QMessageBox.No))
   QTest.mouseClick(c['close'],Qt.LeftButton)
   assert seen and dlg.isVisible() and c['group'].text()=='UNSAVED'
   QTimer.singleShot(20,lambda:answer(QMessageBox.Yes))
   QTest.mouseClick(c['close'],Qt.LeftButton)
   assert len(seen)==2
  except Exception as e:errors.append(repr(e));dlg.reject()
 QTimer.singleShot(20,run)
 open_bored_pile_editor(a,project_id='P',floor_id='FND')
 assert not a.open_project('P')['boq'];a.store.close();assert not errors,errors
