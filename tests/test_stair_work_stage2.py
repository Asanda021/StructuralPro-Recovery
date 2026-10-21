"""Explicit synthetic ownership documents, not a real structural design."""
from pathlib import Path
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from core.platform.application import StructuralProApp
from test_stair_work_core import sample as core_sample

def doc(path,value):
 path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'reference':'سند صریحاً مصنوعی آزمون'}

def sample(folder,*,sid='ST1',floor='L1',pid='P',operations=None):
 from core.takeoff.stair_detail import ownership_binding,_validated
 d=core_sample(folder,sid=sid,floor=floor,pid=pid);e=d['stair_detail']['input']
 # Explicit variant with equal-width internal contacts and formed free ends.
 e['flights'][1]['start_y_m']='0';e['landings'][0].update(width_m='1.2',thickness_m='.15')
 for s in e['steps']:
  if s['flight_id']=='F2':s['y_m']='0'
 for f in e['form_faces']:
  f['physical_id']=sid+'-'+f['physical_id']
  if f['key'] in ('F1:end_low','F2:end_high'):f.update(treatment='form',reason='قالب انتهای آزاد؛ نمونه مصنوعی')
 for b in e['rebars']:b['physical_id']=sid+'-'+b['physical_id']
 dt=d['stair_detail'];dt['input_document']=doc(folder/(sid+'-input.json'),e);result,compiled=_validated(d,pid);bars={b['physical_id']:b for b in e['rebars']};alloc=[]
 for r in result['rows']:
  if operations is not None and r['operation'] not in operations:continue
  physical=r['physical_id'];alloc.append({'operation':r['operation'],'physical_id':physical,'scope_id':sid+'-OWN-'+physical,'bar_pieces':[sid+'-'+physical+'-'+str(i) for i in range(int(bars[physical]['count']))] if physical in bars else []})
 o={'schema':'stair_payment_ownership_v1','project_id':pid,'physical_stair_id':dt['physical_stair_id'],'coordinate_ref':'CS1','binding_sha256':ownership_binding(d),'input_document_sha256':dt['input_document']['sha256'],'prepared_by':'تنظیم‌کننده سند','reviewer':'بازبین مالکیت','reference':'مالکیت مستقل مصنوعی','envelope_scope':'complete_assembly_including_bars_forms_connections','bounds':{'min_x_m':'-1','max_x_m':'9','min_y_m':'-1','max_y_m':'5','min_z_m':'-1','max_z_m':'4'},'allocations':alloc}
 dt['ownership_document']=doc(folder/(sid+'-owner.json'),o);return d

def refresh(d,folder,owner=None):
 from core.takeoff.stair_detail import ownership_binding
 dt=d['stair_detail'];o=owner or json.loads(Path(dt['ownership_document']['path']).read_text());dt['input_document']=doc(folder/'revision-input.json',dt['input']);o.update(binding_sha256=ownership_binding(d),input_document_sha256=dt['input_document']['sha256']);dt['ownership_document']=doc(folder/'revision-owner.json',o)

def commit(a,d):
 a.save_aec_system_draft('P',d);a.review_roof_system('P','stair',d['floor_id'],d['system_id'],expected_revision=1,reviewer='بازبین نهایی',note='کنترل مستقل مصنوعی');return a.commit_aec_system('P','stair',d['floor_id'],d['system_id'],expected_revision=2)

def test_owned_rows_commit_sqlite_amendment_preserves_original(tmp_path):
 import core.takeoff.stair_detail as module
 assert hasattr(module,'ownership_binding'),'Payment ownership integration missing'
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);commit(a,d);old=deepcopy(a.open_project('P'));assert old['boq']
 d['stair_detail']['input']['rebars'][0]['straight_m']='4';revision=tmp_path/'rev';revision.mkdir();refresh(d,revision);p=revision/'reason.txt';p.write_text('EXPLICIT SYNTHETIC amendment');evidence={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':'نقشه اصلاحی مصنوعی'}
 am=a.create_roof_amendment('P','stair','L1','ST1',d,expected_revision=2,created_by='درخواست‌کننده',reason='اصلاح طول برش مصنوعی',evidence=evidence)
 with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
 a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='بازبین اصلاحیه',note='کنترل مستقل');a.apply_beam_amendment('P',am['id'],expected_revision=1)
 now=a.open_project('P');assert now['takeoffs']==old['takeoffs'] and now['boq']!=old['boq']
 with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
 a.store.close();b=StructuralProApp(tmp_path/'db');assert b.get_aec_system('P','stair','L1','ST1')['revision']==3;b.store.close()

