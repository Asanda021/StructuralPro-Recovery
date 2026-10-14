from copy import deepcopy
from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from core.platform.application import StructuralProApp
from core.takeoff.reviewed_structural import preview_member
from core.takeoff.engine import TakeoffEngine


def column(count=2):
 def na():return {'status':'not_applicable','reason':'عدم کاربرد صریح در نمونه مصنوعی','source_ref':'D1','approved_by':'مهندس مصنوعی'}
 return {'kind':'column','member_id':'C1','floor_id':'L1','building_id':'B1','axis':'A-1','measurement_policy':'column_specialist_v1','source':{'mode':'manual','source_id':'column-P-L1-C1','plan_ref':'P1 مصنوعی','detail_ref':'D1 مصنوعی'},'geometry':{'shape':'rectangular','width':'.4','depth':'.5','height':'3','count':count,'variable_units':{'width':'m','depth':'m','height':'m','count':'عدد'},'repeat_scope':'identical_members','source_ref':'D1','approved_by':'مهندس مصنوعی','intersection_scope':'total_group','intersection_ref':'عدم کسر مستند','intersections':[]},'formwork':{'status':'confirmed','approved_by':'مهندس مصنوعی','source_ref':'D1','area_scope':'per_member','area_scope_ref':'هر ستون','surfaces':[{'id':'f1','role':'side1','gross_area_m2':'1.2','contact':True,'source_ref':'D1','approved_by':'مهندس مصنوعی'},{'id':'f2','role':'side2','gross_area_m2':'1.5','contact':True,'source_ref':'D1','approved_by':'مهندس مصنوعی'},{'id':'f3','role':'side3','gross_area_m2':'1.2','contact':False,'source_ref':'D1 عدم قالب وجه سوم','approved_by':'مهندس مصنوعی'},{'id':'f4','role':'side4','gross_area_m2':'1.5','contact':False,'source_ref':'D1 عدم قالب وجه چهارم','approved_by':'مهندس مصنوعی'}]},'rebars':{'longitudinal':{'status':'confirmed','approved_by':'مهندس مصنوعی','source_ref':'D1','count_scope':'per_member','count_scope_ref':'یک ستون','segments':[{'id':'L16','count':'4','nominal_diameter_mm':'16','shape_ref':'مستقیم D1','cut_length_m':'3.4','cut_length_ref':'محور شامل مهاری صریح','unit_weight_kg_m':'1.58','unit_weight_source':'کاتالوگ صریح','source_ref':'D1','approved_by':'مهندس مصنوعی'}]},'ties':na(),'crossties':na(),'starters':na()}}


def test_column_scope_and_exact_independent_reference():
 r=preview_member(column(),TakeoffEngine());assert r['ready'],r['blockers'];q={v['unit']:Decimal(str(v['quantity'])) for v in r['rows']};assert q['m3']==Decimal('1.2') and q['m2']==Decimal('5.4') and q['kg']==Decimal('42.976')


def detailed_column():
 d=column();d['geometry'].update(shape='reviewed_sections',sections=[{'id':'s1','start_m':'0','end_m':'1','width_m':'.4','depth_m':'.5','source_ref':'D1','approved_by':'مهندس'},{'id':'s2','start_m':'1','end_m':'3','width_m':'.3','depth_m':'.4','source_ref':'D2','approved_by':'مهندس'}]);d['geometry'].update(intersection_ref='کسور J1 کل گروه صریح',intersections=[{'id':'joint','volume_m3':'.02','source_ref':'J1','approved_by':'مهندس'}])
 d['rebars']['ties']={'status':'confirmed','approved_by':'مهندس','source_ref':'D1','count_scope':'per_member','count_scope_ref':'یک ستون','segments':[{'id':'tie1','name':'zone1','start_m':'0','end_m':'1','first_bar_m':'0','last_bar_m':'.9','spacing_m':'.15','count':'7','nominal_diameter_mm':'8','shape_ref':'مستطیل D1','cut_length_m':'1.1','cut_length_ref':'برش محور صریح','unit_weight_kg_m':'.395','unit_weight_source':'کاتالوگ','source_ref':'D1','approved_by':'مهندس'},{'id':'tie2','name':'zone2','start_m':'1','end_m':'3','first_bar_m':'1','last_bar_m':'3','spacing_m':'.2','count':'11','nominal_diameter_mm':'8','shape_ref':'مستطیل D2','cut_length_m':'1','cut_length_ref':'برش محور صریح','unit_weight_kg_m':'.395','unit_weight_source':'کاتالوگ','source_ref':'D2','approved_by':'مهندس'}]}
 for p in d['rebars']['ties']['segments']:p['shape_kind']='rectangular'
 return d

