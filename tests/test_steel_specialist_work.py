"""Explicit synthetic schedules; no manufacturer or structural design approval."""
from copy import deepcopy
from decimal import Decimal
import pytest
from core.takeoff.reviewed_aec import empty_system,preview_system
from core.takeoff.engine import TakeoffEngine

KINDS=('steel_frame','steel_deck')
GROUPS=('columns','beams','secondary','bracing','truss','plates','bolts','welds','coatings','operations','studs','rebars')
def entry(i,**kw):return dict(id=i,physical_key='physical-'+i,source_ref='مدرک مصنوعی '+i,approved_by='کنترل مصنوعی',**kw)
def sample(kind='steel_frame'):
 d=empty_system(kind,'L1','S1');d.update(measurement_policy='steel_specialist_v1',building_id='B1',axis='A1',source={'mode':'manual','source_id':'SYNTHETIC-'+kind,'plan_ref':'پلان مصنوعی','detail_ref':'دیتایل مصنوعی'})
 groups={k:dict(status='not_applicable',approved_by='کنترل مصنوعی',source_ref='دیتایل مصنوعی',reason='عدم کاربرد فقط در نمونه مصنوعی',entries=[]) for k in GROUPS}
 def confirmed(k,entries):groups[k]=dict(status='confirmed',approved_by='کنترل مصنوعی',source_ref='دیتایل مصنوعی',entries=entries)
 if kind=='steel_frame':
  for k,l,w,c in [('columns','3.2','23.4','2'),('beams','4.5','18.8','3')]:confirmed(k,[entry(k,count=c,length_m=l,unit_weight_kg_m=w,unit_weight_source='گواهی وزن مصنوعی',section_ref='مقطع مصنوعی',steel_ref='فولاد مصنوعی',scope_ref='ساخت و نصب مشخص',cut_ref='برش مستقیم مستند')])
  confirmed('plates',[entry('P1',count='1',x='0',y='0',z='0',length_m='.25',width_m='.2',thickness_m='.012',density_kg_m3='7850',density_source='گواهی چگالی مصنوعی',steel_ref='ورق مصنوعی')])
  confirmed('bolts',[entry('BT1',count='4',unit_mass_kg='.1',mass_source='گواهی جرم مجموعه پیچ مهره واشر',spec_ref='مجموعه کامل با مشخصات مصنوعی',payment_basis='count')])
  confirmed('welds',[entry('W1',count='2',length_m='.5',spec_ref='جوش گوشه مصنوعی اندازه4میلی‌متر',method_ref='روش جوش مصنوعی')])
 else:
  confirmed('studs',[entry('ST1',count='20',unit_mass_kg='.15',mass_source='گواهی جرم مصنوعی',spec_ref='گل میخ مصنوعی با ارتفاع و قطر مستند',payment_basis='count')])
  confirmed('rebars',[entry('R1',count='10',length_m='4',unit_weight_kg_m='.888',unit_weight_source='گواهی وزن مصنوعی',section_ref='قطر12میلی‌متر',steel_ref='فولاد مصنوعی',scope_ref='میلگرد حرارتی',cut_ref='دیتایل برش مصنوعی')])
 deck=None
 if kind=='steel_deck':
  deck=dict(length_m='4',width_m='4',topping_m='.06',flute_depth_m='.05',flute_top_m='.08',flute_bottom_m='.04',pitch_m='.2',profile_ref='مقطع ذوزنقه واقعی مصنوعی',approved_by='کنترل مصنوعی',source_ref='پلان مصنوعی',openings=[],panels=[entry('D'+str(i),x='0',y=str(i),length_m='4',effective_width_m='1',nominal_width_m='1.1',side_lap_m='.1',end_lap_m='0',thickness_m='.001',unit_weight_kg_m2='10',weight_source='گواهی وزن بر مساحت اسمی مصنوعی',spec_ref='ورق مصنوعی') for i in range(4)])
 d['steel_detail']={'groups':groups,'deck':deck};return d

