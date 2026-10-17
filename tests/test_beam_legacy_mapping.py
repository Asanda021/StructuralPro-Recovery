from copy import deepcopy
from hashlib import sha256
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp
from core.takeoff.commit_guards import rebuild_project_boq


def fixture(path,assembly=False):
 s=StructuralProApp(path/'db');s.create_project('نگاشت مصنوعی صریح','P');p=s.open_project('P')
 def row(sid,code,unit,qty):return {'id':sid,'source_id':sid,'member_code':'old-unspecified','system':'old-floor','revision':1,'item':code,'domain':'building','params':{},'description':'شرح مبهم عمداً','provenance':{'mode':'manual','source_id':'old-bundle' if assembly else sid},'quantities':[{'code':code,'title':code,'unit':unit,'amount':qty,'price_code':None,'unit_price':None,'formula':'ورودی تاریخی صریح'}]}
 rows=[row('old-concrete','concrete' if assembly else 'beam','m3','1.25')]
 if assembly:
  rows.append(row('old-steel','reinforcement','kg','17.75'));p['takeoff_assemblies']=[{'id':'old-bundle','source_id':'old-bundle','revision':1,'assembly_code':'concrete_beam','component_source_ids':['old-concrete','old-steel'],'inputs':{'مدرک':'مصنوعی'}}]
 p['takeoffs'],p['boq']=rebuild_project_boq(p,rows);s.store.save('P',p);doc=path/'evidence.txt';doc.write_text('تخصیص صریح مصنوعی به تیر B1 در طبقه L1؛ طراحی واقعی نیست')
 target={'floor_id':'L1','beam_id':'B1','source_id':'engineer-physical-B1','plan_ref':'P1 صریح','detail_ref':'D1 صریح'};e={'evidence_path':str(doc),'evidence_sha256':sha256(doc.read_bytes()).hexdigest(),'evidence_reference':'مدرک تخصیص مستقل'}
 return s,[r['source_id'] for r in rows],target,e


def create(s,ids,target,e):
 assert callable(getattr(s,'create_beam_legacy_mapping',None)),'گردش نگاشت رسمی موجود نیست'
 return s.create_beam_legacy_mapping('P',source_ids=ids,target=target,created_by='سازنده',reason='تخصیص مستند بدون تغییر کمیت',**e)

@pytest.mark.parametrize('assembly',[False,True])
def test_mapping_original_and_boq_unchanged_reopen_and_report(tmp_path,assembly):
 s,ids,t,e=fixture(tmp_path,assembly);before=deepcopy(s.open_project('P'));a=create(s,ids,t,e)
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='سازنده',note='خودبازبینی')
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='تخصیص و مدارک کنترل شد');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 p=s.open_project('P');assert p['takeoffs']==before['takeoffs'] and p['boq']==before['boq'] and p.get('takeoff_assemblies')==before.get('takeoff_assemblies')
 assert not p.get('beam_detail_register'),'نگاشت حجم، دیتایل کامل تیر نساخت'
 with pytest.raises((ValueError,RuntimeError)):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):create(s,ids,t,e)
 s.store.close();s=StructuralProApp(tmp_path/'db');rows=s.inspect_beam_legacy_mapping('P');assert all(r['status']=='LINKED' for r in rows);assert all(r['needs_detail'] for r in rows)
 s.export_beam_legacy_mapping_report('P',tmp_path/'mapping.xlsx',format='xlsx');s.export_beam_legacy_mapping_report('P',tmp_path/'mapping.pdf',format='pdf');s.store.close()

@pytest.mark.parametrize('bad',['unit','unknown','duplicate','hash','target'])
def test_mapping_invalid_source_unit_document_target_blocked(tmp_path,bad):
 s,ids,t,e=fixture(tmp_path);p=s.open_project('P')
 if bad=='unit':p['takeoffs'][0]['quantities'][0]['unit']='kg';s.store.save('P',p)
 if bad=='unknown':p['takeoffs'][0]['quantities'][0]['amount']=None;s.store.save('P',p)
 if bad=='duplicate':p['takeoffs'].append(deepcopy(p['takeoffs'][0]));s.store.save('P',p)
 if bad=='hash':e['evidence_sha256']='0'*64
 if bad=='target':t['beam_id']=''
 before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):create(s,ids,t,e)
 assert s.open_project('P')==before;s.store.close()


