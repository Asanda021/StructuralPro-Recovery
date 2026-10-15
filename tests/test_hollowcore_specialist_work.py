"""Explicit synthetic manufacturer schedules, not engineering design approval."""
from copy import deepcopy
from decimal import Decimal
import pytest
from test_roof_specialist_work import sample as base_sample
from core.takeoff.reviewed_aec import empty_system,preview_system
from core.takeoff.engine import TakeoffEngine

KIND='hollow_core_detail'
KINDS=(KIND,)

def sample(kind=KIND):
 d=base_sample();d.update(kind=kind,components=empty_system(kind,'L1','S1')['components']);d['source']['source_id']='SYNTHETIC-HOLLOWCORE'
 rd=d['roof_detail'];g=rd['geometry'];g.update(depth='.25',topping_thickness='.05',panel_axis='x');g.pop('action',None)
 def box(i,c,y,w,z='0',h='.2'):
  return dict(id=i,component=c,x='0',y=y,z=z,length='4',width=w,height=h,source_ref='پلان مصنوعی قطعات',approved_by='کنترل مصنوعی')
 rd['regions']=[box('TOP','topping','0','4','.2','.05'),box('R1','precast','0','1.9'),box('J','joints','1.9','.2'),box('R2','precast','2.1','1.9')]
 rd['panels']=[]
 for i in (1,2):rd['panels'].append(dict(id=f'P{i}',physical_key=f'panel-{i}',region_id=f'R{i}',count='1',length='4',width='1.9',height='.2',shape='factory_finished_rectangle',spec_ref='گواهی مصنوعی مقطع کارخانه',fabrication_ref='گواهی مصنوعی قطعه نهایی کارخانه',source_ref='چیدمان مصنوعی قطعات',approved_by='کنترل مصنوعی',void_volume_m3='.52',void_source_ref='حجم حفره در گواهی مصنوعی',net_volume_m3='1',volume_source_ref='حجم خالص گواهی مصنوعی',unit_mass_kg='2400',mass_source_ref='جرم گواهی مصنوعی',mass_scope='whole_panel_including_factory_steel'))
 # Independent site steel and supplier bar/strand schedules with actual cut parts.
 site=deepcopy(rd['rebars']['main_x']);rd['rebars']['thermal']=site;site['series'][0].update(id='SITE',physical_key='site',steel_kind='reinforcing_bar',panel_id='')
 rd['rebars']['main_y']=dict(status='not_applicable',approved_by='کنترل مصنوعی',source_ref='دیتایل مصنوعی',reason='عدم کاربرد مصنوعی')
 for group,steel,weight,qty in [('main_x','prestressing_strand','1.1','4'),('additional','reinforcing_bar','.888','2')]:
  part=deepcopy(site);part['series']=[]
  for i in (1,2):
   s=deepcopy(site['series'][0]);s.update(id=f'{group}-{i}',physical_key=f'{group}-{i}',supply_scope='factory',panel_id=f'P{i}',steel_kind=steel,unit_weight_kg_m=weight,count=qty);part['series'].append(s)
  rd['rebars'][group]=part
 return d


def totals(d):
 r=preview_system(d,TakeoffEngine());assert r['ready'],r['blockers'];out={}
 for v in r['rows']:out[v['item_code']]=out.get(v['item_code'],Decimal(0))+Decimal(str(v['quantity']))
 return out


def test_independent_reference():
 t=totals(sample())
 assert t['concrete']==Decimal('.96') # 16*.05 + 4*.2*.2
 assert t['precast_concrete']==2 # 2*(4*1.9*.2-.52)
 assert t['hollow_core_panels']==2 and t['precast_panel_mass']==4800
 assert t['prestressing_steel']==Decimal('35.2') # 2*4*4*1.1
 assert t['rebar']==Decimal('49.728') # site 10*4*.888 + factory 2*2*4*.888
 assert t['formwork']==16 # explicitly supplied face only