def totals(d):
 r=preview_system(d,TakeoffEngine());assert r['ready'],r['blockers'];t={}
 for row in r['rows']:t[row['item_code']]=t.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
 return t,r

@pytest.mark.parametrize('kind',KINDS)
def test_independent_reference(kind):
 t,r=totals(sample(kind))
 if kind=='steel_frame':assert t['structural_steel']==Decimal('408.27') and t['bolts']==4 and t['bolt_mass']==Decimal('.4') and t['weld']==1
 else:assert t['concrete']==Decimal('1.2') and t['deck_sheet']==Decimal('176') and t['studs']==20 and t['rebar']==Decimal('35.52')
 assert len({v['source_id'] for v in r['rows']})==len(r['rows'])

@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('fault',['no_source','zero','negative','count','duplicate','missing_spec','wrong_policy','unknown'])
def test_fail_closed(kind,fault):
 d=sample(kind);g=d['steel_detail']['groups'];p=g['columns' if kind=='steel_frame' else 'rebars']['entries'][0]
 if fault=='no_source':p['unit_weight_source']=''
 if fault=='zero':p['length_m']='0'
 if fault=='negative':p['length_m']='-1'
 if fault=='count':p['count']='1.5'
 if fault=='duplicate':g['plates' if kind=='steel_frame' else 'studs']['entries'][0]['physical_key']=p['physical_key']
 if fault=='missing_spec':p['section_ref']=''
 if fault=='wrong_policy':d['measurement_policy']='invalid'
 if fault=='unknown':p['guess']=1
 assert not preview_system(d,TakeoffEngine())['ready']

@pytest.mark.parametrize('fault',['width','flute','stud','bar_cut','overlap','opening','cut','no_certificate'])
def test_deck_rejects_incomplete_or_overlapping(fault):
 d=sample('steel_deck');deck=d['steel_detail']['deck']
 if fault=='width':deck['panels'][0]['effective_width_m']=''
 if fault=='flute':deck['flute_bottom_m']=''
 if fault=='stud':d['steel_detail']['groups']['studs']['entries'][0]['spec_ref']=''
 if fault=='bar_cut':d['steel_detail']['groups']['rebars']['entries'][0]['cut_ref']=''
 if fault=='overlap':deck['panels'][1]['y']='.5'
 if fault=='opening':deck['openings']=[{'id':'unknown'}]
 if fault=='cut':deck['panels'][0]['end_lap_m']='.2'
 if fault=='no_certificate':deck['panels'][0]['weight_source']=''
 assert not preview_system(d,TakeoffEngine())['ready']

@pytest.mark.parametrize('kind',KINDS)
def test_existing_ledger_review_amendment_and_four_reports(tmp_path,kind):
 from core.platform.application import StructuralProApp
 from hashlib import sha256
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی صریح','P');d=sample(kind)
 a.save_aec_system_draft('P',d,expected_revision=0)
 with pytest.raises(ValueError):a.commit_aec_system('P',kind,'L1','S1',expected_revision=1)
 a.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='بازبین مستقل',note='کنترل مستند')
 a.commit_aec_system('P',kind,'L1','S1',expected_revision=2);before=deepcopy(a.open_project('P'))
 assert not any(r['item_code'] in ('bolt_mass','stud_mass') for r in before['boq'])
 b=deepcopy(before);next(iter(b['reviewed_aec_systems'].values()))['data']['axis']='B'
 with pytest.raises(ValueError):a.store.save('P',b)
 d=deepcopy(a.get_aec_system('P',kind,'L1','S1')['data']);d.pop('roof_review')
 if kind=='steel_frame':d['steel_detail']['groups']['columns']['entries'][0]['count']='3'
 else:d['steel_detail']['deck']['topping_m']='.07'
 path=tmp_path/'certificate.txt';path.write_text('Explicit SYNTHETIC revised steel/deck detail')
 am=a.create_roof_amendment('P',kind,'L1','S1',d,expected_revision=2,created_by='سازنده',reason='اصلاح مستند مصنوعی',evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':'مدرک اصلاحی مصنوعی'})
 with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='سازنده',note='نامجاز')
 a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='بازبین دیگر',note='کنترل مستقل');a.apply_beam_amendment('P',am['id'],expected_revision=1)
 assert a.get_aec_system('P',kind,'L1','S1')['revision']==3
 assert a.open_project('P')['takeoffs']==before['takeoffs'] and a.open_project('P')['boq']!=before['boq']
 from core.reports.steel_detail_report import export
 for fmt in ('pdf','xlsx','docx','csv'):
  p=tmp_path/('steel.'+fmt);export(a,'P',kind,'L1','S1',p,format=fmt);assert p.stat().st_size>100
 a.store.close();a=StructuralProApp(tmp_path/'db');assert a.get_aec_system('P',kind,'L1','S1')['revision']==3;assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';a.store.close()