def test_issued_finance_and_changed_evidence_apply_blocked(tmp_path):
 s,ids,t,e=fixture(tmp_path);p=s.open_project('P');p['statement_periods']=[{'id':'issued','amount':'5.25'}];s.store.save('P',p);a=create(s,ids,t,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert s.open_project('P')==before;s.store.close()
 s,ids,t,e=fixture(tmp_path/'second');a=create(s,ids,t,e);Path(e['evidence_path']).write_text('تغییر مدرک')
 with pytest.raises(ValueError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل')
 s.store.close()


def _worker(path,aid,event,queue):
 s=StructuralProApp(path);event.wait()
 try:s.apply_beam_amendment('P',aid,expected_revision=1);queue.put('APPLIED')
 except (ValueError,RuntimeError):queue.put('BLOCKED')
 finally:s.store.close()


def test_real_two_process_mapping_cas(tmp_path):
 import multiprocessing as mp,sqlite3
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.store.close();ctx=mp.get_context('spawn');event=ctx.Event();q=ctx.Queue();ps=[ctx.Process(target=_worker,args=(str(tmp_path/'db'),a['id'],event,q)) for _ in range(2)]
 for p in ps:p.start()
 event.set();results=[q.get(timeout=20) for p in ps]
 for p in ps:p.join(20);assert p.exitcode==0
 assert sorted(results)==['APPLIED','BLOCKED']
 for path in (tmp_path/'db').rglob('*.db'):
  with sqlite3.connect(path) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_explicit_competing_target_is_ambiguous_until_reviewed_application(tmp_path):
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);b=create(s,ids,{**t,'beam_id':'B2','source_id':'physical-B2'},e);assert s.inspect_beam_legacy_mapping('P')[0]['status']=='AMBIGUOUS'
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='تیر اول صریحاً انتخاب شد');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):s.review_beam_amendment('P',b['id'],expected_revision=1,reviewer='بازبین',note='منبع قبلاً تخصیص یافت')
 s.store.close()


def test_mapping_original_link_boq_and_future_duplicate_commit_protected(tmp_path):
 from test_beam_stage21 import specialist
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='تخصیص');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 for mutation in ('original','pointer','boq'):
  p=s.open_project('P')
  if mutation=='original':p['takeoffs'][0]['quantities'][0]['amount']='9'
  elif mutation=='pointer':p['beam_legacy_links']={}
  else:p['boq'][0]['quantity']='9'
  with pytest.raises(ValueError):s.store.save('P',p)
 d=specialist();d['source']['source_id']=t['source_id'];s.save_beam_detail_draft('P',d,expected_revision=0)
 with pytest.raises(ValueError):s.commit_beam_detail('P','L1','B1',expected_revision=1)
 s.store.close()


def test_native_mapping_in_existing_panel(tmp_path,monkeypatch,nonblocking_error_dialogs):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt
 from app.beam_detail_panel import BeamDetailPanel
 global _qt
 _qt=QApplication.instance() or QApplication([]);s,ids,t,e=fixture(tmp_path);p=BeamDetailPanel(s,lambda:'P',lambda:None);p.show();_qt.processEvents()
 assert hasattr(p,'legacy_mapping_button'),'گردش نگاشت در پنل موجود نیست'
 QTest.mouseClick(p.legacy_refresh_button,Qt.LeftButton);_qt.processEvents();assert p.legacy_rows.count()==1;p.legacy_rows.setCurrentIndex(0)
 p.floor.setText(t['floor_id']);p.beam.setText(t['beam_id']);p.legacy_target_source.setText(t['source_id']);p.plan_ref.setText(t['plan_ref']);p.detail_ref.setText(t['detail_ref']);p.migration_evidence_path.setText(e['evidence_path']);p.migration_reference.setText(e['evidence_reference']);p.beam_amend_creator.setText('سازنده');p.beam_amend_reviewer.setText('بازبین');p.beam_amend_note.setText('تخصیص صریح');p.edit_reason.setText('نگاشت مستند')
 for button in (p.legacy_mapping_button,p.amend_review_button,p.amend_apply_button):QTest.mouseClick(button,Qt.LeftButton);_qt.processEvents()
 assert s.inspect_beam_legacy_mapping('P')[0]['status']=='LINKED',nonblocking_error_dialogs
 from PySide6.QtWidgets import QFileDialog
 for fmt in ('xlsx','pdf'):
  destination=tmp_path/('native-mapping.'+fmt);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,filepath=str(destination):(filepath,''));QTest.mouseClick(p.legacy_report_buttons[fmt],Qt.LeftButton);_qt.processEvents();assert destination.exists(),nonblocking_error_dialogs
 p.grab().save(str(tmp_path/'legacy-mapping-qt.png'));p.close();p.deleteLater();_qt.processEvents();s.store.close()