def test_column_sections_and_tie_zones_repeat_explicitly():
 d=detailed_column();r=preview_member(d,TakeoffEngine());assert r['ready'],r['blockers'];assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['unit']=='m3')))==Decimal('.86');assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['source_id'].endswith(':ties'))))==Decimal('14.773')

@pytest.mark.parametrize('mutate',[lambda d:d['geometry']['variable_units'].update(width='m2'),lambda d:d['geometry'].pop('repeat_scope'),lambda d:d['rebars']['longitudinal']['segments'][0].pop('nominal_diameter_mm'),lambda d:d['rebars']['longitudinal']['segments'][0].update(length_parts_m=[{'kind':'straight','length_m':'3','source_ref':'D'},{'kind':'lap','length_m':'.4'}])])
def test_column_invalid_contract_blocked(mutate):
 d=column();mutate(d);assert not preview_member(d,TakeoffEngine())['ready']


def test_column_amendment_immutable_and_boq(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('ستون مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);s.commit_structural_member('P','column','L1','C1',expected_revision=1);before=deepcopy(s.open_project('P'));d['geometry']['width']='.5'
 assert callable(getattr(s,'create_column_amendment',None))
 a=s.create_column_amendment('P','L1','C1',d,expected_revision=1,created_by='سازنده',reason='دیتایل جدید صریح');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='کنترل');s.apply_beam_amendment('P',a['id'],expected_revision=1);p=s.open_project('P');assert p['takeoffs']==before['takeoffs'] and p['reviewed_structural_members']==before['reviewed_structural_members'];assert Decimal(str(next(v['quantity'] for v in p['boq'] if v['unit']=='m3')))==Decimal('1.5');s.store.close()


def test_column_real_two_process_amendment_and_finance_gate(tmp_path):
 import multiprocessing as mp,sqlite3
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);s.commit_structural_member('P','column','L1','C1',expected_revision=1);d['geometry']['width']='.5';a=s.create_column_amendment('P','L1','C1',d,expected_revision=1,created_by='سازنده',reason='مرجع');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.store.close();ctx=mp.get_context('spawn');event=ctx.Event();q=ctx.Queue();ps=[ctx.Process(target=_column_apply,args=(str(tmp_path),a['id'],event,q)) for _ in range(2)]
 for p in ps:p.start()
 event.set();answers=[q.get(timeout=20) for p in ps]
 for p in ps:p.join(20);assert p.exitcode==0
 assert sorted(answers)==['APPLIED','BLOCKED'];s=StructuralProApp(tmp_path);assert s.get_structural_member('P','column','L1','C1')['revision']==2;p=s.open_project('P');p['statement_periods']=[{'id':'issued','amount':'100'}];s.store.save('P',p);d['geometry']['width']='.6';a=s.create_column_amendment('P','L1','C1',d,expected_revision=2,created_by='سازنده',reason='پیشنهاد');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل')
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 s.store.close()
 for path in tmp_path.rglob('*.db'):
  with sqlite3.connect(path) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def _column_apply(path,aid,event,q):
 s=StructuralProApp(path);event.wait()
 try:s.apply_beam_amendment('P',aid,expected_revision=1);q.put('APPLIED')
 except (ValueError,RuntimeError):q.put('BLOCKED')
 finally:s.store.close()


def test_column_report_and_existing_form_are_connected(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtWidgets import QApplication,QDialog
 from PySide6.QtCore import QTimer
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0)
 assert callable(getattr(s,'export_column_detail_report',None)),'گزارش ستون موجود نیست'
 s.export_column_detail_report('P','L1','C1',tmp_path/'column.xlsx',format='xlsx');s.export_column_detail_report('P','L1','C1',tmp_path/'column.pdf',format='pdf')
 seen=[]
 def check():
  dialog=_qt.activeModalWidget();seen.append(hasattr(dialog,'column_controls') and 'scroll' in dialog.column_controls);dialog.reject()
 QTimer.singleShot(100,check);open_manual_structural_editor(s,project_id='P',floor_id='L1');assert seen==[True],'فرم تخصصی ستون به فرم فعلی متصل نیست';s.store.close()