@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('case',['cas','source','physical','legacy','policy'])
def test_storage_guards(tmp_path,kind,case):
 from core.platform.application import StructuralProApp
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(kind)
 if case=='legacy':
  old=empty_system(kind,'L1','S1');old['source']={'mode':'manual','source_id':'LEGACY'};a.save_aec_system_draft('P',old,expected_revision=0)
  with pytest.raises(ValueError):a.save_aec_system_draft('P',d,expected_revision=1)
 else:
  a.save_aec_system_draft('P',d,expected_revision=0)
  if case=='cas':
   with pytest.raises(RuntimeError):a.save_aec_system_draft('P',d,expected_revision=0)
  elif case=='policy':
   d.pop('measurement_policy')
   with pytest.raises(ValueError):a.save_aec_system_draft('P',d,expected_revision=1)
  else:
   d['system_id']='S2'
   if case=='physical':d['source']['source_id']='OTHER'
   with pytest.raises(ValueError):a.save_aec_system_draft('P',d,expected_revision=0)
 a.store.close()

@pytest.mark.parametrize('case',['plate_overlap','bolt_spec','weld_spec','duplicate_emitted_source','scope_unknown'])
def test_steel_connections_fail_closed(case):
 d=sample();groups=d['steel_detail']['groups']
 if case=='plate_overlap':
  p=deepcopy(groups['plates']['entries'][0]);p.update(id='P2',physical_key='physical-P2');groups['plates']['entries'].append(p)
 if case=='bolt_spec':groups['bolts']['entries'][0]['spec_ref']=''
 if case=='weld_spec':groups['welds']['entries'][0]['method_ref']=''
 if case=='duplicate_emitted_source':groups['plates']['entries'][0]['id']='BT1-mass'
 if case=='scope_unknown':groups['columns']['entries'][0]['scope_ref']=''
 assert not preview_system(d,TakeoffEngine())['ready']

@pytest.mark.parametrize('kind',KINDS)
@pytest.mark.parametrize('fault',['identity','duplicate','evidence','finance','same_reviewer','repeat_apply'])
def test_formal_amendment_guards(tmp_path,kind,fault):
 from core.platform.application import StructuralProApp
 from hashlib import sha256
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(kind);a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='مستقل',note='کنترل');a.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
 d=deepcopy(a.get_aec_system('P',kind,'L1','S1')['data']);d.pop('roof_review')
 if kind=='steel_frame':d['steel_detail']['groups']['columns']['entries'][0]['count']='3'
 else:d['steel_detail']['deck']['topping_m']='.07'
 path=tmp_path/'new.txt';path.write_text('SYNTHETIC');kw=dict(expected_revision=2,created_by='سازنده',reason='علت مصنوعی',evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':'مرجع مصنوعی'})
 if fault=='identity':
  d['axis']='changed'
  with pytest.raises(ValueError):a.create_roof_amendment('P',kind,'L1','S1',d,**kw)
 else:
  am=a.create_roof_amendment('P',kind,'L1','S1',d,**kw)
  if fault=='duplicate':
   with pytest.raises(ValueError):a.create_roof_amendment('P',kind,'L1','S1',d,**kw)
  elif fault=='evidence':
   path.write_text('changed')
   with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='دیگری',note='کنترل')
  elif fault=='same_reviewer':
   with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='سازنده',note='کنترل')
  else:
   a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='دیگری',note='کنترل')
   if fault=='finance':
    p=a.open_project('P');p['contract']={'id':'locked'};a.store.save('P',p)
    with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
   else:
    a.apply_beam_amendment('P',am['id'],expected_revision=1)
    with pytest.raises((ValueError,RuntimeError)):a.apply_beam_amendment('P',am['id'],expected_revision=1)
 a.store.close()