def test_partial_ownership_never_pays_unknown_bars_or_forms(tmp_path):
 from core.takeoff.stair_detail import preview
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path,operations={'waist_concrete','step_concrete','landing_concrete'});r=preview(d,None);assert r['ready'] and r['excluded_operations'];assert {x['unit'] for x in r['rows']}=={'m3'};commit(a,d);assert {r['unit'] for r in a.open_project('P')['boq']}=={'m3'};a.store.close()

@pytest.mark.parametrize('bad',['file','hash','binding','missing_bar','duplicate_bar','duplicate_allocation','self_owner','bounds','unknown_operation','partial_contact','external_contact','shared_form'])
def test_invalid_owner_or_shared_geometry_cannot_register(tmp_path,bad):
 from core.takeoff.stair_detail import preview
 d=sample(tmp_path);dt=d['stair_detail'];o=json.loads(Path(dt['ownership_document']['path']).read_text());bars=[x for x in o['allocations'] if x['bar_pieces']]
 if bad=='file':Path(dt['ownership_document']['path']).unlink()
 elif bad=='hash':dt['ownership_document']['sha256']='0'*64
 elif bad=='binding':o['binding_sha256']='0'*64;dt['ownership_document']=doc(tmp_path/'bad.json',o)
 else:
  if bad=='missing_bar':bars[0]['bar_pieces'].pop()
  elif bad=='duplicate_bar':bars[1]['bar_pieces'][0]=bars[0]['bar_pieces'][0]
  elif bad=='duplicate_allocation':o['allocations'].append(deepcopy(o['allocations'][0]))
  elif bad=='self_owner':o['reviewer']=o['prepared_by']
  elif bad=='bounds':o['bounds']['max_x_m']='1'
  elif bad=='unknown_operation':o['allocations'][0]['operation']='invented'
  else:
   if bad=='partial_contact':dt['input']['landings'][0]['thickness_m']='.2'
   elif bad=='external_contact':next(x for x in dt['input']['form_faces'] if x['key']=='F1:end_low')['treatment']='contact'
   elif bad=='shared_form':next(x for x in dt['input']['form_faces'] if x['key']=='F1-S1:waist_contact')['treatment']='form'
   # Keep only still-existing paid rows; rejection must be the contact contract.
   from core.takeoff.stair_detail import _validated
   probe=deepcopy(d);probe['stair_detail']['input_document']=doc(tmp_path/'changed.json',dt['input']);result,_=_validated(probe,'P')
   ids={(x['operation'],x['physical_id']) for x in result['rows']};o['allocations']=[x for x in o['allocations'] if (x['operation'],x['physical_id']) in ids]
  refresh(d,tmp_path,o)
 r=preview(d,None);assert not r['ready'] and not r['rows']

@pytest.mark.parametrize('peer',['beam','column','foundation','tie','slab','legacy_stair','legacy_row'])
def test_unknown_foreign_member_stays_blocked(tmp_path,peer):
 from core.takeoff.stair_detail import project_gate
 from core.takeoff.reviewed_aec import _id
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);p=a.open_project('P')
 if peer=='beam':p['beam_detail_register']={'OLD':{'data':{}}}
 elif peer in ('column','foundation','tie'):p['reviewed_structural_members']={'OLD':{'data':{'kind':peer}}}
 elif peer in ('slab','legacy_stair'):p['reviewed_aec_systems']['OLD']={'data':{'kind':'solid_slab' if peer=='slab' else 'stair','system_id':'OLD','floor_id':'L2'}}
 else:p['takeoffs']=[{'source_id':'old-history'}]
 with pytest.raises(ValueError):project_gate(p,_id('stair','L1','ST1'))
 a.store.close()

@pytest.mark.parametrize('bad',['overlap','shared_bar','different_coordinate'])
def test_two_stairs_cannot_share_unresolved_geometry_or_bars(tmp_path,bad):
 from core.takeoff.stair_detail import project_gate
 from core.takeoff.reviewed_aec import _id
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');one=sample(tmp_path);commit(a,one);p=tmp_path/'other';p.mkdir();two=sample(p,sid='ST2',floor='L2');o=json.loads(Path(two['stair_detail']['ownership_document']['path']).read_text())
 if bad=='shared_bar':
  old=json.loads(Path(one['stair_detail']['ownership_document']['path']).read_text());next(x for x in o['allocations'] if x['bar_pieces'])['bar_pieces'][0]=next(x for x in old['allocations'] if x['bar_pieces'])['bar_pieces'][0]
 if bad=='different_coordinate':o['coordinate_ref']='OTHER'
 refresh(two,p,o);a.save_aec_system_draft('P',two)
 with pytest.raises(ValueError):project_gate(a.open_project('P'),_id('stair','L2','ST2'))
 a.store.close()

