"""Explicit synthetic stage-one pile persistence; never financial acceptance."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
from decimal import Decimal,localcontext,Inexact,Rounded
import json,pytest
from core.platform.application import StructuralProApp

def sample(folder,group='PG1',floor='FND'):
 from core.takeoff.bored_pile_detail import new_detail
 d=new_detail(floor,group);e=json.loads(Path('examples/bored_pile_documented_synthetic.json').read_text());e.update(group_id=group,floor_id=floor);d['source']={'mode':'manual','source_id':e['source']['source_id'],'approved_by':e['source']['approved_by'],'measurement_ref':e['source']['source_ref']};d['pile_detail'].update(input=e,preflight={'reviewer':'IndependentReviewer','ownership_reference_claim':'ادعای مصنوعی؛ مجوز مالی نیست'});refresh(d,folder);return d

def refresh(d,folder):
 p=folder/(d['member_id']+'.json');p.write_text(json.dumps(d['pile_detail']['input'],ensure_ascii=False));d['pile_detail']['input_document']={'path':str(p),'sha256':sha256(p.read_bytes()).hexdigest(),'reference':'دیتایل صریحاً مصنوعی'}

def test_sqlite_preview_cas_and_exact_reference(tmp_path):
 d=sample(tmp_path);a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');a.save_structural_member_draft('P',d)
 b=StructuralProApp(tmp_path/'db');assert b.get_structural_member('P','bored_pile','FND','PG1')['data']==d
 r=b.preview_structural_member('P','bored_pile','FND','PG1');assert r['engineering_ready'] and not r['ready'] and not r['commit_allowed'] and not r['rows'];assert r['takeoff_candidates']
 with localcontext() as c:
  c.prec=256;assert Decimal(r['totals_exact']['m3'])==Decimal('3.14159265358979323846264338327950288419716939937510')*Decimal('.8')**2/4*Decimal('11.25')
  assert Decimal(r['totals_exact']['kg'])==8*Decimal('12.2')*Decimal('1.58')+Decimal('80.125')*Decimal('.395')
 a.save_structural_member_draft('P',d,expected_revision=1)
 with pytest.raises(RuntimeError):b.save_structural_member_draft('P',d,expected_revision=1)
 assert b.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';a.store.close();b.store.close()

@pytest.mark.parametrize('bad',['hash','file','content','project','identity','float','zero','bar_detail','generic_component','source'])
def test_bad_detail_never_ready(tmp_path,bad):
 from core.takeoff.bored_pile_detail import preview
 d=sample(tmp_path);dt=d['pile_detail'];e=dt['input']
 if bad=='hash':dt['input_document']['sha256']='0'*64
 elif bad=='file':Path(dt['input_document']['path']).unlink()
 elif bad=='content':e['datum']['axis_ref']='changed'
 elif bad=='project':e['project_id']='OTHER';refresh(d,tmp_path)
 elif bad=='identity':d['member_id']='OTHER'
 elif bad=='generic_component':d['formwork']['status']='confirmed'
 elif bad=='source':d['source']['source_id']='OTHER'
 else:
  if bad=='float':e['piles'][0]['diameter_m']=.8
  if bad=='zero':e['piles'][0]['diameter_m']='0'
  if bad=='bar_detail':e['piles'][0]['rebars']['longitudinal']['series'][0]['cut_length_ref']=''
  refresh(d,tmp_path)
 r=preview(d,None,project_id='P');assert not r['engineering_ready'] and not r['ready'] and not r['rows']

@pytest.mark.parametrize('bad',['physical','bar','source','pile_id'])
def test_duplicate_claims_across_groups(tmp_path,bad):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_structural_member_draft('P',d);other=sample(tmp_path,'PG2','F2');e=other['pile_detail']['input'];e['source']['source_id']='NEW';other['source']['source_id']='NEW';p=e['piles'][0]
 if bad!='physical':p['physical_id']='OTHER'
 if bad!='pile_id':p['id']='BP2'
 for k,g in p['rebars'].items():
  for s in g.get('series',[]):s['physical_id']='NEW-'+s['physical_id']
 if bad=='bar':p['rebars']['longitudinal']['series'][0]['physical_id']='bar-physical-01'
 if bad=='source':e['source']['source_id']=d['source']['source_id'];other['source']=deepcopy(d['source'])
 refresh(other,tmp_path)
 with pytest.raises(ValueError):a.save_structural_member_draft('P',other)
 a.store.close()

def test_historical_policy_and_financial_bypass_blocked(tmp_path):
 from core.takeoff.bored_pile_detail import POLICY
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_structural_member_draft('P',d)
 with pytest.raises(ValueError):a.commit_structural_member('P','bored_pile','FND','PG1',expected_revision=1)
 for attack in ('status','policy','takeoff','boq'):
  p=a.open_project('P')
  if attack=='status':next(iter(p['reviewed_structural_members'].values()))['status']='committed'
  if attack=='policy':next(iter(p['reviewed_structural_members'].values()))['data'].pop('measurement_policy')
  if attack=='takeoff':p['takeoffs'].append({'source_id':'X','params':{'pile_policy':POLICY},'quantities':[]})
  if attack=='boq':p['boq'].append({'source_id':'aec:bored_pile:FND:PG1:BP1:any:concrete_net','quantity':'1','unit':'m3'})
  with pytest.raises(ValueError):a.store.save('P',p)
 old=a.new_structural_member('bored_pile','FND','OLD');a.save_structural_member_draft('P',old)
 changed=sample(tmp_path,'OLD');changed['source']['source_id']='NEW';changed['pile_detail']['input']['source']['source_id']='NEW';refresh(changed,tmp_path)
 with pytest.raises(ValueError):a.save_structural_member_draft('P',changed,expected_revision=1)
 assert not a.open_project('P')['boq'];a.store.close()

def test_source_change_after_save_blocks_preview_and_save(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_structural_member_draft('P',d);Path(d['pile_detail']['input_document']['path']).write_text('{}')
 assert not a.preview_structural_member('P','bored_pile','FND','PG1')['engineering_ready']
 with pytest.raises(ValueError):a.save_structural_member_draft('P',d,expected_revision=1)
 a.store.close()

def test_inherited_decimal_traps_do_not_change_engine_contract(tmp_path):
 from core.takeoff.bored_pile_detail import preview
 d=sample(tmp_path);expected=preview(d,None)
 with localcontext() as c:
  c.traps[Inexact]=True;c.traps[Rounded]=True;r=preview(d,None)
 assert r['engineering_ready'] and r['totals_exact']==expected['totals_exact']

@pytest.mark.parametrize('attack',['wrong_register','revision','known_legacy_physical'])
def test_direct_store_and_historical_identity_controls(tmp_path,attack):
 from core.takeoff.reviewed_structural import _key
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path)
 if attack=='known_legacy_physical':
  old=a.new_structural_member('bored_pile','F2','OLD');old['geometry']['physical_pile_id']='pile-physical-01';a.save_structural_member_draft('P',old)
  with pytest.raises(ValueError):a.save_structural_member_draft('P',d)
 else:
  a.save_structural_member_draft('P',d);p=a.open_project('P');key=_key('bored_pile','FND','PG1')
  if attack=='wrong_register':p.setdefault('reviewed_aec_systems',{})['FOREIGN']=p['reviewed_structural_members'].pop(key)
  else:p['reviewed_structural_members'][key]['revision']=999
  with pytest.raises(ValueError):a.store.save('P',p)
 a.store.close()
