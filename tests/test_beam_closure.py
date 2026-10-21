from copy import deepcopy
from decimal import Decimal
import pytest
from PySide6.QtWidgets import QApplication
from core.platform.application import StructuralProApp
from test_beam_stage21 import specialist

def service(path):
 s=StructuralProApp(path);s.create_project('مصنوعی صریح','P');return s

def committed(s):
 d=specialist(2);s.save_beam_detail_draft('P',d,expected_revision=0);s.commit_beam_detail('P','L1','B1',expected_revision=1);return d

def test_formal_beam_amendment_keeps_original_and_effective_boq(tmp_path):
 s=service(tmp_path);d=committed(s);before=deepcopy(s.open_project('P'));d['geometry']['width']='.4';d['geometry']['source_ref']='D2 صریح'
 assert callable(getattr(s,'create_beam_amendment',None)),'گردش رسمی تیر قطعی موجود نیست'
 a=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='اصلاح عرض با دیتایل مستقل')
 assert Decimal(str(a['delta']['beam-detail:L1:B1:concrete']))==Decimal('.5')
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises(ValueError):s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='سازنده',note='خودبازبینی')
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='منبع و فرمول کنترل شد');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 p=s.open_project('P');assert p['takeoffs']==before['takeoffs'] and p['beam_detail_register']==before['beam_detail_register']
 assert Decimal(str(next(r['quantity'] for r in p['boq'] if r['item_code']=='beam')))==Decimal('2')
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 s.store.close();s=StructuralProApp(tmp_path);assert s.get_beam_detail('P','L1','B1')['revision']==2 and s.preview_beam_detail('P','L1','B1')['ready'];s.store.close()

def test_issued_financial_basis_and_tampering_are_blocked(tmp_path):
 s=service(tmp_path);d=committed(s);p=s.open_project('P');p['statement_periods']=[{'id':'issued','amount':'100.25'}];s.store.save('P',p);before=deepcopy(s.open_project('P'));d['geometry']['width']='.4'
 assert callable(getattr(s,'create_beam_amendment',None))
 a=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='پیشنهاد فقط');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل')
 with pytest.raises(ValueError):s.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert s.open_project('P')['boq']==before['boq'] and s.open_project('P')['statement_periods']==before['statement_periods']
 p=s.open_project('P');key=next(iter(p['beam_detail_register']));p['beam_detail_register'][key]['data']['geometry']['width']='.9'
 with pytest.raises(ValueError):s.store.save('P',p)
 s.store.close()