@pytest.mark.parametrize('operation',['sqlite_amendment_and_boq','copy_delete_and_reports'])
def test_shared_workflow(tmp_path,operation,monkeypatch):
 import test_roof_specialist_work as base
 monkeypatch.setattr(base,'sample',sample);getattr(base,'test_'+operation)(tmp_path,KIND)

@pytest.mark.parametrize('case',['volume_only','mass_with_void_volume','no_topping','axis_y'])
def test_valid_documented_variants(case):
 d=sample();rd=d['roof_detail']
 if case=='volume_only':
  for p in rd['panels']:p.update(unit_mass_kg='',mass_source_ref='',mass_scope='')
 elif case=='mass_with_void_volume':
  for p in rd['panels']:p.update(net_volume_m3='',volume_source_ref='')
 elif case=='no_topping':
  rd['geometry'].update(depth='.2',topping_thickness='0');rd['regions']=[p for p in rd['regions'] if p['component']!='topping']
 elif case=='axis_y':
  rd['geometry']['panel_axis']='y'
  for p in rd['regions']:p['x'],p['y']=p['y'],p['x'];p['length'],p['width']=p['width'],p['length']
  for p in rd['panels']:p['length'],p['width']=p['width'],p['length']
 t=totals(d);assert t['precast_concrete']==2
 assert t['concrete']==Decimal('.16' if case=='no_topping' else '.96')
 if case=='volume_only':assert 'precast_panel_mass' not in t

@pytest.mark.parametrize('fault',['unit','missing_dimension','region_overlap','region_duplicate','partition','missing_panel','panel_duplicate','panel_physical','panel_region','panel_dimension','panel_count','panel_shape','fabrication','void_missing','void_negative','void_too_big','net_volume','volume_source','no_volume_or_mass','mass_scope','mass_negative','mass_source','panel_axis','hidden_joist','hidden_waffle','top_level_unknown','panel_unknown','factory_detail','factory_owner','factory_coverage','bar_physical','strand_site','site_owner','missing_steel_type','opening_panel','deduction_overlap','wrong_top','policy'])
def test_fail_closed(fault):
 d=sample();rd=d['roof_detail'];p=rd['panels'][0];steel=rd['rebars']['main_x']['series'][0]
 if fault=='unit':rd['geometry']['unit']='cm'
 elif fault=='missing_dimension':del p['height']
 elif fault=='region_overlap':rd['regions'][2]['y']='1.8'
 elif fault=='region_duplicate':rd['regions'].append(deepcopy(rd['regions'][0]))
 elif fault=='partition':rd['regions'].pop()
 elif fault=='missing_panel':rd['panels'].pop()
 elif fault=='panel_duplicate':rd['panels'].append(deepcopy(p))
 elif fault=='panel_physical':rd['panels'][1]['physical_key']=p['physical_key']
 elif fault=='panel_region':rd['panels'][1]['region_id']=p['region_id']
 elif fault=='panel_dimension':p['length']='3'
 elif fault=='panel_count':p['count']='2'
 elif fault=='panel_shape':p['shape']='site_cut'
 elif fault=='fabrication':p['fabrication_ref']=''
 elif fault=='void_missing':del p['void_volume_m3']
 elif fault=='void_negative':p['void_volume_m3']='-.1'
 elif fault=='void_too_big':p['void_volume_m3']='1.52'
 elif fault=='net_volume':p['net_volume_m3']='1.1'
 elif fault=='volume_source':p['volume_source_ref']=''
 elif fault=='no_volume_or_mass':p.update(net_volume_m3='',volume_source_ref='',unit_mass_kg='',mass_source_ref='',mass_scope='')
 elif fault=='mass_scope':p['mass_scope']='assumed_concrete_only'
 elif fault=='mass_negative':p['unit_mass_kg']='-1'
 elif fault=='mass_source':p['mass_source_ref']=''
 elif fault=='panel_axis':rd['geometry']['panel_axis']=None
 elif fault=='hidden_joist':rd['joist_layout']=[{}]
 elif fault=='hidden_waffle':rd['rib_layout']=[{}]
 elif fault=='top_level_unknown':rd['guess_density']='2400'
 elif fault=='panel_unknown':p['assumed_void_diameter']='.1'
 elif fault=='factory_detail':steel['shape_ref']=''
 elif fault=='factory_owner':steel['panel_id']='absent'
 elif fault=='factory_coverage':rd['rebars']['main_x']['series']=[];rd['rebars']['additional']['series'].pop()
 elif fault=='bar_physical':rd['rebars']['additional']['series'][0]['physical_key']=steel['physical_key']
 elif fault=='strand_site':steel['supply_scope']='site';steel['panel_id']=''
 elif fault=='site_owner':rd['rebars']['thermal']['series'][0]['panel_id']='P1'
 elif fault=='missing_steel_type':steel.pop('steel_kind')
 elif fault in ('opening_panel','deduction_overlap'):
  o=dict(id='O',kind='opening',x='0',y='0',z='0',length='.1',width='.1',height='.25',source_ref='مصنوعی',approved_by='مصنوعی');rd['deductions']=[o]
  if fault=='deduction_overlap':o=deepcopy(o);o['id']='DUP';rd['deductions'].append(o)
 elif fault=='wrong_top':rd['geometry']['topping_thickness']='.06'
 elif fault=='policy':d.pop('measurement_policy')
 assert not preview_system(d,TakeoffEngine())['ready']


