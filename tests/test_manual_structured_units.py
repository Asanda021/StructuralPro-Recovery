from copy import deepcopy
from decimal import Decimal
import pytest
from core.platform.application import StructuralProApp
from core.takeoff.formulas import evaluate_rows
from test_manual_formula_persistence import data

POLICY='dimensional_decimal_v1'
def typed(**kw):
 d=data(variable_units={'length':'m','width':'m','height':'m'},unit_policy=POLICY)
 d.update(kw);return d

def legacy(s,key):
 # Exact historical v1 wire fixture, no inferred units or automatic approval.
 from core.takeoff.manual_formula_register import POLICY as OLD_POLICY
 d=data();d.pop('variable_units');d.pop('unit_policy');p=s.open_project('P')
 p['manual_formula_register']={key:{'data':d,'revision':1,'status':'draft','numeric_policy':OLD_POLICY,'quantity':6}}
 s.store.save('P',p)

def test_exact_scaled_area_volume_and_speed():
 rows={'A':{'expression':'a*b','variables':{'a':'12345678901234567890.123456789','b':'10'},'variable_units':{'a':'mm','b':'cm'},'unit_policy':POLICY,'unit':'m2'},
       'B':{'expression':'base*h','references':{'base':'A'},'variables':{'h':'20'},'variable_units':{'h':'cm'},'unit_policy':POLICY,'unit':'m3'},
       'S':{'expression':'distance/time','variables':{'distance':'120','time':'2'},'variable_units':{'distance':'m','time':'min'},'unit_policy':POLICY,'unit':'m/s'}}
 out=evaluate_rows(rows)
 assert Decimal(str(out['A']))==Decimal('1234567890123456.7890123456789')
 assert Decimal(str(out['B']))==Decimal('246913578024691.35780246913578')
 assert out['S']==1

@pytest.mark.parametrize('bad',[
 {'variable_units':{'length':'m','width':'m'}},
 {'variable_units':{'length':'m','width':'m2','height':'m'}},
 {'expression':'length+width','unit':'m','variable_units':{'length':'m','width':'m2','height':'m'}},
 {'expression':'length**width','unit':'m','variable_units':{'length':'m','width':'m','height':'m'}},
 {'unit':'m2'}, {'variables':{'length':'NaN','width':'1','height':'1'}},
 {'variable_units':{'length':'unknown','width':'m','height':'m'}},
 {'expression':'length/0','unit':'m'}, {'expression':'length**0.5','unit':'m'},
 {'expression':'length*0','unit':'m2'},
])
def test_invalid_typed_formula_atomic(tmp_path,bad):
 s=StructuralProApp(tmp_path);s.create_project('صریح مصنوعی','P')
 with pytest.raises(ValueError):s.save_manual_formula('P','A',typed(**bad),expected_revision=0,reason='ورودی نامعتبر')
 assert not s.open_project('P').get('manual_formula_register');s.store.close()