def test_native_column_edit_review_save_commit_correction_and_reports(tmp_path,monkeypatch,nonblocking_error_dialogs):
 from PySide6.QtWidgets import QApplication,QFileDialog
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path/'db');s.create_project('مصنوعی','P');s.save_structural_member_draft('P',column(),expected_revision=0);errors=[]
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls;c['id'].setText('C1');QTest.mouseClick(c['load'],Qt.LeftButton);_qt.processEvents();assert c['specialist'].isChecked();c['numeric']['width'].setText('.5');c['reason'].setText('دیتایل عرض صریح');QTest.mouseClick(c['review'],Qt.LeftButton);assert 'بتن ناخالص' in c['message'].text();QTest.mouseClick(c['save'],Qt.LeftButton);_qt.processEvents();assert s.get_structural_member('P','column','L1','C1')['revision']==2,nonblocking_error_dialogs
   QTest.mouseClick(c['commit'],Qt.LeftButton);_qt.processEvents();assert s.get_structural_member('P','column','L1','C1')['status']=='committed',nonblocking_error_dialogs
   c['numeric']['width'].setText('.6');c['reason'].setText('اصلاح رسمی');c['creator'].setText('سازنده');c['reviewer'].setText('بازبین مستقل');c['note'].setText('مدرک و دلتا کنترل شد')
   for action in ('create','review','apply'):QTest.mouseClick(c['amend'][action],Qt.LeftButton);_qt.processEvents()
   assert s.get_structural_member('P','column','L1','C1')['revision']==3,nonblocking_error_dialogs
   for fmt in ('xlsx','pdf'):
    dest=tmp_path/('native-column.'+fmt);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *args,path=str(dest):(path,''));QTest.mouseClick(c['reports'][fmt],Qt.LeftButton);assert dest.exists(),nonblocking_error_dialogs
   dialog.grab().save(str(tmp_path/'column-qt.png'))
  except Exception as e:errors.append(str(e))
  finally:dialog.reject()
 QTimer.singleShot(100,run);open_manual_structural_editor(s,project_id='P',floor_id='L1');assert not errors,errors;s.store.close()


def test_column_overlap_sources_and_direct_committed_mutation_blocked(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);s.commit_structural_member('P','column','L1','C1',expected_revision=1);p=s.open_project('P');p['reviewed_structural_members'][next(iter(p['reviewed_structural_members']))]['data']['geometry']['width']='9'
 with pytest.raises(ValueError):s.store.save('P',p)
 duplicate=deepcopy(d);duplicate['member_id']='C2'
 with pytest.raises(ValueError):s.save_structural_member_draft('P',duplicate,expected_revision=0)
 s.store.close()


def test_column_missing_count_never_creates_assumed_repetition():
 d=column();d['geometry'].pop('count');r=preview_member(d,TakeoffEngine());assert not r['ready'] and not r['rows'],'پیش‌نمایش نباید تعداد یک را حدس بزند'


def test_column_contract_cannot_be_deleted_from_saved_draft(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);d.pop('measurement_policy')
 with pytest.raises(ValueError):s.save_structural_member_draft('P',d,expected_revision=1)
 s.store.close()


def test_beam_amendment_cannot_switch_to_column_engine(tmp_path):
 from test_beam_closure import committed
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=committed(s);d.update(kind='column',member_id='C1');d['geometry'].update(shape='rectangular',height='3',intersections=[]);d['rebars']={k:{'status':'not_applicable','reason':'مرجع','approved_by':'مهندس','source_ref':'D'} for k in ('longitudinal','ties','crossties','starters')};d['formwork']={'status':'confirmed','source_ref':'D','approved_by':'مهندس','area_scope':'total_group','area_scope_ref':'مرجع','surfaces':[{'id':'x','net_area_m2':'1','source_ref':'D'}]}
 with pytest.raises(ValueError):s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='تغییر موتور غیرمجاز')
 s.store.close()


