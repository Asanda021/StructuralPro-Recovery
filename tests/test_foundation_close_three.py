"""Synthetic detail schedules and native modal UI acceptance; no real design approval."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import re
import pytest
from PySide6.QtWidgets import QApplication
from test_foundation_tie_stage23_chat import sample
from core.platform.application import StructuralProApp
from core.takeoff.reviewed_structural import empty_member,preview_member
from core.takeoff.engine import TakeoffEngine

FAMILIES=['tie_beam','isolated_footing','strip_footing','mat_footing','pile_cap']

def starter():
 return {'status':'confirmed','source_ref':'دیتایل مصنوعی انتظار','approved_by':'بازبین مصنوعی','count_scope':'per_member','count_scope_ref':'برای هر شناژ مصنوعی','segments':[{'id':'انتظار-مستقل','position':'support','count':'6','nominal_diameter_mm':'16','shape_ref':'خم مستند مصنوعی','cut_length_m':'1.7','cut_length_ref':'طول برش صریح مصنوعی','unit_weight_kg_m':'1.58','unit_weight_source':'جدول وزن مصنوعی صریح','source_ref':'دیتایل مصنوعی مستقل انتظار','approved_by':'بازبین مصنوعی'}]}

def with_starters():
 d=sample();d['rebars']['starters']=starter();return d

def test_starter_exists_unknown_is_not_zero():
 d=empty_member('tie_beam','L1','T1');assert d['rebars']['starters']['status']=='unreviewed'
 d=sample();d['rebars'].pop('starters',None);assert not preview_member(d,TakeoffEngine())['ready']

@pytest.mark.parametrize('fault',['no_detail','no_weight_source','no_cut_ref','duplicate','bad_scope','missing_group'])
def test_starter_fail_closed(fault):
 d=with_starters();g=d['rebars']['starters'];p=g['segments'][0]
 if fault=='no_detail':p.pop('source_ref')
 if fault=='no_weight_source':p.pop('unit_weight_source')
 if fault=='no_cut_ref':p.pop('cut_length_ref')
 if fault=='duplicate':p['id']=d['rebars']['longitudinal']['segments'][0]['id']
 if fault=='bad_scope':g['count_scope']='assumed'
 if fault=='missing_group':d['rebars'].pop('starters')
 assert not preview_member(d,TakeoffEngine())['ready']

def test_starter_sqlite_amendment_boq_exact(tmp_path):
 app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');d=with_starters()
 r=preview_member(d,app.takeoff);assert r['ready'],r['blockers']
 assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['source_id'].endswith(':starters'))))==Decimal('32.232')
 app.save_structural_member_draft('P',d,expected_revision=0);app.commit_structural_member('P','tie_beam','L1','T1',expected_revision=1);original=deepcopy(app.open_project('P'))
 doc=tmp_path/'مدرک.txt';doc.write_text('مدرک کاملاً مصنوعی اصلاح انتظار')
 d['rebars']['starters']['segments'][0]['count']='8'
 a=app.create_foundation_amendment('P','tie_beam','L1','T1',d,expected_revision=1,created_by='سازنده',reason='تغییر دیتایل انتظار',evidence={'evidence_path':str(doc),'evidence_sha256':sha256(doc.read_bytes()).hexdigest(),'evidence_reference':'مدرک مصنوعی'})
 assert Decimal(str(next(v for k,v in a['delta'].items() if k.endswith(':starters'))))==Decimal('10.744')
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='مستقل',note='کنترل صریح')
 app.apply_beam_amendment('P',a['id'],expected_revision=1);app.store.close();app=StructuralProApp(tmp_path/'db')
 p=app.open_project('P');assert p['takeoffs']==original['takeoffs'];assert p['reviewed_structural_members']==original['reviewed_structural_members']
 r=app.preview_structural_member('P','tie_beam','L1','T1');q=next(v for v in r['rows'] if v['source_id'].endswith(':starters'));assert Decimal(str(q['quantity']))==Decimal('42.976')
 assert any(Decimal(str(row['quantity']))==Decimal('42.976') and any(str(v).endswith(':starters') for v in row['source_ids']) for row in p['boq'])
 app.store.close()

@pytest.mark.parametrize('kind',FAMILIES)
def test_report_all_titles_persian_with_history(tmp_path,kind):
 from openpyxl import load_workbook
 app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');d=sample(kind);app.save_structural_member_draft('P',d,expected_revision=0);app.commit_structural_member('P',kind,'L1','T1',expected_revision=1)
 doc=tmp_path/'مدرک.txt';doc.write_text('مدرک مصنوعی')
 d['geometry']['count']='3';a=app.create_foundation_amendment('P',kind,'L1','T1',d,expected_revision=1,created_by='سازنده',reason='اصلاح مصنوعی',evidence={'evidence_path':str(doc),'evidence_sha256':sha256(doc.read_bytes()).hexdigest(),'evidence_reference':'مرجع مصنوعی'})
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='مستقل',note='کنترل');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 path=tmp_path/'گزارش.xlsx';app.export_foundation_detail_report('P',kind,'L1','T1',path,format='xlsx');book=load_workbook(path)
 sheet=book['ریز متره'];header_row=next(i for i,row in enumerate(sheet,1) if any(c.value=='عنوان' for c in row))
 headers=[str(c.value) for c in sheet[header_row]];field=headers.index('عنوان');component=headers.index('جزء عضو')
 for row in list(sheet.rows)[header_row:]:
  for col in [field,component]:assert not re.search('[A-Za-z]',str(row[col].value).replace('T1','')),row[col].value
 assert 'متر' in [str(c.value) for row in sheet for c in row]
 app.export_foundation_detail_report('P',kind,'L1','T1',tmp_path/'گزارش.pdf',format='pdf');app.store.close()

@pytest.mark.parametrize('kind',FAMILIES)
def test_native_full_five_family_lifecycle(tmp_path,kind,nonblocking_error_dialogs,monkeypatch):
 from PySide6.QtWidgets import QApplication,QFileDialog,QDialog
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 from app.beam_component_editor import BeamComponentEditor,shown
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P');errors=[];clicked=[];outputs={}
 doc=tmp_path/'مدرک.txt';doc.write_text('مدرک کاملاً مصنوعی؛ بدون اعتبار نقشه واقعی')
 def click(button,name):
  QTest.mouseClick(button,Qt.LeftButton);_qt.processEvents();clicked.append(name)
 def fill_row(child,data):
  click(child.add_button,'افزودن جزء')
  i=child.table.currentRow()
  for j,(key,_) in enumerate(child.fields):
   if key in data:child.table.item(i,j).setText(str(shown(key,data[key])))
  child.reviewer.setText('بازبین مصنوعی ردیف');click(child.review_button,'بازبینی جزء')
 def schedule(callback):
  def run():
   child=_qt.activeModalWidget()
   try:callback(child)
   except Exception as exc:errors.append(repr(exc));child.reject()
  QTimer.singleShot(30,run)
 def edit_rows(child,rows,nested=None):
  assert isinstance(child,BeamComponentEditor)
  for data in rows:fill_row(child,data)
  original_id=child.collect(0)['id'];click(child.copy_button,'کپی جزء');assert child.collect(child.table.currentRow())['id']!=original_id
  click(child.delete_button,'حذف جزء');child.table.setCurrentCell(0,0)
  if nested:
   schedule(lambda grand:edit_rows(grand,nested));click(child.nested_button,'جزئیات تو در تو');child.table.setCurrentCell(0,0);child.reviewer.setText('بازبین مصنوعی ردیف');click(child.review_button,'بازبینی پس از تغییر جزء')
  if child.calculate_button.isEnabled():click(child.calculate_button,'محاسبه وزن');assert 'کیلوگرم' in child.total.text()
  click(child.save_button,'انتقال دیتایل')
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls
   for required in ['geometry_ref','source_id','group_approver','group_ref','group_reason','scope_ref','apply','add','remove']:assert required in c,required
   c['kind'].setCurrentIndex(c['kind'].findData(kind));c['id'].setText('T1');click(c['load'],'عضو جدید')
   c['specialist'].setChecked(True)
   assert not c['add'].isEnabled() and not c['remove'].isEnabled(),'دکمه میراثی نباید در قرارداد تخصصی عملیات بی‌اثر ارائه کند'
   assert not c['sections'].isEnabled(),'هندسه بدون قرارداد نباید قابل انتخاب باشد'
   d=sample(kind);g=d['geometry'];c['shape'].setCurrentIndex(c['shape'].findData('rectangular'))
   for key in ['length','width','depth','thickness','count']:
    if key in g:c['numeric'][key].setText(str(g[key]))
   c['building'].setText('B1');c['geometry_ref'].setText('هندسه مصنوعی');c['geometry_reviewer'].setText('بازبین هندسه مصنوعی');c['source_id'].setText('مصنوعی:'+kind);c['plan'].setText('نقشه مصنوعی');c['detail_ref'].setText('دیتایل مصنوعی');c['repeat_scope'].setCurrentIndex(c['repeat_scope'].findData('identical_members'));c['ded_scope'].setCurrentIndex(c['ded_scope'].findData('total_group'));c['ded_ref'].setText('کسورات مصنوعی')
   schedule(lambda child:edit_rows(child,[{'id':'کسر مستقل','volume_m3':'.1','source_ref':'کسر مصنوعی'}]));click(c['deductions'],'کسورات عضو')
   form={'id':'وجه مستقل','role':'side1','gross_area_m2':'2.4','contact':True,'source_ref':'وجه مصنوعی'}
   schedule(lambda child:edit_rows(child,[form],[{'id':'کسر سطح','area_m2':'.4','source_ref':'کسر سطح مصنوعی'}]));click(c['advanced'],'ویرایش وجه قالب')
   def confirm(status):
    c['status'].setCurrentIndex(c['status'].findData(status));c['group_approver'].setText('بازبین گروه مصنوعی');c['group_ref'].setText('مرجع گروه مصنوعی');c['group_reason'].setText('عدم کاربرد مستند مصنوعی');c['scope'].setCurrentIndex(c['scope'].findData('per_member'));c['scope_ref'].setText('برای هر عضو مصنوعی');click(c['apply'],'اعمال گروه')
   confirm('confirmed')
   primary='starters' if kind=='tie_beam' else 'bottom_x'
   for group in list(d['rebars']):
    c['group'].setCurrentIndex(c['group'].findData(group))
    if group==primary:
     bar=starter()['segments'][0]
     schedule(lambda child:edit_rows(child,[bar],[{'id':'مستقیم','kind':'straight','length_m':'1.5','source_ref':'جزء مستقیم مصنوعی'},{'id':'خم','kind':'bend','length_m':'.2','source_ref':'خم مصنوعی'}]));click(c['advanced'],'ویرایش میلگرد مستقل')
     confirm('confirmed')
    else:confirm('not_applicable')
   click(c['preview'],'پیش‌نمایش');click(c['review'],'بازبینی کل عضو');click(c['save'],'ذخیره')
   record=app.get_structural_member('P',kind,'L1','T1');assert record['revision']==1,nonblocking_error_dialogs
   click(c['load'],'بازگشایی');r=app.preview_structural_member('P',kind,'L1','T1');assert r['ready'],r['blockers'];assert Decimal(str(next(v['quantity'] for v in r['rows'] if v['unit']=='kg')))==Decimal('32.232')
   click(c['commit'],'ثبت قطعی');original=deepcopy(app.open_project('P'));assert len(original['boq'])==3
   c['numeric']['count'].setText('3');c['creator'].setText('سازنده اصلاحیه');c['reason'].setText('اصلاح تعداد مصنوعی');c['reviewer'].setText('بازبین مستقل اصلاحیه');c['note'].setText('کنترل صریح مصنوعی');c['evidence_path'].setText(str(doc));c['evidence_ref'].setText('مدرک مصنوعی جدید')
   for a in ['create','review','apply']:click(c['amend'][a],'اصلاحیه '+a)
   assert app.get_structural_member('P',kind,'L1','T1')['revision']==2,nonblocking_error_dialogs
   assert app.open_project('P')['takeoffs']==original['takeoffs']
   for fmt in ['xlsx','pdf']:
    path=tmp_path/('native_'+kind+'.'+fmt);monkeypatch.setattr(QFileDialog,'getSaveFileName',lambda *a,p=path,**kw:(str(p),''));click(c['reports'][fmt],'گزارش '+fmt);assert path.exists();outputs[fmt]=str(path)
   c['new_member'].setText('T2');c['new_source'].setText('کپی مصنوعی مستقل:'+kind);click(c['copy_member'],'کپی عضو');copied=app.get_structural_member('P',kind,'L1','T2');assert copied['revision']==1 and copied['status']=='draft';assert not app.preview_structural_member('P',kind,'L1','T2')['ready']
   click(c['delete_member'],'حذف پیش‌نویس');assert app.get_structural_member('P',kind,'L1','T2') is None
   assert not nonblocking_error_dialogs,nonblocking_error_dialogs
   import json
   (tmp_path/'native-clicks.json').write_text(json.dumps({'family':kind,'operations':clicked,'outputs':outputs,'synthetic':True},ensure_ascii=False,indent=2))
  except Exception as exc:errors.append(repr(exc))
  finally:dialog.reject()
 schedule(lambda _:run());open_manual_structural_editor(app,project_id='P',floor_id='L1');assert not errors,errors
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.get_structural_member('P',kind,'L1','T1')['revision']==2;app.store.close()


@pytest.mark.parametrize('kind',FAMILIES)
def test_native_reopen_units_and_clear_dimension(tmp_path,kind,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path);app.create_project('مصنوعی','P');d=sample(kind)
 d['geometry']['width']='30' if kind=='tie_beam' else '150';d['geometry']['variable_units']['width']='cm'
 app.save_structural_member_draft('P',d,expected_revision=0);before=deepcopy(app.preview_structural_member('P',kind,'L1','T1'));errors=[]
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls;c['kind'].setCurrentIndex(c['kind'].findData(kind));c['id'].setText('T1');QTest.mouseClick(c['load'],Qt.LeftButton)
   QTest.mouseClick(c['commit'],Qt.LeftButton);assert app.get_structural_member('P',kind,'L1','T1')['status']=='committed',nonblocking_error_dialogs
   assert app.preview_structural_member('P',kind,'L1','T1')['rows']==before['rows']
   c['numeric']['width'].clear();QTest.mouseClick(c['preview'],Qt.LeftButton)
   assert 'آماده ریزمتره' not in c['message'].text(),'بعد حذف بعد، عدد ذخیره‌شده نباید جایگزین ورودی خالی شود'
   assert not nonblocking_error_dialogs,nonblocking_error_dialogs
  except Exception as exc:errors.append(repr(exc))
  finally:dialog.reject()
 QTimer.singleShot(30,run);open_manual_structural_editor(app,project_id='P',floor_id='L1');assert not errors,errors;app.store.close()


def test_historical_applied_tie_stays_immutable_without_assumed_starters(tmp_path,monkeypatch):
 from core.takeoff.reviewed_structural import KINDS
 from core.takeoff.commit_guards import rebuild_project_boq
 old=KINDS['tie_beam'];app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی تاریخی','P')
 # Reproduce the exact pre-change group schema using real services, not fake rows.
 with monkeypatch.context() as historical:
  historical.setitem(KINDS,'tie_beam',(*old[:4],tuple(g for g in old[4] if g!='starters')))
  d=sample();app.save_structural_member_draft('P',d,expected_revision=0);app.commit_structural_member('P','tie_beam','L1','T1',expected_revision=1)
  doc=tmp_path/'مدرک.txt';doc.write_text('مصنوعی تاریخی');evidence={'evidence_path':str(doc),'evidence_sha256':sha256(doc.read_bytes()).hexdigest(),'evidence_reference':'مرجع تاریخی مصنوعی'}
  d['geometry']['count']='3';a=app.create_foundation_amendment('P','tie_beam','L1','T1',d,expected_revision=1,created_by='سازنده',reason='تاریخی',evidence=evidence);app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='مستقل',note='تاریخی');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 app.store.close();app=StructuralProApp(tmp_path/'db');before=deepcopy(app.open_project('P'))
 assert not app.preview_structural_member('P','tie_beam','L1','T1')['ready'],'دیتایل انتظار تاریخی نباید صفر فرض شود'
 _,boq=rebuild_project_boq(before,before['takeoffs']);assert boq==before['boq']
 p=deepcopy(before);p['metadata']['یادداشت']='ذخیره نامرتبط';app.store.save('P',p)
 with pytest.raises(ValueError):app.create_foundation_amendment('P','tie_beam','L1','T1',d,expected_revision=2,created_by='سازنده',reason='دیتایل ناقص',evidence=evidence)
 d['rebars']['starters']=starter();a=app.create_foundation_amendment('P','tie_beam','L1','T1',d,expected_revision=2,created_by='سازنده',reason='تکمیل صریح انتظار',evidence=evidence);app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='مستقل',note='تکمیل انتظار');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert app.preview_structural_member('P','tie_beam','L1','T1')['ready'];assert app.open_project('P')['takeoffs']==before['takeoffs'];assert 'starters' not in next(iter(before['reviewed_structural_members'].values()))['data']['rebars']
 app.store.close()

@pytest.mark.parametrize('kind',['tie_beam','isolated_footing'])
def test_native_edit_preview_revert_preserves_raw_units(tmp_path,kind,nonblocking_error_dialogs):
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.reviewed_structural_manual_editor import open_manual_structural_editor
 global _qt
 _qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path);app.create_project('مصنوعی','P');d=sample(kind);d['geometry']['width']='30';d['geometry']['variable_units']['width']='cm';app.save_structural_member_draft('P',d,expected_revision=0);errors=[]
 def run():
  dialog=_qt.activeModalWidget()
  try:
   c=dialog.column_controls;c['kind'].setCurrentIndex(c['kind'].findData(kind));c['id'].setText('T1');QTest.mouseClick(c['load'],Qt.LeftButton);shown=c['numeric']['width'].text()
   c['numeric']['width'].setText('0.4');QTest.mouseClick(c['preview'],Qt.LeftButton)
   c['numeric']['width'].setText(shown);QTest.mouseClick(c['preview'],Qt.LeftButton)
   assert c['state']['data']['geometry']['width']=='30';assert c['state']['data']['geometry']['variable_units']['width']=='cm'
   QTest.mouseClick(c['review'],Qt.LeftButton);QTest.mouseClick(c['save'],Qt.LeftButton);assert app.get_structural_member('P',kind,'L1','T1')['data']['geometry']['width']=='30';assert not nonblocking_error_dialogs,nonblocking_error_dialogs
  except Exception as exc:errors.append(repr(exc))
  finally:dialog.reject()
 QTimer.singleShot(30,run);open_manual_structural_editor(app,project_id='P',floor_id='L1');assert not errors,errors;app.store.close()


def test_reviewed_historical_missing_starter_cannot_newly_apply(tmp_path,monkeypatch):
 from core.takeoff.reviewed_structural import KINDS
 old=KINDS['tie_beam'];app=StructuralProApp(tmp_path);app.create_project('مصنوعی تاریخی','P')
 with monkeypatch.context() as historical:
  historical.setitem(KINDS,'tie_beam',(*old[:4],tuple(g for g in old[4] if g!='starters')))
  d=sample();app.save_structural_member_draft('P',d,expected_revision=0);app.commit_structural_member('P','tie_beam','L1','T1',expected_revision=1)
  doc=tmp_path/'مدرک.txt';doc.write_text('مصنوعی');d['geometry']['count']='3'
  a=app.create_foundation_amendment('P','tie_beam','L1','T1',d,expected_revision=1,created_by='سازنده',reason='قدیمی',evidence={'evidence_path':str(doc),'evidence_sha256':sha256(doc.read_bytes()).hexdigest(),'evidence_reference':'مصنوعی'});app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='مستقل',note='قدیمی')
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert app.open_project('P')==before
 # Also reject direct forged application through the transactional store boundary.
 p=deepcopy(before);p['beam_amendments'][a['id']].update(status='applied',applied_at='مصنوعی');p.setdefault('beam_amendment_applied',{})[a['beam_key']]=a['id']
 with pytest.raises(ValueError):app.store.save('P',p,manual_formula_command={'action':'beam_apply','id':a['id']})
 app.store.close()
