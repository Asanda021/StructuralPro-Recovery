"""Extend saved package-two DB; explicit synthetic horizontal insulation only."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json,shutil,sys,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from core.platform.application import StructuralProApp
from core.reports.architecture_detail_report import export_project,export
from core.commercial.exact_values import exact
from test_insulation_specialist_work import sample

@exact
def extend_sample(reference,out):
 reference=Path(reference).resolve();out=Path(out).resolve()
 if not (reference/'package1/db').is_dir() or not (reference/'scenario.json').is_file():raise ValueError('سناریوی ذخیره‌شده بسته دوم لازم است')
 if out.exists():raise ValueError('مقصد جدید لازم است؛ بازنویسی ممنوع')
 out.mkdir();shutil.copytree(reference,out/'package2');docs=out/'documents';docs.mkdir();app=StructuralProApp(out/'package2/package1/db');pid='ARCH-5';previous=deepcopy(app.open_project(pid));inputs={};documents={}
 def comparable(rows):return {r['source_id']:{k:v for k,v in r.items() if k!='item_no'} for r in rows}
 previous_boq=comparable(previous['boq']);families={1:'waterproofing',2:'thermal_insulation',3:'thermal_insulation',4:'acoustic_insulation',5:'waterproofing'}
 for i,kind in families.items():
  floor='L'+str(i);d=sample(kind);old=app.get_aec_system(pid,'floor_finish',floor,'F-'+floor)['data'];d.update(floor_id=floor,system_id='I-'+floor,axis=old['axis']);d['source']['source_id']='SYNTHETIC-INSULATION-'+floor;a=d['architecture_detail'];a['geometry']=deepcopy(old['architecture_detail']['geometry']);a['geometry'].update(installation_plane='horizontal',installation_ref='سطح افقی مستند بالای لایه‌های کف همان طبقه؛ مصنوعی')
  shift=Decimal('.16') if i==3 else Decimal('.15')
  for p in a['layers']:p['bottom_m']=str(Decimal(p['bottom_m'])+shift)
  doc=docs/(floor+'-insulation.txt');doc.write_text('EXPLICIT SYNTHETIC SOFTWARE TEST ONLY. '+floor+' '+kind+'\nHorizontal 5 x 4 m, one 1 x 1 m opening at (1,1). Above saved floor stratum; region identity reused explicitly.\nEach layer has its own entered elevation, thickness, material and source; no purchase, rolls, strips, returns or prices.\n'+json.dumps(a,ensure_ascii=False,indent=2));documents[str(doc)]=sha256(doc.read_bytes()).hexdigest();d['source'].update(plan_ref=str(doc),detail_ref='مصنوعی؛ SHA-256: '+documents[str(doc)]);a['geometry']['source_ref']=str(doc)
  mapping={p['id']:'I-'+floor+'-'+p['id'] for name in ('openings','layers') for p in a[name]}
  for name in ('openings','layers'):
   for p in a[name]:
    p.update(id=mapping[p['id']],physical_key='I-'+floor+'-'+p['physical_key'],source_ref=str(doc))
    if 'layer_key' in p:p['layer_key']='I-'+floor+'-'+p['layer_key']
    if p.get('opening_ids'):p['opening_ids']='|'.join(mapping[j] for j in p['opening_ids'].split('|'))
  inputs[floor]=deepcopy(d);app.save_aec_system_draft(pid,d,expected_revision=0);app.review_roof_system(pid,kind,floor,d['system_id'],expected_revision=1,reviewer='بازبین مستقل',note='کنترل هم‌پوشانی مشترک عایق و کف');app.commit_aec_system(pid,kind,floor,d['system_id'],expected_revision=2)
 before=deepcopy(app.open_project(pid));d=deepcopy(app.get_aec_system(pid,'thermal_insulation','L3','I-L3')['data']);d.pop('roof_review');d['architecture_detail']['layers'][1]['thickness_m']='.05';d['architecture_detail']['layers'][2]['bottom_m']='.31'
 doc=docs/'L3-insulation-revision.txt';doc.write_text('EXPLICIT SYNTHETIC: L3 thermal second layer thickness .04 -> .05 m; third bottom .30 -> .31 m. Original floors/walls unchanged.');documents[str(doc)]=sha256(doc.read_bytes()).hexdigest()
 am=app.create_roof_amendment(pid,'thermal_insulation','L3','I-L3',d,expected_revision=2,created_by='تهیه‌کننده',reason='اصلاح عایق فقط طبقه سوم؛ مصنوعی',evidence=dict(evidence_path=str(doc),evidence_sha256=documents[str(doc)],evidence_reference='مدرک مستقل مصنوعی'))
 app.review_beam_amendment(pid,am['id'],expected_revision=1,reviewer='بازبین مستقل دوم',note='حفظ چهار طبقه دیگر و تمام کف و دیوار');app.apply_beam_amendment(pid,am['id'],expected_revision=1);after=app.open_project(pid)
 assert after['takeoffs']==before['takeoffs'];assert all(after['reviewed_aec_systems'][k]==v for k,v in previous['reviewed_aec_systems'].items());assert comparable([r for r in after['boq'] if r['source_id'] in previous_boq])==previous_boq
 for i in (1,2,4,5):
  marker='aec:'+families[i]+':L'+str(i)+':'
  assert comparable([r for r in before['boq'] if r['source_id'].startswith(marker)])==comparable([r for r in after['boq'] if r['source_id'].startswith(marker)])
 totals={}
 for r in after['boq']:
  if not any(r['source_id'].startswith('aec:'+k+':') for k in families.values()):continue
  key=r['item_code']+'|'+r['unit'];totals[key]=totals.get(key,Decimal(0))+Decimal(str(r['quantity']))
 assert totals=={'membrane_layer|m2':Decimal('114'),'thermal_layer|m3':Decimal('5.51'),'thermal_layer|m2':Decimal('38'),'acoustic_layer|m3':Decimal('2.66'),'acoustic_layer|m2':Decimal('19')}
 assert len(after['boq'])==43 and len({r['source_id'] for r in after['boq']})==43
 for fmt in ('pdf','xlsx','docx','csv'):export(app,pid,'thermal_insulation','L3','I-L3',out/('insulation.'+fmt),format=fmt)
 export_project(app,pid,out/'all_architecture.csv',format='csv')
 for i in range(1,6):export_project(app,pid,out/('architecture_L'+str(i)+'.csv'),format='csv',floor='L'+str(i))
 (out/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2))
 result=dict(synthetic=True,project_id=pid,reference_directory=str(reference),previous_records_preserved=True,previous_boq_preserved=True,previous_amendments_preserved=True,other_four_floor_quantities_unchanged=True,original_takeoffs_preserved=True,floors=5,boq_rows=43,insulation_effective_totals={k:str(v) for k,v in totals.items()},insulation_amendment_id=am['id'],insulation_amendment_delta_m3='.19',documents=documents,blocked_operations=['roll/strip layout and laps','returns and vertical insulation','liquid consumption','sloping roof layers','facade and dry fixings','specialist doors/windows','unfinished package2 ceramic stone paint skirting ceiling'],sqlite_integrity=app.store.db.execute('pragma integrity_check').fetchone()[0]);app.store.close();reopened=StructuralProApp(out/'package2/package1/db');assert reopened.get_aec_system(pid,'thermal_insulation','L3','I-L3')['revision']==3;assert reopened.get_aec_system(pid,'floor_finish','L3','F-L3')['revision']==3;assert reopened.get_aec_system(pid,'block_wall','L3','W-L3')['revision']==3;reopened.store.close();(out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference-dir',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);args=p.parse_args();print(json.dumps(extend_sample(args.reference_dir,args.output_dir),ensure_ascii=False,indent=2))