@pytest.mark.parametrize('fault',['spiral','boundary','duplicate','lap_missing_source'])
def test_column_tie_shape_exact_boundaries_and_independent_ids(fault):
 d=detailed_column()
 if fault=='spiral':d['rebars']['ties']['segments'][0]['shape_kind']='spiral'
 if fault=='boundary':d['rebars']['ties']['segments'][1]['start_m']='1.000000001'
 if fault=='duplicate':d['rebars']['ties']['segments'][1]['id']=d['rebars']['ties']['segments'][0]['id']
 if fault=='lap_missing_source':
  p=d['rebars']['longitudinal']['segments'][0];p.pop('cut_length_m');p['length_parts_m']=[{'kind':'straight','length_m':'3','source_ref':'D1'},{'kind':'lap','length_m':'.4'}]
 assert not preview_member(d,TakeoffEngine())['ready']


def test_column_tie_explicit_cut_parts_are_supported():
 d=detailed_column();p=d['rebars']['ties']['segments'][0];p.pop('cut_length_m');p['length_parts_m']=[{'kind':'straight','length_m':'1','source_ref':'D1'},{'kind':'hook','length_m':'.1','source_ref':'D1-hook'}];r=preview_member(d,TakeoffEngine());assert r['ready'],r['blockers'];assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['source_id'].endswith(':ties'))))==Decimal('14.773')


def test_column_missing_form_face_stays_incomplete():
 d=column();d['formwork']['surfaces']=[d['formwork']['surfaces'][0]];assert not preview_member(d,TakeoffEngine())['ready'],'وجوه نامعلوم نباید بدون دیتایل حذف شوند'


def test_native_column_multiseries_and_geometry_editors(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_structural_member_draft('P',column(),expected_revision=0);errors=[]
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls;c['id'].setText('C1');QTest.mouseClick(c['load'],Qt.LeftButton);c['group'].setCurrentIndex(c['group'].findData('longitudinal'))
   def add_series():
    child=_qt.activeModalWidget();assert isinstance(child,BeamComponentEditor);child.add({'id':'L20','position':'بالا','count':'2','nominal_diameter_mm':'20','shape_ref':'D2','cut_length_m':'3.3','cut_length_ref':'D2-cut','unit_weight_kg_m':'2.47','unit_weight_source':'کاتالوگ D2','source_ref':'D2'});child.reviewer.setText('مهندس مصنوعی');QTest.mouseClick(child.review_button,Qt.LeftButton);QTest.mouseClick(child.save_button,Qt.LeftButton)
   QTimer.singleShot(100,add_series);QTest.mouseClick(c['advanced'],Qt.LeftButton);_qt.processEvents();QTest.mouseClick(c['review'],Qt.LeftButton);QTest.mouseClick(c['save'],Qt.LeftButton);_qt.processEvents();saved=s.get_structural_member('P','column','L1','C1');assert len(saved['data']['rebars']['longitudinal']['segments'])==2,nonblocking_error_dialogs;assert saved['revision']==2
  except Exception as e:errors.append(str(e))
  finally:dialog.reject()
 QTimer.singleShot(100,run);open_manual_structural_editor(s,project_id='P',floor_id='L1');assert not errors,errors;s.store.close()


def test_column_negative_dimensions_cannot_cancel_each_other():
 d=column();d['geometry'].update(width='-.4',depth='-.5');assert not preview_member(d,TakeoffEngine())['ready']


def test_column_fresh_review_cannot_reassign_physical_identity(tmp_path):
 from core.takeoff.manual_formula_amendments import digest
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);d['source']['source_id']='different-physical-source';d['building_id']='different-building';d['component_review']={'digest':digest(d),'reviewer':'بازبین','base_revision':1}
 with pytest.raises(ValueError):s.save_structural_member_draft('P',d,expected_revision=1)
 s.store.close()


def test_column_and_beam_connection_cannot_be_deducted_twice(tmp_path):
 from test_beam_stage21 import specialist
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');b=specialist();b['geometry'].pop('deductions_m3',None);b['geometry']['intersections']=[{'id':'shared-J1','volume_m3':'.02','source_ref':'نقطه مشترک','approved_by':'مهندس'}];s.save_beam_detail_draft('P',b,expected_revision=0);s.commit_beam_detail('P','L1','B1',expected_revision=1);d=column();d['geometry']['intersections']=[{'id':'shared-J1','volume_m3':'.02','source_ref':'همان اتصال','approved_by':'مهندس'}];s.save_structural_member_draft('P',d,expected_revision=0)
 with pytest.raises(ValueError):s.commit_structural_member('P','column','L1','C1',expected_revision=1)
 s.store.close()