def opening_sample():
 d=sample();rd=d['roof_detail'];rd['regions'][2]['component']='cast_in_place'
 rd['rebars']['opening']=deepcopy(rd['rebars']['thermal']);rd['rebars']['opening']['series'][0].update(id='OPENING-STEEL',physical_key='opening-steel')
 rd['deductions']=[dict(id='OPEN',kind='opening',x='1',y='1.95',z='0',length='1',width='.1',height='.25',source_ref='دیتایل مصنوعی بازشو در نوار درجاریز',approved_by='مصنوعی')]
 return d


def test_independent_opening_and_beam_joint():
 d=opening_sample();assert totals(d)['concrete']==Decimal('.935') # .96 - 1*.1*.25
 d['roof_detail']['deductions'][0].update(kind='beam_joint',owner_source_id='BEAM-OWNER');assert totals(d)['concrete']==Decimal('.935')
 d['roof_detail']['deductions'][0]['owner_source_id']='';assert not preview_system(d,TakeoffEngine())['ready']


def test_copy_remaps_ownership_and_no_duplicate_financial_payment(tmp_path):
 from core.platform.application import StructuralProApp
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample();a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P',KIND,'L1','S1',expected_revision=1,reviewer='مستقل',note='کنترل');a.commit_aec_system('P',KIND,'L1','S1',expected_revision=2)
 p=a.open_project('P');assert {r['item_code'] for r in p['boq']}=={'concrete','hollow_core_panels','rebar','formwork'}
 assert sum(Decimal(str(r['quantity'])) for r in p['boq'] if r['item_code']=='rebar')==Decimal('35.52')
 c=a.aec_workflow().copy_roof('P',KIND,'L1','S1',new_system_id='S2',new_source_id='COPY',reason='مصنوعی')['data']['roof_detail'];ids={p['id'] for p in c['panels']}
 assert not ids & {'P1','P2'} and all(p['region_id'] in {r['id'] for r in c['regions']} for p in c['panels'])
 assert all(s['panel_id'] in ids for g in c['rebars'].values() for s in g.get('series',[]) if s['supply_scope']=='factory')
 a.store.close()

@pytest.mark.parametrize('case',['policy','financial','concurrent','source','immutable'])
def test_workflow_guards(tmp_path,case,monkeypatch):
 import test_waffle_specialist_work as base
 monkeypatch.setattr(base,'sample',sample);base.test_persistence_guards(tmp_path,KIND,case)


def test_unreviewed_factory_schedule_cannot_be_waived():
 d=sample();rd=d['roof_detail']
 for k in ('main_x','additional'):rd['rebars'][k]=dict(status='not_applicable',reason='بدون جدول کارخانه',source_ref='مصنوعی',approved_by='مصنوعی')
 assert not preview_system(d,TakeoffEngine())['ready']