def test_typed_sqlite_dependency_copy_review_freeze(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('صریح مصنوعی','P')
 s.save_manual_formula('P','A',typed(variables={'length':'1000','width':'20','height':'3'},variable_units={'length':'mm','width':'cm','height':'m'}),expected_revision=0,reason='ثبت دقیق')
 s.save_manual_formula('P','B',typed(member='C2',source_id='sB',expression='base*factor',variables={'factor':'2'},variable_units={'factor':'1'},references={'base':'A'}),expected_revision=0,reason='وابسته')
 assert Decimal(str(s.load_manual_formulas('P')['B']['quantity']))==Decimal('1.2')
 d=deepcopy(s.load_manual_formulas('P')['A']['data']);d['variables']['length']='100';d['variable_units']['length']='cm'
 s.save_manual_formula('P','A',d,expected_revision=1,reason='تبدیل واحد صریح معادل')
 assert s.load_manual_formulas('P')['B']['revision']==2
 mapping=s.copy_manual_formulas('P',['A','B'],floor='دوم',expected_revisions={'A':2,'B':2},reason='کپی واحددار')
 s.store.close();s=StructuralProApp(tmp_path);reg=s.load_manual_formulas('P')
 assert reg[mapping['A']]['data']['variable_units']==d['variable_units']
 s.review_manual_formula('P','A',expected_revision=2,reviewer='بازبین',note='واحد کنترل شد');s.commit_manual_formula('P','A',expected_revision=2)
 before=deepcopy(s.open_project('P'))
 d['variable_units']['length']='mm'
 with pytest.raises(ValueError):s.save_manual_formula('P','A',d,expected_revision=2,reason='قطعی غیرمجاز')
 assert s.open_project('P')==before
 assert Decimal(str(before['boq'][0]['quantity']))==Decimal('.6');s.store.close()

def test_strict_dependency_does_not_guess_legacy_unit(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');legacy(s,'old')
 before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.save_manual_formula('P','B',typed(member='C2',source_id='B',expression='base',variables={},variable_units={},references={'base':'old'}),expected_revision=0,reason='مرجع بدون قرارداد ابعادی')
 assert s.open_project('P')==before;s.store.close()

def test_typed_exports_units_and_scaled_excel_not_live(tmp_path):
 from openpyxl import load_workbook
 import fitz
 s=StructuralProApp(tmp_path/'db');s.create_project('مصنوعی','P')
 s.save_manual_formula('P','A',typed(variables={'length':'1000','width':'200','height':'3000'},variable_units={'length':'mm','width':'mm','height':'mm'},title='=HYPERLINK("x")'),expected_revision=0,reason='ثبت')
 s.export_manual_formula_report('P',tmp_path/'units.xlsx',format='xlsx');w=load_workbook(tmp_path/'units.xlsx')
 assert w['ورودی‌ها']['E1'].value=='واحد ساختاریافته'
 assert w['ورودی‌ها']['E2'].value=='میلی‌متر'
 assert w['محاسبه امن']['C2'].data_type=='s' and Decimal(w['محاسبه امن']['C2'].value)==Decimal('.6')
 assert any(c.value=='=HYPERLINK("x")' and c.data_type=='s' for row in w['ریز متره'] for c in row)
 s.export_manual_formula_report('P',tmp_path/'units.pdf',format='pdf')
 with fitz.open(tmp_path/'units.pdf') as doc:
  assert len(doc)>0
  assert all(page.get_pixmap().width>0 for page in doc)
 s.store.close()

def test_typed_deductions_bulk_units_and_undo(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',typed(),expected_revision=0,reason='ثبت')
 s.set_manual_formula_deduction('P','A',{'id':'explicit:void','source_id':'explicit:void','variable':'void','quantity':'.5','unit':'m3','basis':'حجم صریح مصنوعی'},expected_revision=1,reason='کسر')
 assert s.manual_formula_deduction_summary('P','A')=={'gross':6,'net':5.5,'deducted':.5,'unit':'m3'}
 s.bulk_edit_manual_formulas('P',['A'],changes={'variables':{'length':'1000'},'variable_units':{'length':'mm'}},expected_revisions={'A':2},reason='تغییر صریح مقدار و واحد')
 assert Decimal(str(s.load_manual_formulas('P')['A']['quantity']))==Decimal('.1')
 s.undo_manual_formulas('P');assert s.load_manual_formulas('P')['A']['data']['variable_units']['length']=='m'
 s.redo_manual_formulas('P');assert s.load_manual_formulas('P')['A']['data']['variable_units']['length']=='mm'
 s.store.close()

def test_native_custom_unit_selector_save_reopen_and_incompatible_edit(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.manual_takeoff import ManualTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 assert hasattr(d,'dynamic_units'),'انتخاب واحد ساختاریافته پارامترها وجود ندارد'
 d.formula_family.setCurrentIndex(d.formula_family.findData('column'));d.formula_id.setText('typed');d.formula_source.setText('manual:typed');d.formula_member.setText('C1');d.formula_title.setText('صریح مصنوعی');d.floor_id.setText('اول');d.formula_unit.setCurrentIndex(d.formula_unit.findData('m2'));d.formula_expression.setText('x*y');d.formula_variables.setPlainText('x=1000\ny=20');d.formula_basis.setText('هندسه مصنوعی صریح');d.formula_reason.setText('ثبت');_qt.processEvents()
 for key,unit in [('x','mm'),('y','cm')]:
  combo=d.dynamic_units[key];d.formula_scroll.ensureWidgetVisible(combo);combo.setFocus();QTest.keyClick(combo,Qt.Key_Home)
  for _ in range(combo.findData(unit)):QTest.keyClick(combo,Qt.Key_Down)
  QTest.keyClick(combo,Qt.Key_Enter)
 QTest.mouseClick(d.formula_save_button,Qt.LeftButton);_qt.processEvents();row=s.load_manual_formulas('P')['typed'];assert row['quantity']==.2 and row['data']['variable_units']=={'x':'mm','y':'cm'}
 d.table.setCurrentCell(0,0);QTest.mouseClick(d.formula_load_button,Qt.LeftButton);_qt.processEvents();assert d.dynamic_units['x'].currentData()=='mm'
 combo=d.dynamic_units['y'];combo.setCurrentIndex(combo.findData('m2'));d.formula_reason.setText('نامعتبر');QTest.mouseClick(d.formula_save_button,Qt.LeftButton);_qt.processEvents()
 assert s.load_manual_formulas('P')['typed']['revision']==1 and 'ناسازگار' in d.status.text()
 d.grab().save(str(tmp_path/'units-form.png'));d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_native_new_contract_requires_explicit_units_and_legacy_review_blocked(tmp_path):
 from PySide6.QtWidgets import QApplication
 from PySide6.QtCore import Qt
 from PySide6.QtTest import QTest
 from app.manual_takeoff import ManualTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');legacy(s,'legacy')
 d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 assert d.formula_unit_mode.currentData() is True,'ردیف تازه نباید قرارداد تاریخی بدون واحد داشته باشد'
 d.table.setCurrentCell(0,0);d.formula_reviewer.setText('بازبین');d.formula_review_note.setText('کنترل');QTest.mouseClick(d.formula_review_button,Qt.LeftButton);_qt.processEvents()
 assert s.load_manual_formulas('P')['legacy']['status']=='draft' and 'واحد' in d.status.text()
 d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_contract_cannot_be_removed_or_hidden_in_amendment(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',typed(),expected_revision=0,reason='ثبت')
 d=data();d.pop('variable_units');d.pop('unit_policy')
 with pytest.raises(ValueError):s.save_manual_formula('P','A',d,expected_revision=1,reason='حذف پنهانی واحد')
 s.review_manual_formula('P','A',expected_revision=1,reviewer='بازبین',note='کنترل');s.commit_manual_formula('P','A',expected_revision=1)
 with pytest.raises(ValueError):s.create_manual_formula_amendment('P','A',d,expected_revision=1,created_by='مهندس',reason='حذف قرارداد واحد در اصلاحیه')
 s.store.close()

def _units_worker(path,event,queue):
 s=StructuralProApp(path);event.wait()
 try:
  s.bulk_edit_manual_formulas('P',['A'],changes={'variables':{'length':'1000'},'variable_units':{'length':'mm'}},expected_revisions={'A':1},reason='اصلاح هم‌زمان مقدار و واحد');queue.put('SAVED')
 except (RuntimeError,ValueError):queue.put('BLOCKED')
 finally:s.store.close()

def test_two_process_typed_unit_cas_and_integrity(tmp_path):
 import multiprocessing as mp
 import sqlite3
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',typed(),expected_revision=0,reason='ثبت');s.store.close()
 ctx=mp.get_context('spawn');event=ctx.Event();queue=ctx.Queue();ps=[ctx.Process(target=_units_worker,args=(str(tmp_path),event,queue)) for _ in range(2)]
 for p in ps:p.start()
 event.set();result=[queue.get(timeout=15) for p in ps]
 for p in ps:p.join(15);assert p.exitcode==0
 assert sorted(result)==['BLOCKED','SAVED']
 s=StructuralProApp(tmp_path);r=s.load_manual_formulas('P')['A'];assert r['revision']==2 and r['data']['variable_units']['length']=='mm' and Decimal(str(r['quantity']))==Decimal('.6');s.store.close()
 for db in tmp_path.rglob('*.db'):
  with sqlite3.connect(db) as conn:assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'

def test_exact_conversion_powers_cycles_and_unknown_units():
 from core.takeoff.units import convert_exact
 assert Decimal(str(convert_exact('12345678901234567890.123456789','mm','m')))==Decimal('12345678901234567.890123456789')
 rows={'A':{'expression':'-(x-x)+(x**2)','variables':{'x':'200'},'variable_units':{'x':'cm'},'unit_policy':POLICY,'unit':'m2'}}
 with pytest.raises(ValueError):evaluate_rows(rows) # length plus area, even if the length is zero
 rows['A']['expression']='(x**2)';assert evaluate_rows(rows)['A']==4
 rows['A'].update(expression='base',variables={},variable_units={},references={'base':'A'})
 with pytest.raises(ValueError):evaluate_rows(rows)
 for value in ('NaN','Infinity',True):
  with pytest.raises(ValueError):convert_exact(value,'m','cm')
 with pytest.raises(ValueError):convert_exact('1','m','m2')

def test_new_untyped_api_row_and_legacy_review_fail_closed(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');d=data();d.pop('variable_units',None);d.pop('unit_policy',None)
 with pytest.raises(ValueError):s.save_manual_formula('P','missing',d,expected_revision=0,reason='واحد ناموجود')
 s.store.close()

def test_legacy_read_migration_history_and_no_automatic_approval(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');legacy(s,'old');before=deepcopy(s.open_project('P'))
 assert s.load_manual_formulas('P')['old']['quantity']==6
 with pytest.raises(ValueError):s.review_manual_formula('P','old',expected_revision=1,reviewer='بازبین',note='متن جایگزین واحد نیست')
 assert s.open_project('P')==before
 d=deepcopy(before['manual_formula_register']['old']['data']);d.update(variable_units={'length':'m','width':'m','height':'m'},unit_policy=POLICY)
 s.save_manual_formula('P','old',d,expected_revision=1,reason='مهاجرت صریح مهندس بدون حدس')
 row=s.load_manual_formulas('P')['old'];assert row['revision']==2 and row['status']=='draft' and row['quantity']==6
 assert s.open_project('P')['manual_formula_history'][-1]['previous']==before['manual_formula_register']['old']
 s.store.close();s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['old']['data']['variable_units']==d['variable_units'];s.store.close()

def test_native_bulk_unit_control(tmp_path):
 from PySide6.QtWidgets import QApplication,QMessageBox
 from PySide6.QtCore import Qt,QTimer
 from PySide6.QtTest import QTest
 from app.manual_takeoff import ManualTakeoffDialog
 global _qt
 _qt=QApplication.instance() or QApplication([]);s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');s.save_manual_formula('P','A',typed(),expected_revision=0,reason='ثبت')
 d=ManualTakeoffDialog(s,'P');d.show();d.manual_tabs.setCurrentIndex(1);_qt.processEvents()
 assert hasattr(d,'formula_bulk_unit'),'واحد ویرایش گروهی به رابط متصل نیست'
 d.table.setCurrentCell(0,0);d.formula_bulk_name.setText('length');d.formula_bulk_value.setText('1000');d.formula_reason.setText('واحد و مقدار صریح');combo=d.formula_bulk_unit;combo.setCurrentIndex(combo.findData('mm'))
 confirmations=[];expired=[]
 responder=QTimer();responder.setInterval(10)
 watchdog=QTimer();watchdog.setSingleShot(True)
 def approve_native_bulk():
  dialog=QApplication.activeModalWidget()
  if isinstance(dialog,QMessageBox) and dialog.isVisible():
   button=dialog.button(QMessageBox.StandardButton.Yes)
   if button is not None:
    confirmations.append(dialog.text());responder.stop()
    QTest.mouseClick(button,Qt.LeftButton)
 def dismiss_stalled_confirmation():
  expired.append(True)
  dialog=QApplication.activeModalWidget()
  if dialog is not None:dialog.reject()
 responder.timeout.connect(approve_native_bulk);watchdog.timeout.connect(dismiss_stalled_confirmation)
 responder.start();watchdog.start(2000)
 try:QTest.mouseClick(d.formula_bulk_button,Qt.LeftButton);_qt.processEvents()
 finally:responder.stop();watchdog.stop()
 assert not expired,'Native unit-edit confirmation did not complete within two seconds'
 assert len(confirmations)==1,'The real bulk confirmation must appear exactly once'
 r=s.load_manual_formulas('P')['A'];assert r['data']['variable_units']['length']=='mm' and Decimal(str(r['quantity']))==Decimal('.6')
 d.close();d.deleteLater();_qt.processEvents();s.store.close()

def test_all_85_explicit_quantity_families_and_incompatible_output(tmp_path):
 from core.takeoff.manual_formula_register import catalog
 s=StructuralProApp(tmp_path);s.create_project('صریح مصنوعی','P')
 for i,f in enumerate(catalog()):
  r=s.save_manual_formula('P','f'+str(i),typed(family=f['code'],title=f['title'],member='member'+str(i),source_id='source'+str(i),unit='عدد',expression='q',variables={'q':'2'},variable_units={'q':'عدد'}),expected_revision=0,reason='مقدار دستی صریح؛ نه موتور تخصصی')
  assert r['quantity']==2 and r['data']['variable_units']=={'q':'عدد'}
 assert len(s.load_manual_formulas('P'))==85 and not s.open_project('P')['boq'];s.store.close()

def test_legacy_issued_basis_preserved_and_formal_typed_amendment(tmp_path):
 from core.takeoff.manual_formula_register import fingerprints
 from core.takeoff.commit_guards import rebuild_project_boq
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');legacy(s,'old');p=s.open_project('P');r=p['manual_formula_register']['old'];d=r['data'];r['status']='committed';r['review']={'reviewer':'بازبین تاریخی','digest':fingerprints(p['manual_formula_register'])['old']}
 # Historical v1 committed wire fixture, not a new approval through the API.
 p['takeoffs']=[{'id':'manual-formula:old','source_id':d['source_id'],'member_code':'C1','domain':'building','item':'column','params':deepcopy(d),'revision':1,'system':'اول','description':d['title'],'quantities':[{'code':'column','title':d['title'],'unit':'m3','amount':6,'formula':d['expression'],'role':'work','price_code':None,'unit_price':None}]}]
 _,p['boq']=rebuild_project_boq(p,p['takeoffs']);s.store.save('P',p);before=deepcopy(s.open_project('P'));assert s.load_manual_formulas('P')['old']['quantity']==6
 with pytest.raises(ValueError):s.commit_manual_formula('P','old',expected_revision=1)
 d=deepcopy(d);d.update(variable_units={'length':'m','width':'m','height':'m'},unit_policy=POLICY);d['variables']['length']='5'
 a=s.create_manual_formula_amendment('P','old',d,expected_revision=1,created_by='سازنده',reason='مهاجرت و اصلاح صریح')
 s.review_manual_formula_amendment('P',a['id'],expected_revision=1,reviewer='بازبین مستقل',note='واحد و مبنا');s.apply_manual_formula_amendment('P',a['id'],expected_revision=1)
 p=s.open_project('P');assert p['takeoffs']==before['takeoffs'] and p['manual_formula_register']==before['manual_formula_register'] and p['boq'][0]['quantity']==3
 s.store.close();s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['old']['data']['variable_units']==d['variable_units'] and s.open_project('P')['takeoffs'][0]['quantities'][0]['amount']==6;s.store.close()
