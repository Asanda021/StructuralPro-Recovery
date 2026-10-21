"""Extend a real saved package-one synthetic scenario, never rebuild it in place."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json,shutil,sys,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from core.platform.application import StructuralProApp
from core.reports.architecture_detail_report import export_project
from core.commercial.exact_values import exact
from test_floor_specialist_work import sample

@exact
def extend_sample(reference,out):
 reference=Path(reference).resolve();out=Path(out).resolve()
 if not (reference/'db').is_dir() or not (reference/'scenario.json').is_file():raise ValueError('سناریوی ذخیره‌شده بسته اول لازم است')
 if out.exists():raise ValueError('مقصد باید جدید باشد؛ بازنویسی ممنوع است')
 out.mkdir();shutil.copytree(reference,out/'package1');docs=out/'documents';docs.mkdir();app=StructuralProApp(out/'package1/db');pid='ARCH-5';previous=deepcopy(app.open_project(pid));inputs={};documents={}
 def comparable(rows):return {r['source_id']:{k:v for k,v in r.items() if k!='item_no'} for r in rows}
 previous_wall=comparable(previous['boq'])
 for i in range(1,6):
  floor='L'+str(i);d=sample();d.update(floor_id=floor,system_id='F-'+floor,axis='اتاق مصنوعی مستقل طبقه '+str(i));d['source']['source_id']='SYNTHETIC-FLOOR-'+floor;a=d['architecture_detail'];a['geometry'].update(physical_region_id='SYNTHETIC-FLOOR-REGION-'+floor,space_id='ROOM-'+floor,repeat_ref='یک ناحیه مستقل همین طبقه')
  doc=docs/(floor+'-floor.txt');doc.write_text('EXPLICIT SYNTHETIC SOFTWARE TEST ONLY.\nFloor '+floor+'; region 5 x 4 m, base level -1.2 m.\nOne 1 x 1 m opening at (1,1) through all layers.\nFill bottom 0 thickness .1 m; screed bottom .1 thickness .04 m; protection bottom .14 thickness .01 m.\nScreed purchase 1.1 m3 per region from synthetic independent procurement document. No waste or price inferred.\n');documents[str(doc)]=sha256(doc.read_bytes()).hexdigest();d['source'].update(plan_ref=str(doc),detail_ref='مدرک مصنوعی؛ SHA-256: '+documents[str(doc)]);a['geometry']['source_ref']=str(doc)
  mapping={p['id']:floor+'-'+p['id'] for name in ('openings','layers') for p in a[name]}
  for name in ('openings','layers'):
   for p in a[name]:
    p.update(id=mapping[p['id']],physical_key=floor+'-'+p['physical_key'],source_ref=str(doc))
    if 'layer_key' in p:p['layer_key']=floor+'-'+p['layer_key']
    if p.get('opening_ids'):p['opening_ids']='|'.join(mapping[j] for j in p['opening_ids'].split('|'))
  a['layers'][1].update(purchase_quantity='1.1',purchase_unit='m3',purchase_ref='خرید مستقل هر ناحیه؛ مدرک مصنوعی '+str(doc));inputs[floor]=deepcopy(d)
  app.save_aec_system_draft(pid,d,expected_revision=0);app.review_roof_system(pid,'floor_finish',floor,d['system_id'],expected_revision=1,reviewer='بازبین مستقل',note='کنترل ناحیه، لایه و کسورات');app.commit_aec_system(pid,'floor_finish',floor,d['system_id'],expected_revision=2)
 before=deepcopy(app.open_project(pid));d=deepcopy(app.get_aec_system(pid,'floor_finish','L3','F-L3')['data']);d.pop('roof_review');d['architecture_detail']['layers'][1]['thickness_m']='.05';d['architecture_detail']['layers'][2]['bottom_m']='.15'
 doc=docs/'L3-floor-revision.txt';doc.write_text('EXPLICIT SYNTHETIC: L3 screed thickness .04 -> .05 m, protective layer bottom .14 -> .15 m; no other quantity changes.');documents[str(doc)]=sha256(doc.read_bytes()).hexdigest()
 am=app.create_roof_amendment(pid,'floor_finish','L3','F-L3',d,expected_revision=2,created_by='تهیه‌کننده',reason='اصلاح مستند کف فقط طبقه سوم',evidence=dict(evidence_path=str(doc),evidence_sha256=documents[str(doc)],evidence_reference='مدرک اصلاحی مصنوعی کف'))
 app.review_beam_amendment(pid,am['id'],expected_revision=1,reviewer='بازبین مستقل دوم',note='کنترل اختلاف و حفظ سایر طبقات');app.apply_beam_amendment(pid,am['id'],expected_revision=1);after=app.open_project(pid)
 assert after['takeoffs']==before['takeoffs'];assert all(after['reviewed_aec_systems'][k]==v for k,v in previous['reviewed_aec_systems'].items());assert comparable([r for r in after['boq'] if r['source_id'] in previous_wall])==previous_wall
 for i in (1,2,4,5):
  marker='aec:floor_finish:L'+str(i)+':'
  assert comparable([r for r in before['boq'] if r['source_id'].startswith(marker)])==comparable([r for r in after['boq'] if r['source_id'].startswith(marker)])
 totals={}
 for r in after['boq']:
  if not r['source_id'].startswith('aec:floor_finish:'):continue
  totals[r['item_code']]=totals.get(r['item_code'],Decimal(0))+Decimal(str(r['quantity']))
 assert totals=={'floor_fill':Decimal('9.5'),'floor_screed':Decimal('3.99'),'floor_protection':Decimal('95')};assert len(after['boq'])==35 and len({r['source_id'] for r in after['boq']})==35
 for fmt in ('pdf','xlsx','docx','csv'):export_project(app,pid,out/('floors.'+fmt),format=fmt,family='floor_finish')
 export_project(app,pid,out/'all_architecture.csv',format='csv')
 for i in range(1,6):export_project(app,pid,out/('floor_L'+str(i)+'.csv'),format='csv',floor='L'+str(i),family='floor_finish')
 (out/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2))
 result=dict(synthetic=True,project_id=pid,reference_directory=str(reference),previous_wall_records_preserved=True,previous_wall_boq_preserved=True,previous_wall_amendment_preserved=True,other_four_floor_quantities_unchanged=True,original_takeoffs_preserved=True,floors=5,boq_rows=35,floor_effective_totals={k:str(v) for k,v in totals.items()},floor_amendment_id=am['id'],floor_amendment_delta_m3='.19',documents=documents,blocked_operations=['ceramic layouts','stone and stair parts','skirting','paint coats','suspended ceiling','waterproofing'],sqlite_integrity=app.store.db.execute('pragma integrity_check').fetchone()[0]);app.store.close();reopened=StructuralProApp(out/'package1/db');assert reopened.get_aec_system(pid,'floor_finish','L3','F-L3')['revision']==3;assert reopened.get_aec_system(pid,'block_wall','L3','W-L3')['revision']==3;reopened.store.close();(out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference-dir',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);args=p.parse_args();print(json.dumps(extend_sample(args.reference_dir,args.output_dir),ensure_ascii=False,indent=2))