def test_native_series_and_surfaces_editors_exist_and_preserve_rows(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.beam_detail_panel import BeamDetailPanel
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=service(tmp_path);d=specialist();s.save_beam_detail_draft('P',d,expected_revision=0);panel=BeamDetailPanel(s,lambda:'P',lambda:None);panel.floor.setText('L1');panel.beam.setText('B1');panel.show();_qt.processEvents();QTest.mouseClick(panel.load_button,Qt.LeftButton);_qt.processEvents()
 assert hasattr(panel,'series_buttons'),'ویرایشگر چندسری به پنل تیر متصل نیست'
 assert all(k in panel.detail_buttons for k in ('sections','surfaces','intersections'))
 panel.close();panel.deleteLater();_qt.processEvents();s.store.close()

def test_native_multiseries_copy_delete_parts_and_surface_fields(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 rows=[{'id':'top16','position':'top','count':'2','nominal_diameter_mm':'16','shape_ref':'straight-D1','cut_length_m':'5','cut_length_ref':'fullcutD1','unit_weight_kg_m':'1.58','unit_weight_source':'catalog16','source_ref':'D1'}, {'id':'bottom20','position':'bottom','count':'3','nominal_diameter_mm':'20','shape_ref':'straight-D2','cut_length_m':'5.5','cut_length_ref':'fullcutD2','unit_weight_kg_m':'2.47','unit_weight_source':'catalog20','source_ref':'D2'}]
 d=BeamComponentEditor('series',rows);d.show();_qt.processEvents();d.table.setCurrentCell(0,0);d.reviewer.setText('بازبین');QTest.mouseClick(d.review_button,Qt.LeftButton);_qt.processEvents();assert d.table.rowCount()==2
 d.table.setCurrentCell(0,0);QTest.mouseClick(d.copy_button,Qt.LeftButton);_qt.processEvents();assert d.table.rowCount()==3
 ids=[d.table.item(i,0).text() for i in range(3)];assert len(set(ids))==3
 QTest.mouseClick(d.delete_button,Qt.LeftButton);_qt.processEvents();assert d.table.rowCount()==2
 QTest.mouseClick(d.save_button,Qt.LeftButton);_qt.processEvents();assert len(d.rows)==2 and {r['id'] for r in d.rows}=={'top16','bottom20'};d.close();d.deleteLater();_qt.processEvents()


def test_review_blocks_nan_incomplete_row(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([]);d=BeamComponentEditor('series',[{'id':'bad','source_ref':'D','count':'NaN'}]);d.show();_qt.processEvents();d.table.setCurrentCell(0,0);d.reviewer.setText('بازبین');QTest.mouseClick(d.review_button,Qt.LeftButton);_qt.processEvents()
 assert d.collect(0).get('review_status')!='confirmed','ردیف نامعتبر در فرم بازبینی‌شده اعلام شد';d.close();d.deleteLater();_qt.processEvents()

def _apply_worker(path,aid,event,queue):
 s=StructuralProApp(path);event.wait()
 try:s.apply_beam_amendment('P',aid,expected_revision=1);queue.put('APPLIED')
 except (ValueError,RuntimeError):queue.put('BLOCKED')
 finally:s.store.close()

def test_two_process_amendment_cas_and_multiple_series(tmp_path):
 import multiprocessing as mp,sqlite3
 s=service(tmp_path);d=committed(s);d['geometry']['width']='.4'
 a=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='دیتایل');s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.store.close();ctx=mp.get_context('spawn');event=ctx.Event();queue=ctx.Queue();ps=[ctx.Process(target=_apply_worker,args=(str(tmp_path),a['id'],event,queue)) for _ in range(2)]
 for p in ps:p.start()
 event.set();results=[queue.get(timeout=15) for p in ps]
 for p in ps:p.join(15);assert p.exitcode==0
 assert sorted(results)==['APPLIED','BLOCKED'];s=StructuralProApp(tmp_path);assert len(s.open_project('P')['takeoffs'])==3;s.store.close()
 for db in tmp_path.rglob('*.db'):
  with sqlite3.connect(db) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_reviewed_multiseries_sections_faces_and_export(tmp_path):
 from core.takeoff.beam_detail import component_fingerprint
 s=service(tmp_path);d=specialist();d['formwork'].pop('net_area_m2')
 def approve(row):
  row.update(review_status='confirmed',reviewed_by='بازبین',approved_by='بازبین');row['review_digest']=component_fingerprint(row);return row
 d['formwork']['surfaces']=[approve({'id':'bottom','role':'bottom_face','gross_area_m2':'1.5','contact':True,'source_ref':'F1'}),approve({'id':'side1','role':'side1','gross_area_m2':'2.5','contact':True,'source_ref':'F2','deductions':[approve({'id':'void','area_m2':'.1','source_ref':'opening'})]}),approve({'id':'side2','role':'side2','gross_area_m2':'2.5','contact':True,'source_ref':'F3'}),approve({'id':'end','role':'end','gross_area_m2':'.15','contact':False,'source_ref':'بدون قالب صریح'})]
 groups={}
 for kind,pos,diam,weight in [('longitudinal','top','16','1.58'),('additional','support','20','2.47'),('side_bars','side','12','.888'),('crossties','crosstie','8','.395')]:
  rows=[approve({'id':kind+str(i),'position':pos if i==0 else 'bottom','count':'2','nominal_diameter_mm':diam,'shape_ref':'D1','cut_length_m':'5','cut_length_ref':'تمام اجزای برش صریح','unit_weight_kg_m':weight,'unit_weight_source':'کاتالوگ صریح','source_ref':'D1'}) for i in range(2)]
  d['bars'][kind]={'status':'confirmed','approved_by':'بازبین','source_ref':'D1','count_scope':'per_member','count_scope_ref':'یک تیر','segments':rows}
 s.save_beam_detail_draft('P',d,expected_revision=0);r=s.preview_beam_detail('P','L1','B1');assert r['ready'],r['blockers'];q=next(v for v in r['rows'] if v['unit']=='m2');assert Decimal(str(q['quantity']))==Decimal('6.4') and Decimal(str(q['params']['gross_area_m2']))==Decimal('6.65')
 s.commit_beam_detail('P','L1','B1',expected_revision=1);s.export_beam_detail_report('P','L1','B1',tmp_path/'detail.xlsx',format='xlsx');s.export_beam_detail_report('P','L1','B1',tmp_path/'detail.pdf',format='pdf');s.store.close();s=StructuralProApp(tmp_path);assert len(s.get_beam_detail('P','L1','B1')['data']['bars']['longitudinal']['segments'])==2;s.store.close()

def test_store_guard_rejects_forged_delta(tmp_path):
 s=service(tmp_path);d=committed(s);d['geometry']['width']='.4';a=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='عرض')
 p=s.open_project('P');fake=deepcopy(a);fake['id']='BA-forged';fake['delta']['beam-detail:L1:B1:concrete']='999';p['beam_amendments'][fake['id']]=fake
 with pytest.raises(ValueError):s.store.save('P',p,manual_formula_command={'action':'beam_create','id':fake['id']})
 s.store.close()

def test_native_panel_series_faces_save_review_and_formal_correction(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.beam_detail_panel import BeamDetailPanel
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=service(tmp_path);d=specialist();s.save_beam_detail_draft('P',d,expected_revision=0);p=BeamDetailPanel(s,lambda:'P',lambda:None);p.floor.setText('L1');p.beam.setText('B1');p.show();_qt.processEvents();QTest.mouseClick(p.load_button,Qt.LeftButton);_qt.processEvents()
 def fill_series():
  dialog=_qt.activeModalWidget();assert isinstance(dialog,BeamComponentEditor)
  for ident,pos,diam,weight in [('top','top','16','1.58'),('bottom','bottom','20','2.47')]:
   dialog.add({'id':ident,'position':pos,'count':'2','nominal_diameter_mm':diam,'shape_ref':'straight','cut_length_m':'5','cut_length_ref':'محور برش صریح','unit_weight_kg_m':weight,'unit_weight_source':'کاتالوگ','source_ref':'D1'});dialog.reviewer.setText('بازبین');QTest.mouseClick(dialog.review_button,Qt.LeftButton)
  QTest.mouseClick(dialog.save_button,Qt.LeftButton)
 QTimer.singleShot(100,fill_series);QTest.mouseClick(p.series_buttons['longitudinal'],Qt.LeftButton);_qt.processEvents();p.bars['longitudinal']['status'].setCurrentIndex(p.bars['longitudinal']['status'].findData('confirmed'));p.bars['longitudinal']['source_ref'].setText('D1');p.bars['longitudinal']['count_scope_ref'].setText('یک تیر');p.bar_scopes['longitudinal'].setCurrentIndex(p.bar_scopes['longitudinal'].findData('per_member'))
 p.edit_reason.setText('دو سری مستقل');QTest.mouseClick(p.review_beam_button,Qt.LeftButton);_qt.processEvents();assert 'بتن ناخالص' in p.message.text() and 'بتن خالص' in p.message.text();QTest.mouseClick(p.save_button,Qt.LeftButton);_qt.processEvents()
 saved=s.get_beam_detail('P','L1','B1');assert 'segments' in saved['data']['bars']['longitudinal'],nonblocking_error_dialogs;assert len(saved['data']['bars']['longitudinal']['segments'])==2,nonblocking_error_dialogs
 assert s.preview_beam_detail('P','L1','B1')['ready'],nonblocking_error_dialogs
 s.commit_beam_detail('P','L1','B1',expected_revision=saved['revision']);QTest.mouseClick(p.load_button,Qt.LeftButton);_qt.processEvents();p.geometry['width'].setText('.4');p.beam_amend_creator.setText('سازنده');p.beam_amend_reviewer.setText('بازبین مستقل');p.beam_amend_note.setText('دیتایل و دلتا کنترل شد');p.edit_reason.setText('اصلاح رسمی عرض')
 for b in (p.amend_create_button,p.amend_review_button,p.amend_apply_button):QTest.mouseClick(b,Qt.LeftButton);_qt.processEvents()
 assert s.get_beam_detail('P','L1','B1')['revision']==saved['revision']+1,nonblocking_error_dialogs
 assert Decimal(str(next(r['quantity'] for r in s.open_project('P')['boq'] if r['item_code']=='beam')))==Decimal('1.0')
 p.grab().save(str(tmp_path/'beam-closure-qt.png'));p.close();p.deleteLater();_qt.processEvents();s.store.close()

def test_native_sections_surfaces_deductions_and_parts(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([])
 for kind,row in [('sections',{'id':'s1','start_m':'0','end_m':'5','width_m':'.3','depth_m':'.5','source_ref':'D1'}),('intersections',{'id':'joint','volume_m3':'.05','source_ref':'J1'}),('surfaces',{'id':'side','role':'side1','gross_area_m2':'2.5','contact':True,'source_ref':'F1'})]:
  d=BeamComponentEditor(kind,[row]);d.show();_qt.processEvents();d.reviewer.setText('بازبین');QTest.mouseClick(d.review_button,Qt.LeftButton);_qt.processEvents();QTest.mouseClick(d.save_button,Qt.LeftButton);_qt.processEvents();assert d.rows[0]['review_status']=='confirmed',nonblocking_error_dialogs;d.close();d.deleteLater();_qt.processEvents()
 d=BeamComponentEditor('series',[{'id':'bar','position':'top','count':'2','nominal_diameter_mm':'16','shape_ref':'D','cut_length_m':'5','cut_length_ref':'تمام اجزای صریح','unit_weight_kg_m':'1.58','unit_weight_source':'C','source_ref':'D'}]);d.show();_qt.processEvents()
 def parts():
  child=_qt.activeModalWidget();child.add({'id':'straight','kind':'straight','length_m':'4','source_ref':'D'});child.reviewer.setText('بازبین');QTest.mouseClick(child.review_button,Qt.LeftButton);child.add({'id':'hook','kind':'hook','length_m':'.3','source_ref':'D-hook'});QTest.mouseClick(child.review_button,Qt.LeftButton);QTest.mouseClick(child.save_button,Qt.LeftButton)
 QTimer.singleShot(100,parts);QTest.mouseClick(d.nested_button,Qt.LeftButton);_qt.processEvents();d.reviewer.setText('بازبین');QTest.mouseClick(d.review_button,Qt.LeftButton);_qt.processEvents();QTest.mouseClick(d.save_button,Qt.LeftButton);_qt.processEvents();assert len(d.rows[0]['length_parts_m'])==2 and 'cut_length_m' not in d.rows[0],nonblocking_error_dialogs;d.close();d.deleteLater();_qt.processEvents()

def test_native_series_independent_weight_and_total(tmp_path,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.beam_component_editor import BeamComponentEditor
 global _qt
 _qt=QApplication.instance() or QApplication([]);d=BeamComponentEditor('series',[{'id':'a','count':'2','cut_length_m':'5','unit_weight_kg_m':'1.58'},{'id':'b','count':'3','cut_length_m':'5.5','unit_weight_kg_m':'2.47'}]);d.show();_qt.processEvents()
 assert hasattr(d,'calculate_button'),'وزن مستقل سری‌ها در فرم دیده نمی‌شود'
 QTest.mouseClick(d.calculate_button,Qt.LeftButton);_qt.processEvents();assert d.table.item(0,len(d.fields)).text()=='15.8' and d.table.item(1,len(d.fields)).text()=='40.755';assert '56.555' in d.total.text();d.close();d.deleteLater();_qt.processEvents()


def test_amendment_series_delta_stale_proposal_and_removal(tmp_path):
 s=service(tmp_path);d=committed(s);original=deepcopy(s.open_project('P')['takeoffs'])
 d['bars']['longitudinal']={'status':'confirmed','approved_by':'بازبین','source_ref':'D1','count_scope':'per_member','count_scope_ref':'یک تیر','segments':[{'id':'top','position':'top','count':'2','nominal_diameter_mm':'16','shape_ref':'D1','cut_length_m':'5','cut_length_ref':'برش صریح','unit_weight_kg_m':'1.58','unit_weight_source':'کاتالوگ','source_ref':'D1'},{'id':'bottom','position':'bottom','count':'3','nominal_diameter_mm':'20','shape_ref':'D2','cut_length_m':'5.5','cut_length_ref':'برش صریح','unit_weight_kg_m':'2.47','unit_weight_source':'کاتالوگ','source_ref':'D2'}]}
 a=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='افزودن دو سری صریح');stale=s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='دیگری',reason='رقیب')
 s.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.review_beam_amendment('P',stale['id'],expected_revision=1,reviewer='بازبین',note='کنترل');s.apply_beam_amendment('P',a['id'],expected_revision=1)
 with pytest.raises((ValueError,RuntimeError)):s.apply_beam_amendment('P',stale['id'],expected_revision=1)
 p=s.open_project('P');assert p['takeoffs']==original
 assert Decimal(str(next(r['quantity'] for r in p['boq'] if r['item_code']=='rebar' and any(x.endswith(':longitudinal') for x in r['source_ids']))))==(Decimal('2')*Decimal('5')*Decimal('1.58')+Decimal('3')*Decimal('5.5')*Decimal('2.47'))*Decimal('2')
 d['bars']['longitudinal']['segments'].pop();b=s.create_beam_amendment('P','L1','B1',d,expected_revision=2,created_by='سازنده',reason='حذف نسخه‌دار سری مستقل');s.review_beam_amendment('P',b['id'],expected_revision=1,reviewer='بازبین',note='کنترل حذف');s.apply_beam_amendment('P',b['id'],expected_revision=1)
 assert s.open_project('P')['takeoffs']==original
 assert Decimal(str(next(r['quantity'] for r in s.open_project('P')['boq'] if r['item_code']=='rebar' and any(x.endswith(':longitudinal') for x in r['source_ids']))))==Decimal('31.6')
 s.store.close();s=StructuralProApp(tmp_path);assert s.get_beam_detail('P','L1','B1')['revision']==3;s.store.close()


def test_historical_missing_contract_requires_separate_migration(tmp_path):
 s=service(tmp_path);d=specialist();d.pop('measurement_policy');d['source'].pop('plan_ref');d['source'].pop('detail_ref');s.save_beam_detail_draft('P',d,expected_revision=0);s.commit_beam_detail('P','L1','B1',expected_revision=1);before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.create_beam_amendment('P','L1','B1',d,expected_revision=1,created_by='سازنده',reason='فاقد قرارداد معتبر')
 proposed=deepcopy(d);proposed['measurement_policy']='beam_specialist_v1';proposed['source'].update(plan_ref='مدرک جدید',detail_ref='دیتایل جدید')
 with pytest.raises(ValueError):s.create_beam_amendment('P','L1','B1',proposed,expected_revision=1,created_by='سازنده',reason='مهاجرت فاقد گردش مستقل')
 assert s.open_project('P')==before;s.store.close()
