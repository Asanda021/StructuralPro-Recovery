from copy import deepcopy
from decimal import Decimal
import pytest
from core.platform.application import StructuralProApp

def data(**kw):
 d=dict(family='column',title='ستون مصنوعی',floor='اول',member='C1',unit='m3',expression='length*width*height',variables={'length':'10','width':'0.2','height':'3'},references={},source_id='manual:test:A',basis='ورودی صریح مصنوعی؛ طول و عرض و ارتفاع متر',deductions=[])
 d.update(kw)
 if 'variable_units' not in kw:
  explicit={'length':'m','width':'m','height':'m','طول':'m','عرض':'m','ارتفاع':'m','تعداد':'عدد'}
  d['variable_units']={k:explicit[k] for k in d['variables'] if k in explicit}
 d.setdefault('unit_policy','dimensional_decimal_v1')
 return d

def app(tmp_path):
 s=StructuralProApp(tmp_path);s.create_project('مصنوعی','P');return s

def ready(s):assert callable(getattr(s,'save_manual_formula',None)), 'فرمول به SQLite متصل نیست'

def test_save_reopen_exact_formula_review_boq(tmp_path):
 s=app(tmp_path);ready(s)
 d=data(variables={'length':'12345678901234567890.123456789','width':'1','height':'1'})
 row=s.save_manual_formula('P','A',d,expected_revision=0,reason='ثبت اولیه');assert row['status']=='draft';assert not s.open_project('P')['boq'];s.store.close()
 s=StructuralProApp(tmp_path);assert s.load_manual_formulas('P')['A']['data']==d
 assert Decimal(str(s.load_manual_formulas('P')['A']['quantity']))==Decimal(d['variables']['length'])
 with pytest.raises(ValueError):s.commit_manual_formula('P','A',expected_revision=1)
 s.review_manual_formula('P','A',expected_revision=1,reviewer='مهندس آزمون',note='فرمول و واحد کنترل شد')
 s.commit_manual_formula('P','A',expected_revision=1)
 p=s.open_project('P');assert Decimal(str(p['boq'][0]['quantity']))==Decimal(d['variables']['length']);assert p['takeoffs'][0]['params']['expression']==d['expression']
 with pytest.raises(ValueError):s.commit_manual_formula('P','A',expected_revision=1)
 with pytest.raises(ValueError):s.save_manual_formula('P','A',d,expected_revision=1,reason='دوباره')
 s.store.close()

def test_recalculate_dependents_reset_review_and_freeze_posted(tmp_path):
 s=app(tmp_path);ready(s);s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 b=data(source_id='manual:test:B',expression='base*2',variables={},references={'base':'A'},member='C2')
 s.save_manual_formula('P','B',b,expected_revision=0,reason='وابسته');s.review_manual_formula('P','B',expected_revision=1,reviewer='مهندس',note='کنترل')
 d=data(variables={'length':'5','width':'0.2','height':'3'});s.save_manual_formula('P','A',d,expected_revision=1,reason='اصلاح طول')
 rows=s.load_manual_formulas('P');assert rows['B']['quantity']==6;assert rows['B']['status']=='draft';assert rows['B']['revision']==2
 s.review_manual_formula('P','B',expected_revision=2,reviewer='مهندس',note='کنترل');s.commit_manual_formula('P','B',expected_revision=2)
 before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.save_manual_formula('P','A',data(),expected_revision=2,reason='تغییر مقدار قطعی وابسته')
 assert s.open_project('P')==before;s.store.close()

@pytest.mark.parametrize('bad',[{'expression':'__import__("os")'},{'expression':'1/3','variables':{}},{'unit':'نامعتبر'},{'references':{'length':'A'}},{'source_id':''},{'variables':{'length':True,'width':'1','height':'1'}}])
def test_invalid_formula_atomic(tmp_path,bad):
 s=app(tmp_path);ready(s)
 with pytest.raises(ValueError):s.save_manual_formula('P','A',data(**bad),expected_revision=0,reason='اول')
 assert not s.open_project('P').get('manual_formula_register');s.store.close()

