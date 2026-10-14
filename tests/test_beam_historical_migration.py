from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import pytest
from core.platform.application import StructuralProApp
from test_beam_stage21 import specialist


def legacy_service(tmp_path,committed=True):
 s=StructuralProApp(tmp_path/'db');s.create_project('تاریخی مصنوعی','P');d=specialist(2);d.pop('measurement_policy');d['source'].pop('plan_ref');d['source'].pop('detail_ref');d['historical_annotation']={'متن':'حفظ کامل','schema':'unknown-original'}
 s.save_beam_detail_draft('P',d,expected_revision=0)
 if committed:s.commit_beam_detail('P','L1','B1',expected_revision=1)
 evidence=tmp_path/'engineer-input.txt';evidence.write_text('ورودی مصنوعی صریح مهندس: پلان و دیتایل تکمیلی، هیچ طراحی واقعی نیست.');e={'evidence_path':str(evidence),'evidence_sha256':sha256(evidence.read_bytes()).hexdigest(),'evidence_reference':'دیتایل تکمیلی مصنوعی D1'}
 proposal=deepcopy(d);proposal['measurement_policy']='beam_specialist_v1';proposal['source'].update(plan_ref='پلان تکمیلی صریح',detail_ref='دیتایل تکمیلی صریح')
 return s,d,proposal,e


def migrate(s,d,e):
 assert callable(getattr(s,'create_beam_migration',None)),'گردش مهاجرت تاریخی موجود نیست'
 return s.create_beam_migration('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='تکمیل صریح قرارداد تاریخی',**e)

@pytest.mark.parametrize('committed',[True,False])
def test_historical_migration_preserves_original_and_reopens(tmp_path,committed):
 s,d,proposal,e=legacy_service(tmp_path,committed);before=deepcopy(s.open_project('P'));a=migrate(s,proposal,e)
 assert a['migration']['from_policy'] is None and a['previous']['data']==d
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='سازنده',note='خودبازبینی')
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='مدرک و واحد کنترل شد');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 after=s.open_project('P');assert after['takeoffs']==before['takeoffs'];assert after['beam_amendments'][a['id']]['previous']==before['beam_detail_register'][a['beam_key']]
 if committed:assert after['beam_detail_register']==before['beam_detail_register']
 else:assert after['beam_detail_register'][a['beam_key']]['revision']==2 and after['boq']==before['boq']
 with pytest.raises((ValueError,RuntimeError)):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises((ValueError,RuntimeError)):migrate(s,proposal,e)
 s.store.close();s=StructuralProApp(tmp_path/'db');r=s.get_beam_detail('P','L1','B1');assert r['data']['historical_annotation']==d['historical_annotation'] and r['data']['measurement_policy']=='beam_specialist_v1' and s.preview_beam_detail('P','L1','B1')['ready']
 if not committed:s.commit_beam_detail('P','L1','B1',expected_revision=2)
 assert len(s.open_project('P')['takeoffs'])==3;s.export_beam_detail_report('P','L1','B1',tmp_path/'migrated.xlsx',format='xlsx');s.export_beam_detail_report('P','L1','B1',tmp_path/'migrated.pdf',format='pdf');s.store.close()

@pytest.mark.parametrize('mutate',[
 lambda d:d['geometry'].pop('variable_units'),
 lambda d:d['bars']['stirrups']['segments'][0].pop('cut_length_ref'),
 lambda d:d['bars']['stirrups']['segments'][0].pop('shape_ref'),
 lambda d:d['geometry']['variable_units'].update(width='m2'),
 lambda d:d['source'].update(source_id='nouveau'),
 lambda d:d['bars']['stirrups']['segments'][0].update(id='renamed-old-id'),
])
def test_incomplete_incompatible_or_identity_changed_migration_blocked(tmp_path,mutate):
 s,old,d,e=legacy_service(tmp_path);before=deepcopy(s.open_project('P'));mutate(d)
 assert callable(getattr(s,'create_beam_migration',None))
 with pytest.raises(ValueError):migrate(s,d,e)
 assert s.open_project('P')==before;s.store.close()


