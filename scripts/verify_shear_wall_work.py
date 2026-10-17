"""Extend the accepted synthetic five-floor project in an independent copy."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json,shutil,sys,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from core.platform.application import StructuralProApp
from test_shear_wall_work import sample,refresh

def verify(reference,out):
 reference=Path(reference).resolve();out=Path(out).resolve();out.mkdir(exist_ok=False);shutil.copytree(reference,out/'previous')
 db=out/'previous/previous/previous/package2/package1/db';assert (db/'projects.db').is_file()
 a=StructuralProApp(db);pid='ARCH-5';before=deepcopy(a.open_project(pid));assert before and len(before['boq'])==63
 before_ids={r['source_id'] for r in before['takeoffs']};inputs={}
 for floor,z in [('L1','0'),('L2','4'),('L3','8'),('L4','12'),('L5','16')]:
  folder=out/'documents'/floor;folder.mkdir(parents=True);sid='SW-'+floor;d=sample(folder,pid=pid,floor=floor,sid=sid,z=z)
  for op in d['shear_wall_detail']['input']['openings']:op['z_m']=str(Decimal(z)+1)
  refresh(d,folder);a.save_aec_system_draft(pid,d);a.review_roof_system(pid,'shear_wall',floor,sid,expected_revision=1,reviewer='بازبین نهایی مستقل',note='نمونه صریحاً مصنوعی');a.commit_aec_system(pid,'shear_wall',floor,sid,expected_revision=2);inputs[floor]=d
 original=deepcopy(a.open_project(pid));revision=out/'documents'/'revision-L3';revision.mkdir();d=deepcopy(inputs['L3']);d['shear_wall_detail']['input']['segments'][0]['length_m']='6';refresh(d,revision);reason=revision/'reason.txt';reason.write_text('EXPLICIT SYNTHETIC width change in L3 only');evidence={'evidence_path':str(reason),'evidence_sha256':sha256(reason.read_bytes()).hexdigest(),'evidence_reference':'اصلاحیه مصنوعی طبقه سوم'}
 am=a.create_roof_amendment(pid,'shear_wall','L3','SW-L3',d,expected_revision=2,created_by='درخواست‌کننده اصلاحیه',reason='اصلاح مصنوعی طبقه سوم',evidence=evidence);a.review_beam_amendment(pid,am['id'],expected_revision=1,reviewer='بازبین اصلاحیه مستقل',note='کنترل مستقل');a.apply_beam_amendment(pid,am['id'],expected_revision=1)
 for fmt in ('pdf','xlsx','docx','csv'):a.export_shear_wall_detail_report(pid,'L3','SW-L3',out/('shear-wall.'+fmt),format=fmt)
 a.store.close();b=StructuralProApp(db);after=b.open_project(pid);assert b.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
 assert after['takeoffs']==original['takeoffs'];assert [r for r in after['takeoffs'] if r['source_id'] in before_ids]==before['takeoffs']
 assert all(after['reviewed_aec_systems'][key]==row for key,row in before['reviewed_aec_systems'].items());assert all(after['beam_amendments'][key]==row for key,row in before['beam_amendments'].items())
 from core.takeoff.manual_formula_amendments import beam_effective_takeoffs
 effective=beam_effective_takeoffs(after,after['takeoffs']);totals={}
 for floor in inputs:
  rec=b.get_aec_system(pid,'shear_wall',floor,'SW-'+floor);assert rec['revision']==(3 if floor=='L3' else 2)
  if floor!='L3':assert rec['data']==b.get_aec_system(pid,'shear_wall',floor,'SW-'+floor)['data'] and rec['data']['shear_wall_detail']['input']==inputs[floor]['shear_wall_detail']['input']
  vals=[r for r in effective if r.get('member_code')=='SW-'+floor];totals[floor]=str(sum((Decimal(str(q['amount'])) for r in vals for q in r['quantities'] if q['code']=='shear_wall_concrete'),Decimal(0)))
 assert totals=={'L1':'3.5','L2':'3.5','L3':'4.25','L4':'3.5','L5':'3.5'}
 documents={str(p):sha256(p.read_bytes()).hexdigest() for p in (out/'documents').rglob('*') if p.is_file()}
 result={'explicitly_synthetic':True,'previous_boq_rows':63,'boq_rows':len(after['boq']),'previous_amendments':5,'amendments':len(after['beam_amendments']),'old_data_preserved':True,'sqlite_integrity':'ok','net_concrete_by_floor_m3':totals,'total_net_concrete_m3':str(sum(map(Decimal,totals.values()))),'new_amendment_id':am['id'],'documents':documents,'new_wall_count':5,'unsupported':'اشتراک با تیر، ستون، پی، شناژ و رکوردهای سازه‌ای قدیمی فاقد قرارداد مختصات مسدود است'}
 (out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));b.store.close();return result

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True);p.add_argument('--output',required=True);args=p.parse_args();print(json.dumps(verify(args.reference,args.output),ensure_ascii=False,indent=2))