def test_three_column_scenarios_sqlite_and_report_recovery(tmp_path):
 cases=[column(),detailed_column(),detailed_column()]
 for i,d in enumerate(cases):
  path=tmp_path/str(i);s=StructuralProApp(path);s.create_project('سناریوی مصنوعی','P');s.save_structural_member_draft('P',d,expected_revision=0);s.commit_structural_member('P','column','L1','C1',expected_revision=1)
  if i==2:
   d['geometry']['sections'][1]['width_m']='.4';d['geometry']['sections'][1]['source_ref']='D3';a=s.create_column_amendment('P','L1','C1',d,expected_revision=1,created_by='سازنده',reason='مقطع دوم با دیتایل صریح جدید');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='مقطع و کسر اتصال کنترل شد');s.apply_beam_amendment('P',a['id'],expected_revision=1)
  s.export_column_detail_report('P','L1','C1',path/'column.xlsx',format='xlsx');s.export_column_detail_report('P','L1','C1',path/'column.pdf',format='pdf');s.store.close();s=StructuralProApp(path);r=s.preview_structural_member('P','column','L1','C1');assert r['ready'];assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['unit']=='m3')))==[Decimal('1.2'),Decimal('.86'),Decimal('1.02')][i];s.store.close()


def test_column_correction_type_and_draft_history_are_guarded(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);s.save_structural_member_draft('P',d,expected_revision=1);p=s.open_project('P');p['structural_member_history']=[]
 with pytest.raises(ValueError):s.store.save('P',p)
 s.commit_structural_member('P','column','L1','C1',expected_revision=2);d['geometry']['width']='.5';a=s.create_column_amendment('P','L1','C1',d,expected_revision=2,created_by='سازنده',reason='مدرک جدید');p=s.open_project('P');fake=deepcopy(a);fake['id']='BA-fake-column';fake.pop('kind');p['beam_amendments'][fake['id']]=fake
 with pytest.raises(ValueError):s.store.save('P',p,manual_formula_command={'action':'beam_create','id':fake['id']})
 s.store.close()


def test_column_native_edit_preserves_drawing_provenance(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from hashlib import sha256
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path/'db');s.create_project('مصنوعی','P');doc=tmp_path/'synthetic-source.txt';doc.write_text('مدرک مصنوعی ورودی صریح؛ نقشه واقعی نیست');d=column();d['source'].update(mode='drawing',drawing_path=str(doc),sha256=sha256(doc.read_bytes()).hexdigest(),page=1,selected_region=[0,0,1,1]);s.save_structural_member_draft('P',d,expected_revision=0);errors=[]
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls;c['id'].setText('C1');QTest.mouseClick(c['load'],Qt.LeftButton);QTest.mouseClick(c['review'],Qt.LeftButton);QTest.mouseClick(c['save'],Qt.LeftButton);_qt.processEvents();assert s.get_structural_member('P','column','L1','C1')['data']['source']==d['source'],nonblocking_error_dialogs
  except Exception as e:errors.append(str(e))
  finally:dialog.reject()
 QTimer.singleShot(100,run);open_manual_structural_editor(s,project_id='P',floor_id='L1');assert not errors,errors;s.store.close()


def test_column_amendment_does_not_break_existing_beam_report(tmp_path):
 from test_beam_stage21 import specialist
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=column();s.save_structural_member_draft('P',d,expected_revision=0);s.commit_structural_member('P','column','L1','C1',expected_revision=1);d['geometry']['width']='.5';a=s.create_column_amendment('P','L1','C1',d,expected_revision=1,created_by='سازنده',reason='مدرک');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.apply_beam_amendment('P',a['id'],expected_revision=1);s.save_beam_detail_draft('P',specialist(),expected_revision=0)
 for fmt in ('xlsx','pdf'):s.export_beam_detail_report('P','L1','B1',tmp_path/('beam.'+fmt),format=fmt)
 s.store.close()


def test_column_unknown_rebar_group_is_not_silently_omitted():
 d=column();d['rebars']['unknown_extra']=deepcopy(d['rebars']['longitudinal']);assert not preview_member(d,TakeoffEngine())['ready']