def test_sources_units_and_stale_revision(tmp_path):
 s=app(tmp_path);ready(s);s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 with pytest.raises(ValueError):s.save_manual_formula('P','B',data(),expected_revision=0,reason='منبع تکراری')
 with pytest.raises(ValueError):s.save_manual_formula('P','B',data(source_id='B',unit='m2',expression='base',variables={},references={'base':'A'}),expected_revision=0,reason='واحد غلط')
 with pytest.raises(RuntimeError):s.save_manual_formula('P','A',data(),expected_revision=0,reason='قدیمی')
 with pytest.raises(ValueError):s.save_manual_formula('P','A',data(source_id='new'),expected_revision=1,reason='هویت جدید')
 s.store.close()

def test_reference_in_denominator_changes_dimensions_and_must_block():
 from core.takeoff.formulas import evaluate_rows
 with pytest.raises(ValueError):evaluate_rows({'A':{'unit':'m2','expression':'2'},'B':{'unit':'m2','expression':'1/base','references':{'base':'A'}}})

def test_bulk_atomic_edit_and_copy_remaps_dependencies(tmp_path):
 s=app(tmp_path);ready(s);s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 s.save_manual_formula('P','B',data(source_id='manual:B',member='C2',variables={},expression='base*2',references={'base':'A'}),expected_revision=0,reason='وابسته')
 assert callable(getattr(s,'copy_manual_formulas',None)), 'کپی اتمیک فرمول‌ها وجود ندارد'
 copied=s.copy_manual_formulas('P',['A','B'],floor='دوم',expected_revisions={'A':1,'B':1},reason='کپی طبقه')
 reg=s.load_manual_formulas('P');assert len(reg)==4;assert copied['A']!=copied['B'];assert reg[copied['B']]['data']['references']['base']==copied['A']
 assert reg[copied['A']]['data']['source_id']!=reg['A']['data']['source_id']
 s.bulk_edit_manual_formulas('P',[copied['A']],changes={'variables':{'length':'5'}},expected_revisions={copied['A']:1},reason='طول جدید')
 reg=s.load_manual_formulas('P');assert reg[copied['B']]['quantity']==6;assert reg['B']['quantity']==12
 before=deepcopy(s.open_project('P'))
 with pytest.raises(ValueError):s.bulk_edit_manual_formulas('P',['A','B'],changes={'variables':{'missing':'9'}},expected_revisions={'A':1,'B':1},reason='فیلد غلط')
 assert s.open_project('P')==before;s.store.close()

def test_all_85_catalog_families_allow_explicit_documented_manual_quantity(tmp_path):
 from core.takeoff.manual_formula_register import catalog
 s=app(tmp_path);families=catalog();assert len(families)==85
 for i,f in enumerate(families):
  r=s.save_manual_formula('P','family'+str(i),data(family=f['code'],title=f['title'],member='عضو'+str(i),source_id='synthetic:family:'+str(i),unit='عدد',expression='تعداد',variables={'تعداد':'2'}),expected_revision=0,reason='فقط ثبت مستند مصنوعی؛ نه موتور تخصصی')
  assert r['quantity']==2 and r['status']=='draft'
 assert len(s.load_manual_formulas('P'))==85;assert not s.open_project('P')['boq'];s.store.close()

def test_tampered_sqlite_review_and_cas_are_fail_closed(tmp_path):
 s=app(tmp_path);s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول');s.review_manual_formula('P','A',expected_revision=1,reviewer='بازبین',note='کنترل')
 other=StructuralProApp(tmp_path);other.save_manual_formula('P','A',data(variables={'length':'5','width':'0.2','height':'3'}),expected_revision=1,reason='اصلاح هم‌زمان')
 with pytest.raises(RuntimeError):s.commit_manual_formula('P','A',expected_revision=1)
 p=other.open_project('P');p['manual_formula_register']['A']['quantity']=999;other.store.save('P',p)
 with pytest.raises(ValueError):s.load_manual_formulas('P')
 other.store.close();s.store.close()

def test_unbound_deduction_and_duplicate_physical_member_blocked(tmp_path):
 s=app(tmp_path);s.save_manual_formula('P','A',data(),expected_revision=0,reason='اول')
 with pytest.raises(ValueError):s.save_manual_formula('P','B',data(source_id='B'),expected_revision=0,reason='عضو همان عملیات دوباره')
 with pytest.raises(ValueError):s.save_manual_formula('P','B',data(source_id='B',member='C2',deductions=[{'id':'opening','quantity':'2','unit':'m3','basis':'ورودی صریح'}]),expected_revision=0,reason='کسر بدون اتصال فرمول')
 s.store.close()