def test_optional_members_coatings_and_operations_have_independent_quantities():
 d=sample();g=d['steel_detail']['groups']
 for key in ('secondary','bracing','truss'):
  p=deepcopy(g['columns']['entries'][0]);p.update(id=key,physical_key='physical-'+key,count='1',length_m='2',unit_weight_kg_m='5')
  g[key]=dict(status='confirmed',approved_by='کنترل مصنوعی',source_ref='دیتایل مصنوعی',entries=[p])
 g['coatings']=dict(status='confirmed',approved_by='کنترل مصنوعی',source_ref='مرجع مصنوعی',entries=[entry('COAT',count='2',length_m='2',width_m='3',spec_ref='ضدزنگ با ضخامت و لایه مستند',scope_ref='وجوه مستقل مصنوعی')])
 g['operations']=dict(status='confirmed',approved_by='کنترل مصنوعی',source_ref='مرجع مصنوعی',entries=[entry('MAKE',quantity='50',unit='kg',operation='fabrication',basis_ref='مبنای مستقل ساخت',spec_ref='دامنه مصنوعی ساخت')])
 t,_=totals(d);assert t['structural_steel']==Decimal('438.27') and t['steel_coating']==12 and t['steel_fabrication']==50


def test_exact_long_decimal_weight_never_rounds_to_binary_float(tmp_path):
 from core.platform.application import StructuralProApp
 d=sample();d['steel_detail']['groups']['columns']['entries'][0]['unit_weight_kg_m']='23.4000000000000000001'
 t,_=totals(d);assert t['structural_steel']==Decimal('408.27000000000000000064')
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P','steel_frame','L1','S1',expected_revision=1,reviewer='مستقل',note='کنترل');a.commit_aec_system('P','steel_frame','L1','S1',expected_revision=2);a.store.close()
 a=StructuralProApp(tmp_path/'db');assert sum(Decimal(str(v['quantity'])) for v in a.open_project('P')['boq'] if v['item_code']=='structural_steel')==Decimal('408.27000000000000000064');a.store.close()

@pytest.mark.parametrize('kind',KINDS)
def test_store_cannot_silently_replace_historical_contract(tmp_path,kind):
 from core.platform.application import StructuralProApp
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');old=empty_system(kind,'L1','S1');old['source']={'mode':'manual','source_id':'LEGACY'};a.save_aec_system_draft('P',old,expected_revision=0)
 p=a.open_project('P');next(iter(p['reviewed_aec_systems'].values()))['data']=sample(kind)
 with pytest.raises(ValueError):a.store.save('P',p)
 a.store.close()


def test_reports_expose_previous_proposed_and_reviewed_absences(tmp_path):
 test_existing_ledger_review_amendment_and_four_reports(tmp_path,'steel_frame')
 from core.platform.application import StructuralProApp
 from core.reports.steel_detail_report import export
 a=StructuralProApp(tmp_path/'db');p=tmp_path/'comparison.csv';export(a,'P','steel_frame','L1','S1',p,format='csv');text=p.read_text(encoding='utf-8-sig')
 assert 'پیشین: 149.76' in text and 'پیشنهادی: 224.64' in text
 assert 'عدم کاربرد مستند' in text and 'عدم کاربرد فقط در نمونه مصنوعی' in text
 a.store.close()
