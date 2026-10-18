"""Synthetic fixtures: core persistence is not financial/engineering acceptance."""
from pathlib import Path
from hashlib import sha256
from copy import deepcopy
from decimal import Decimal,localcontext,Inexact,Rounded
import json,importlib.util
import pytest
from core.platform.application import StructuralProApp
ROOT=Path(__file__).resolve().parents[1]

def sample(folder,*,sid='ST1',floor='L1',pid='P'):
 from core.takeoff.stair_detail import new_detail
 d=new_detail(floor,sid);d.update(building_id='B1',axis='A-1');d['source']={'mode':'manual','source_id':'SRC-'+sid,'approved_by':'تهیه‌کننده مصنوعی','measurement_ref':'برداشت صریحاً مصنوعی','plan_ref':'پلان مصنوعی','detail_ref':'دیتایل مصنوعی'}
 e=json.loads((ROOT/'examples/stair_chat_example.json').read_text());e['metadata'].update(project_id=pid,floor_id=floor,stair_id=sid);p=folder/(sid+'-input.json');p.write_text(json.dumps(e,ensure_ascii=False));d['stair_detail'].update(input=e,physical_stair_id='PH-'+sid,input_document={'path':str(p),'sha256':sha256(p.read_bytes()).hexdigest(),'reference':'دیتایل صریحاً مصنوعی'},preflight={'reviewer':'بازبین جدید مستقل','ownership_reference_claim':'ادعای مرجع مالکیت؛ هنوز تأیید مالی نشده'});return d

def test_sqlite_cas_reopen_and_preview(tmp_path):
 assert importlib.util.find_spec('core.takeoff.stair_detail') is not None,'Stair AEC core adapter missing'
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);r=a.save_aec_system_draft('P',d);assert r['revision']==1
 b=StructuralProApp(tmp_path/'db');assert b.get_aec_system('P','stair','L1','ST1')['data']==d
 out=b.preview_aec_system('P','stair','L1','ST1');assert out['engineering_ready'],out['blockers'];assert out['ready'] is False and out['commit_allowed'] is False and not out['rows'];assert out['takeoff_candidates']
 assert out['totals_exact']['reinforcement']=='98.5680'
 with localcontext() as c:
  c.prec=512;assert Decimal(out['totals_exact']['step_concrete'])==Decimal('.54');assert Decimal(out['totals_exact']['landing_concrete'])==Decimal('.564')
 a.save_aec_system_draft('P',d,expected_revision=1)
 with pytest.raises(RuntimeError):b.save_aec_system_draft('P',d,expected_revision=1)
 assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';b.store.close();a.store.close()

@pytest.mark.parametrize('bad',['file','hash','content','unit','float','zero','duplicate_step','incomplete_rebar','self_review','foreign_project','identity','component'])
def test_engine_or_document_invalid_stays_blocked(tmp_path,bad):
 from core.takeoff.stair_detail import preview
 d=sample(tmp_path);dt=d['stair_detail'];e=dt['input']
 if bad=='file':Path(dt['input_document']['path']).unlink()
 elif bad=='hash':dt['input_document']['sha256']='f'*64
 elif bad=='content':e['metadata']['story_ref']='محتوای متفاوت'
 elif bad=='self_review':dt['preflight']['reviewer']=e['metadata']['approved_by']
 elif bad=='identity':d['system_id']='OTHER'
 elif bad=='component':next(iter(d['components'].values())).update(status='confirmed')
 else:
  if bad=='unit':e['units']['length']='cm'
  elif bad=='float':e['flights'][0]['width_m']=1.2
  elif bad=='zero':e['flights'][0]['normal_waist_thickness_m']='0'
  elif bad=='duplicate_step':e['steps'].append(deepcopy(e['steps'][0]))
  elif bad=='incomplete_rebar':e['rebars']=[]
  elif bad=='foreign_project':e['metadata']['project_id']='OTHER'
  p=Path(dt['input_document']['path']);p.write_text(json.dumps(e,ensure_ascii=False));dt['input_document']['sha256']=sha256(p.read_bytes()).hexdigest()
 r=preview(d,None,project_id='P');assert not r['engineering_ready'] and not r['ready'] and not r['rows']

def test_no_financial_commit_migration_or_direct_store_bypass(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d)
 with pytest.raises(ValueError):a.review_roof_system('P','stair','L1','ST1',expected_revision=1,reviewer='مستقل',note='مدرک مالکیت کافی نیست')
 with pytest.raises(ValueError):a.commit_aec_system('P','stair','L1','ST1',expected_revision=1)
 p=a.open_project('P');next(iter(p['reviewed_aec_systems'].values()))['status']='committed'
 with pytest.raises(ValueError):a.store.save('P',p)
 changed=deepcopy(d);changed.pop('measurement_policy')
 with pytest.raises(ValueError):a.save_aec_system_draft('P',changed,expected_revision=1)
 old=a.new_aec_system('stair','L2','OLD');a.save_aec_system_draft('P',old)
 with pytest.raises(ValueError):a.save_aec_system_draft('P',sample(tmp_path,sid='OLD',floor='L2'),expected_revision=1)
 assert not a.open_project('P')['boq'];a.store.close()

def test_exact_context_does_not_change_engine_results(tmp_path):
 from core.takeoff.stair_detail import preview
 d=sample(tmp_path);normal=preview(d,None)
 with localcontext() as c:
  c.prec=512;c.traps[Inexact]=True;c.traps[Rounded]=True;strict=preview(d,None)
 assert strict['engineering_ready'] and strict['totals_exact']==normal['totals_exact']

@pytest.mark.parametrize('field',['source','physical'])
def test_duplicate_source_or_physical_identity(tmp_path,field):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');one=sample(tmp_path);a.save_aec_system_draft('P',one);two=sample(tmp_path,sid='ST2',floor='L2')
 if field=='source':two['source']=deepcopy(one['source'])
 else:two['stair_detail']['physical_stair_id']=one['stair_detail']['physical_stair_id']
 with pytest.raises(ValueError):a.save_aec_system_draft('P',two)
 a.store.close()