def test_full_registered_link_and_partial_assembly_are_not_remapped(tmp_path):
 from test_beam_stage21 import specialist
 s=StructuralProApp(tmp_path/'registered');s.create_project('مصنوعی','P');d=specialist();s.save_beam_detail_draft('P',d,expected_revision=0);s.commit_beam_detail('P','L1','B1',expected_revision=1);rows=s.inspect_beam_legacy_mapping('P');assert rows and all(r['status']=='LINKED' for r in rows);assert all(not r['needs_detail'] for r in rows);s.store.close()
 s,ids,t,e=fixture(tmp_path/'assembly',True)
 with pytest.raises(ValueError):create(s,ids[:1],t,e)
 s.store.close()


def test_mapping_target_source_identity_cannot_be_reused_or_changed(tmp_path):
 from test_beam_stage21 import specialist
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 for floor,beam,source in [('L1','B2',t['source_id']),('L1','B1','wrong-other-source')]:
  d=specialist();d['floor_id']=floor;d['beam_id']=beam;d['source']['source_id']=source
  with pytest.raises(ValueError):s.save_beam_detail_draft('P',d,expected_revision=0)
 s.store.close()


def test_exact_report_text_and_formula_injection(tmp_path):
 from openpyxl import load_workbook
 import fitz
 s,ids,t,e=fixture(tmp_path);p=s.open_project('P');p['takeoffs'][0]['description']='=HYPERLINK("http://example.invalid")';p['takeoffs'][0]['quantities'][0]['amount']='12345678901234567890.1234567890123456789';p['takeoffs'],p['boq']=rebuild_project_boq(p,p['takeoffs']);s.store.save('P',p);a=create(s,ids,t,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 s.export_beam_legacy_mapping_report('P',tmp_path/'exact.xlsx',format='xlsx');w=load_workbook(tmp_path/'exact.xlsx');cells=[c for sh in w for row in sh for c in row];assert all(c.data_type!='f' for c in cells);assert any(str(c.value)=='12345678901234567890.1234567890123456789' for c in cells)
 s.export_beam_legacy_mapping_report('P',tmp_path/'exact.pdf',format='pdf')
 with fitz.open(tmp_path/'exact.pdf') as doc:assert len(doc)>0 and all(p.get_pixmap().width>0 for p in doc)
 s.store.close()


def test_reviewed_mapping_snapshot_change_and_store_forgery_blocked(tmp_path):
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);p=s.open_project('P');p['takeoffs'][0]['quantities'][0]['amount']='1.75';p['takeoffs'],p['boq']=rebuild_project_boq(p,p['takeoffs']);s.store.save('P',p)
 with pytest.raises(RuntimeError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مبنای کهنه')
 s.store.close()
 s,ids,t,e=fixture(tmp_path/'forge');a=create(s,ids,t,e);p=s.open_project('P');p['beam_legacy_links']={ids[0]:a['id']}
 with pytest.raises(ValueError):s.store.save('P',p)
 s.store.close()


def test_known_destination_quantity_requires_exact_consistency(tmp_path):
 from test_beam_stage21 import specialist
 s,ids,t,e=fixture(tmp_path);d=specialist();d['source']['source_id']=t['source_id'];s.save_beam_detail_draft('P',d,expected_revision=0)
 with pytest.raises(ValueError):create(s,ids,t,e)
 s.store.close()


def test_matching_destination_snapshot_and_independent_partial_detail(tmp_path):
 from test_beam_stage21 import specialist
 s,ids,t,e=fixture(tmp_path);d=specialist();d['geometry']['width']='.5';d['source']['source_id']=t['source_id'];s.save_beam_detail_draft('P',d,expected_revision=0);a=create(s,ids,t,e);assert a['mapping']['target_snapshot']['data']==d
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مقدار مقصد 1.25 کنترل شد');s.apply_beam_amendment('P',a['id'],expected_revision=1);assert len(s.open_project('P')['takeoffs'])==1;s.store.close()


def test_mapping_review_guard_cannot_self_review_with_whitespace(tmp_path):
 from core.takeoff.manual_formula_amendments import digest,beam_review_payload
 s,ids,t,e=fixture(tmp_path);a=create(s,ids,t,e);p=s.open_project('P');a=p['beam_amendments'][a['id']];a.update(status='reviewed',review={'reviewer':' سازنده ','note':'جعل استقلال','digest':digest(beam_review_payload(a))})
 with pytest.raises(ValueError):s.store.save('P',p,manual_formula_command={'action':'mapping_review','id':a['id']})
 s.store.close()