def test_migration_evidence_changed_and_issued_finance_blocked(tmp_path):
 s,old,d,e=legacy_service(tmp_path);a=migrate(s,d,e);Path(e['evidence_path']).write_text('تغییر بعد از ثبت')
 with pytest.raises(ValueError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مدرک کهنه')
 s.store.close()
 s,old,d,e=legacy_service(tmp_path/'second');p=s.open_project('P');p['statement_periods']=[{'id':'issued','amount':'1.25'}];s.store.save('P',p);a=migrate(s,d,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مدرک');before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert s.open_project('P')==before;s.store.close()


def test_native_migration_same_panel_review_apply(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtTest import QTest
 from PySide6.QtCore import Qt
 from app.beam_detail_panel import BeamDetailPanel
 global _qt
 _qt=QApplication.instance() or QApplication([]);s,old,d,e=legacy_service(tmp_path);p=BeamDetailPanel(s,lambda:'P',lambda:None);p.show();p.floor.setText('L1');p.beam.setText('B1');QTest.mouseClick(p.load_button,Qt.LeftButton);_qt.processEvents()
 assert hasattr(p,'migration_button'),'مهاجرت در پنل تیر مسیر عملیاتی ندارد'
 p.specialist_policy.setCurrentIndex(0);p.plan_ref.setText(d['source']['plan_ref']);p.detail_ref.setText(d['source']['detail_ref']);p.migration_evidence_path.setText(e['evidence_path']);p.migration_reference.setText(e['evidence_reference']);p.beam_amend_creator.setText('سازنده');p.beam_amend_reviewer.setText('بازبین مستقل');p.beam_amend_note.setText('مدرک مستقل کنترل شد');p.edit_reason.setText('مهاجرت صریح نسخه قدیمی')
 for b in (p.migration_button,p.amend_review_button,p.amend_apply_button):QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents()
 assert s.get_beam_detail('P','L1','B1')['data']['measurement_policy']=='beam_specialist_v1',nonblocking_error_dialogs
 assert s.get_beam_detail('P','L1','B1')['data']['historical_annotation']==old['historical_annotation'];p.grab().save(str(tmp_path/'migration-qt.png'));p.close();p.deleteLater();_qt.processEvents();s.store.close()


def test_compatibility_inventory_is_read_only(tmp_path):
 s,old,d,e=legacy_service(tmp_path);before=deepcopy(s.open_project('P'))
 assert callable(getattr(s,'inspect_beam_history',None)),'ماتریس سازگاری داده تاریخی موجود نیست'
 rows=s.inspect_beam_history('P');assert rows[0]['status']=='NEEDS_ENGINEER_INPUT' and rows[0]['revision']==1;assert s.open_project('P')==before
 s.store.close()


def test_migration_store_guard_does_not_bypass_changed_evidence(tmp_path):
 from core.takeoff.commit_guards import rebuild_project_boq
 s,old,d,e=legacy_service(tmp_path);a=migrate(s,d,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مدرک');p=s.open_project('P');Path(e['evidence_path']).write_text('تغییر پس از بازبینی');p['beam_amendments'][a['id']].update(status='applied',applied_at='2026-10-14T00:00:00Z');p['beam_amendment_applied']={a['beam_key']:a['id']};_,p['boq']=rebuild_project_boq(p,p['takeoffs'])
 with pytest.raises(ValueError):s.store.save('P',p,manual_formula_command={'action':'beam_apply','id':a['id']})
 s.store.close()


def _migration_apply_worker(path,aid,event,queue):
 s=StructuralProApp(path);event.wait()
 try:s.apply_beam_amendment('P',aid,expected_revision=1);queue.put('APPLIED')
 except (ValueError,RuntimeError):queue.put('BLOCKED')
 finally:s.store.close()

@pytest.mark.parametrize('committed',[True,False])
def test_migration_two_process_sqlite_cas(tmp_path,committed):
 import multiprocessing as mp,sqlite3
 s,old,d,e=legacy_service(tmp_path,committed);a=migrate(s,d,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.store.close();ctx=mp.get_context('spawn');event=ctx.Event();q=ctx.Queue();ps=[ctx.Process(target=_migration_apply_worker,args=(str(tmp_path/'db'),a['id'],event,q)) for _ in range(2)]
 for p in ps:p.start()
 event.set();results=[q.get(timeout=20) for p in ps]
 for p in ps:p.join(20);assert p.exitcode==0
 assert sorted(results)==['APPLIED','BLOCKED']
 s=StructuralProApp(tmp_path/'db');assert s.get_beam_detail('P','L1','B1')['revision']==2 and len(s.open_project('P')['takeoffs'])==(3 if committed else 0);s.store.close()
 for path in (tmp_path/'db').rglob('*.db'):
  with sqlite3.connect(path) as con:assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

@pytest.mark.parametrize('kind',['healthy','incomplete','incompatible'])
def test_three_legacy_shapes_explicit_completion_keeps_history(tmp_path,kind):
 s,old,d,e=legacy_service(tmp_path,False);p=s.open_project('P');key=next(iter(p['beam_detail_register']));legacy=deepcopy(old)
 if kind=='healthy':legacy['source'].update(plan_ref=d['source']['plan_ref'],detail_ref=d['source']['detail_ref'])
 if kind=='incomplete':legacy['geometry'].pop('variable_units');legacy['bars']['stirrups']['segments'][0].pop('shape_ref');legacy['bars']['stirrups']['segments'][0].pop('cut_length_ref')
 if kind=='incompatible':legacy['geometry']['variable_units']['width']='m2';legacy['geometry']['deduction_scope']='unknown-legacy'
 p['beam_detail_register'][key]['data']=legacy;s.store.save('P',p);a=migrate(s,d,e);assert a['previous']['data']==legacy
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='ورودی صریح و مدرک تکمیلی مستقل');s.apply_beam_amendment('P',a['id'],expected_revision=1);p=s.open_project('P');assert p['beam_detail_history'][-1]['previous']['data']==legacy;assert s.preview_beam_detail('P','L1','B1')['ready'];s.store.close()


def test_migration_snapshot_history_cannot_be_erased(tmp_path):
 s,old,d,e=legacy_service(tmp_path,False);a=migrate(s,d,e);s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مدرک');s.apply_beam_amendment('P',a['id'],expected_revision=1);p=s.open_project('P');p['beam_detail_history']=[]
 with pytest.raises(ValueError):s.store.save('P',p)
 s.store.close()


def test_migration_bad_hash_missing_document_and_duplicate_identity(tmp_path):
 s,old,d,e=legacy_service(tmp_path);before=deepcopy(s.open_project('P'))
 for evidence in ({**e,'evidence_sha256':'0'*64},{**e,'evidence_path':str(tmp_path/'missing.txt')}):
  with pytest.raises(ValueError):migrate(s,d,evidence)
 bad=deepcopy(d);bad['bars']['stirrups']['segments'][1]['id']=bad['bars']['stirrups']['segments'][0]['id']
 with pytest.raises(ValueError):migrate(s,bad,e)
 assert s.open_project('P')==before;s.store.close()


def test_unlinked_and_corrupt_legacy_are_reported_without_inventing_details(tmp_path):
 s,old,d,e=legacy_service(tmp_path,False);p=s.open_project('P');p['takeoffs']=[{'id':'raw','source_id':'raw-legacy','item':'beam','quantities':[]}];p['beam_detail_register']['corrupt']={'revision':None,'status':'draft','data':{'old_payload':'حفظ'}};s.store.save('P',p);before=deepcopy(s.open_project('P'));rows=s.inspect_beam_history('P');assert {'UNLINKED_LEGACY','INCOMPATIBLE'}<=set(r['status'] for r in rows);assert s.open_project('P')==before;s.store.close()


def test_migration_review_guard_requires_named_independent_reviewer(tmp_path):
 from core.takeoff.manual_formula_amendments import digest,beam_review_payload
 s,old,d,e=legacy_service(tmp_path);a=migrate(s,d,e);p=s.open_project('P');a=p['beam_amendments'][a['id']];a.update(status='reviewed',review={'reviewer':'','note':'','digest':digest(beam_review_payload(a))})
 with pytest.raises(ValueError):s.store.save('P',p,manual_formula_command={'action':'beam_review','id':a['id']})
 s.store.close()


def test_migration_never_accepts_unspecified_bar_shape(tmp_path):
 s,old,d,e=legacy_service(tmp_path);d['bars']['longitudinal']={'status':'confirmed','approved_by':'بازبین','source_ref':'D','count_scope':'per_member','count_scope_ref':'یک تیر','segments':[{'id':'new-explicit','position':'top','count':'2','nominal_diameter_mm':'16','cut_length_m':'5','cut_length_ref':'برش مستقل','unit_weight_kg_m':'1.58','unit_weight_source':'کاتالوگ','source_ref':'D'}]}
 with pytest.raises(ValueError):migrate(s,d,e)
 s.store.close()


def test_inventory_includes_generic_beam_alias_and_assembly(tmp_path):
 s,old,d,e=legacy_service(tmp_path,False);p=s.open_project('P');p['takeoffs']=[{'id':'raw','source_id':'raw-legacy','item':'beam_concrete','quantities':[]}];p['takeoff_assemblies']=[{'id':'old-assembly','source_id':'old-bundle','assembly_code':'concrete_beam','inputs':{'original':'حفظ'}}];s.store.save('P',p);rows=s.inspect_beam_history('P');assert {'raw-legacy','old-bundle'}<=set(r.get('source_id') for r in rows);s.store.close()
