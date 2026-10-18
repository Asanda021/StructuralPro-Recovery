"""Explicit synthetic five-floor stair acceptance using the real application.

The historical ARCH-5 project is copied and kept byte-for-byte logically intact.
Unknown historical structural ownership remains blocked; STAIR-5 is independent.
"""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal,localcontext
from hashlib import sha256
import argparse,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from core.platform.application import StructuralProApp
from test_stair_work_stage2 import sample,refresh
from core.commercial.exact_values import exact

@exact
def verify(reference,out):
 out=Path(out).resolve();out.mkdir(exist_ok=False);historical=None
 if reference:
  reference=Path(reference).resolve();assert (reference/'projects.db').is_file()
  shutil.copytree(reference,out/'historical-db');h=StructuralProApp(out/'historical-db');historical=deepcopy(h.open_project('ARCH-5'));assert len(historical['boq'])==83 and len(historical['beam_amendments'])==6
  folder=out/'historical-probe';folder.mkdir();probe=sample(folder,pid='ARCH-5',sid='ST-PROBE')
  from core.takeoff.reviewed_aec import _id
  from core.takeoff.stair_detail import project_gate
  image=deepcopy(historical);key=_id('stair','L1','ST-PROBE');image['reviewed_aec_systems'][key]={'data':probe,'revision':1,'status':'draft'}
  try:project_gate(image,key)
  except ValueError as exc:blocked=str(exc)
  else:raise AssertionError('Historical ownership gate unexpectedly opened')
  now=h.open_project('ARCH-5');assert now==historical
  assert h.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';h.store.close()
 a=StructuralProApp(out/'db');pid='STAIR-5';a.create_project('پنج‌طبقه صریحاً مصنوعی؛ مستقل از مالکیت تاریخی',pid);inputs={}
 for n in range(1,6):
  floor='L'+str(n);sid='ST-'+floor;folder=out/'documents'/floor;folder.mkdir(parents=True);d=sample(folder,pid=pid,floor=floor,sid=sid);e=d['stair_detail']['input'];z=Decimal(4*(n-1))
  for k in ('story_start_z_m','story_end_z_m'):e['metadata'][k]=str(Decimal(e['metadata'][k])+z)
  for f in e['flights']:
   for k in ('start_top_z_m','end_top_z_m'):f[k]=str(Decimal(f[k])+z)
  for p in e['landings']:p['top_z_m']=str(Decimal(p['top_z_m'])+z)
  owner=json.loads(Path(d['stair_detail']['ownership_document']['path']).read_text());owner['bounds'].update(min_z_m=str(z-Decimal('.2')),max_z_m=str(z+Decimal('3.2')));refresh(d,folder,owner)
  a.save_aec_system_draft(pid,d);a.review_roof_system(pid,'stair',floor,sid,expected_revision=1,reviewer='بازبین نهایی مستقل',note='کنترل مستقل نمونه مصنوعی');a.commit_aec_system(pid,'stair',floor,sid,expected_revision=2);inputs[floor]=deepcopy(d)
 original=deepcopy(a.open_project(pid));before={floor:deepcopy(a.get_aec_system(pid,'stair',floor,'ST-'+floor)) for floor in inputs}
 folder=out/'documents/revision-L3';folder.mkdir();d=deepcopy(inputs['L3']);d['stair_detail']['input']['rebars'][0]['straight_m']='4';refresh(d,folder);reason=folder/'reason.txt';reason.write_text('EXPLICIT SYNTHETIC: L3 documented straight bar length 3 m -> 4 m',encoding='utf-8');evidence={'evidence_path':str(reason),'evidence_sha256':sha256(reason.read_bytes()).hexdigest(),'evidence_reference':'اصلاحیه مصنوعی طول برش طبقه سوم'}
 amendment=a.create_roof_amendment(pid,'stair','L3','ST-L3',d,expected_revision=2,created_by='درخواست‌کننده مستقل',reason='اصلاح مستند مصنوعی طبقه سوم',evidence=evidence)
 try:a.apply_beam_amendment(pid,amendment['id'],expected_revision=1)
 except ValueError:pass
 else:raise AssertionError('Unreviewed amendment applied')
 a.review_beam_amendment(pid,amendment['id'],expected_revision=1,reviewer='بازبین مستقل اصلاحیه',note='کنترل مستقل طول برش');a.apply_beam_amendment(pid,amendment['id'],expected_revision=1)
 try:a.apply_beam_amendment(pid,amendment['id'],expected_revision=1)
 except ValueError:pass
 else:raise AssertionError('Amendment applied twice')
 a.store.close();a=StructuralProApp(out/'db');after=a.open_project(pid);assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';assert after['takeoffs']==original['takeoffs'];versions={};steel={};by_floor={}
 for floor in inputs:
  current=a.get_aec_system(pid,'stair',floor,'ST-'+floor);versions[floor]=current['revision']
  if floor!='L3':assert current==before[floor]
  r=a.preview_aec_system(pid,'stair',floor,'ST-'+floor);assert r['ready'];steel[floor]=r['payable_totals_exact']['kg'];by_floor[floor]={'engineering':r['totals_exact'],'owned':r['payable_totals_exact']}
 # Independent reference: 5 groups x 6 bars x 3.7 m x .888 kg/m per floor;
 # L3 adds 6 x 1 m x .888 kg/m. No production geometry is inferred.
 assert all(Decimal(v)==Decimal('98.568')+(Decimal('5.328') if f=='L3' else 0) for f,v in steel.items())
 assert sum(map(Decimal,steel.values()))==Decimal('498.168')
 reports=out/'reports';reports.mkdir()
 for fmt in ('pdf','xlsx','docx','csv'):a.export_stair_detail_report(pid,'L3','ST-L3',reports/('stair-L3.'+fmt),format=fmt)
 result={'explicitly_synthetic':True,'project_id':pid,'boq_rows':len(after['boq']),'amendments':len(after['beam_amendments']),'effective_versions':versions,'steel_by_floor_kg':steel,'total_steel_kg':str(sum(map(Decimal,steel.values()))),'by_floor':by_floor,'original_takeoffs_preserved':True,'other_floors_unchanged':True,'historical_boq_rows':83 if historical else None,'historical_amendments':6 if historical else None,'historical_records_preserved':True if historical else None,'historical_integration_blocker':blocked if historical else 'Historical reference not supplied; not tested','sqlite_integrity':'ok','amendment_id':amendment['id'],'windows_office_tested':False,'documents':{str(p.relative_to(out)):sha256(p.read_bytes()).hexdigest() for p in (out/'documents').rglob('*') if p.is_file()}}
 (out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');a.store.close();return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference-db');p.add_argument('--output',required=True);args=p.parse_args();print(json.dumps(verify(args.reference_db,args.output),ensure_ascii=False,indent=2))