def test_review_actor_file_changes_cas_and_direct_store_protection(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);b=StructuralProApp(tmp_path/'db');b.get_aec_system('P','stair','L1','ST1');a.save_aec_system_draft('P',d,expected_revision=1)
 with pytest.raises(RuntimeError):b.save_aec_system_draft('P',d,expected_revision=1)
 for actor in (d['source']['approved_by'],d['stair_detail']['input']['metadata']['approved_by'],'تنظیم‌کننده سند','بازبین مستقل'):
  with pytest.raises(ValueError):a.review_roof_system('P','stair','L1','ST1',expected_revision=2,reviewer=actor,note='خودبازبینی ممنوع')
 p=a.open_project('P');next(iter(p['reviewed_aec_systems'].values()))['status']='committed'
 with pytest.raises(ValueError):a.store.save('P',p)
 a.review_roof_system('P','stair','L1','ST1',expected_revision=2,reviewer='مستقل نهایی',note='کنترل');owner=Path(d['stair_detail']['ownership_document']['path']);raw=owner.read_bytes();owner.write_bytes(raw+b' ')
 with pytest.raises(ValueError):a.commit_aec_system('P','stair','L1','ST1',expected_revision=3)
 assert not a.open_project('P')['boq'];owner.write_bytes(raw)
 a.commit_aec_system('P','stair','L1','ST1',expected_revision=3);old=deepcopy(a.open_project('P'));p=deepcopy(old);next(iter(p['reviewed_aec_systems'].values()))['data']['axis']='OTHER'
 with pytest.raises(ValueError):a.store.save('P',p)
 p=deepcopy(old);p['takeoffs'][0]['quantities'][0]['amount']='999'
 with pytest.raises(ValueError):a.store.save('P',p)
 assert a.open_project('P')==old;b.store.close();a.store.close()

def test_amendment_duplicate_actor_alias_changed_evidence_and_financial_lock(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);commit(a,d);old=deepcopy(a.open_project('P')['boq']);d['stair_detail']['input']['rebars'][0]['straight_m']='4';r=tmp_path/'rev';r.mkdir();refresh(d,r);p=r/'reason.txt';p.write_text('Explicit synthetic revision');ev={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':'دیتایل اصلاحی'}
 def create():return a.create_roof_amendment('P','stair','L1','ST1',d,expected_revision=2,created_by='Maker  Name',reason='اصلاح مصنوعی',evidence=ev)
 am=create()
 with pytest.raises(ValueError):create()
 for actor in ('maker name',d['source']['approved_by'],'بازبین مستقل'):
  with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer=actor,note='ممنوع')
 a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='مستقل اصلاحیه',note='کنترل');path=Path(d['stair_detail']['ownership_document']['path']);raw=path.read_bytes();path.write_bytes(raw+b' ')
 with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
 path.write_bytes(raw);p=a.open_project('P');p['estimate']={'locked':True};a.store.save('P',p)
 with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
 assert a.open_project('P')['boq']==old;a.store.close()

def test_initial_financial_lock(tmp_path):
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);a.review_roof_system('P','stair','L1','ST1',expected_revision=1,reviewer='مستقل نهایی',note='کنترل');p=a.open_project('P');p['estimate']={'locked':True};a.store.save('P',p)
 with pytest.raises(ValueError):a.commit_aec_system('P','stair','L1','ST1',expected_revision=2)
 assert not a.open_project('P')['boq'];a.store.close()

def test_direct_store_cannot_append_unreviewed_stair_rows(tmp_path):
 from core.takeoff.stair_detail import takeoffs
 from core.takeoff.commit_guards import rebuild_project_boq
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);p=a.open_project('P');p['takeoffs'],p['boq']=rebuild_project_boq(p,takeoffs(d,1))
 with pytest.raises(ValueError):a.store.save('P',p)
 assert not a.open_project('P')['takeoffs'] and not a.open_project('P')['boq'];a.store.close()

def test_payable_totals_exclude_unowned_quantities(tmp_path):
 from core.takeoff.stair_detail import preview
 from decimal import Decimal,localcontext
 d=sample(tmp_path,operations={'waist_concrete'});r=preview(d,None);assert set(r['payable_totals_exact'])=={'m3'}
 with localcontext() as c:
  c.prec=512;assert Decimal(r['payable_totals_exact']['m3'])==sum(Decimal(x['quantity']) for x in r['rows'])

def test_direct_store_cannot_inject_payable_boq_for_draft(tmp_path):
 from core.takeoff.stair_detail import takeoffs
 from core.takeoff.commit_guards import rebuild_project_boq
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample(tmp_path);a.save_aec_system_draft('P',d);p=a.open_project('P');_,p['boq']=rebuild_project_boq(p,takeoffs(d,1))
 with pytest.raises(ValueError):a.store.save('P',p)
 assert not a.open_project('P')['boq'];a.store.close()