def test_decimal_mass_never_rounded_to_a_float():
 d=sample()
 for p in d['roof_detail']['panels']:p['unit_mass_kg']='2400.0000000000000000001'
 assert totals(d)['precast_panel_mass']==Decimal('4800.0000000000000000002')


def test_legacy_hollow_core_identity_cannot_be_counted_again(tmp_path):
 from core.platform.application import StructuralProApp
 from test_reviewed_aec_priorities_6_9 import sample as legacy_sample
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');a.save_aec_system_draft('P',legacy_sample('hollow_core'),expected_revision=0)
 with pytest.raises(ValueError,match='تاریخی'):a.save_aec_system_draft('P',sample(),expected_revision=0)
 a.store.close()


def test_real_detail_amendment_keeps_factory_and_site_finance_separate(tmp_path):
 from core.platform.application import StructuralProApp
 from hashlib import sha256
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample();a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P',KIND,'L1','S1',expected_revision=1,reviewer='بازبین مستقل',note='کنترل مصنوعی');a.commit_aec_system('P',KIND,'L1','S1',expected_revision=2);before=deepcopy(a.open_project('P'))
 changed=deepcopy(a.get_aec_system('P',KIND,'L1','S1')['data']);changed.pop('roof_review');rd=changed['roof_detail'];rd['panels'][0].update(void_volume_m3='.42',net_volume_m3='1.1',unit_mass_kg='2500',spec_ref='مقطع جدید مصنوعی',fabrication_ref='قطعه نهایی جدید مصنوعی')
 rd['rebars']['main_x']['series'][0]['count']='5';rd['rebars']['thermal']['series'][0]['count']='12'
 evidence=tmp_path/'new-detail.txt';evidence.write_text('EXPLICIT SYNTHETIC: P1 net=1.1 void=.42 whole mass=2500; P1 strands=5, site bars=12. No real engineering approval.')
 am=a.create_roof_amendment('P',KIND,'L1','S1',changed,expected_revision=2,created_by='سازنده مصنوعی',reason='تغییر مستند قطعه و آرماتور',evidence={'evidence_path':str(evidence),'evidence_sha256':sha256(evidence.read_bytes()).hexdigest(),'evidence_reference':'دیتایل اصلاحی مصنوعی'})
 a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='بازبین مستقل دیگر',note='کنترل مقادیر');a.apply_beam_amendment('P',am['id'],expected_revision=1);p=a.open_project('P')
 assert p['takeoffs']==before['takeoffs'] and p['reviewed_aec_systems']==before['reviewed_aec_systems']
 assert sum(Decimal(str(r['quantity'])) for r in p['boq'] if r['item_code']=='rebar')==Decimal('42.624')
 assert sum(Decimal(str(r['quantity'])) for r in p['boq'] if r['item_code']=='concrete')==Decimal('.96')
 assert not any(r['item_code'] in ('precast_concrete','precast_panel_mass','prestressing_steel') for r in p['boq'])
 assert Decimal(str(am['delta'][f'aec:{KIND}:L1:S1:R1']))==Decimal('.1')
 assert Decimal(str(am['delta'][f'aec:{KIND}:L1:S1:P1:mass']))==100
 path=tmp_path/'new.xlsx';a.export_roof_detail_report('P',KIND,'L1','S1',path,format='xlsx')
 from openpyxl import load_workbook
 w=load_workbook(path);text=' '.join(str(c.value) for sh in w for row in sh for c in row)
 assert all(x in text for x in ('مقطع جدید مصنوعی','حجم حفره','میلگرد معمولی کارخانه‌ای','میلگرد معمولی کارگاهی','فولاد پیش‌تنیدگی داخل قطعه','مقایسه مقدار پیشین'))
 assert all(sh.sheet_view.rightToLeft for sh in w)
 assert any(c.data_type=='n' and c.value==42.624 for row in w['خلاصه'] for c in row)
 a.store.close()
