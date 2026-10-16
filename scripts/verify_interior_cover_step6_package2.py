"""Continue saved wall/floor/insulation scenario with explicit coverings/skirting."""
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json,shutil,sys,argparse
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from core.platform.application import StructuralProApp
from core.reports.architecture_detail_report import export,export_project
from core.commercial.exact_values import exact
from test_cover_specialist_work import sample as cover_sample
from test_skirting_specialist_work import sample as skirt_sample
from test_architecture_specialist_work import obj

@exact
def extend_sample(reference,out):
 reference=Path(reference).resolve();out=Path(out).resolve()
 if not (reference/'package2/package1/db').is_dir() or not (reference/'scenario.json').is_file():raise ValueError('سناریوی ذخیره‌شده دیوار، کف و عایق لازم است')
 if out.exists():raise ValueError('مقصد جدید لازم است؛ بازنویسی ممنوع')
 out.mkdir();shutil.copytree(reference,out/'previous');docs=out/'documents';docs.mkdir();app=StructuralProApp(out/'previous/package2/package1/db');pid='ARCH-5';previous=deepcopy(app.open_project(pid));inputs={};documents={};families={}
 def comparable(rows):return {r['source_id']:{k:v for k,v in r.items() if k!='item_no'} for r in rows}
 old_boq=comparable(previous['boq'])
 def add(d,label):
  a=d['architecture_detail'];floor=d['floor_id'];doc=docs/(floor+'-'+label+'.txt');doc.write_text('EXPLICIT SYNTHETIC SOFTWARE TEST ONLY. No engineering approval, price, guessed waste or automatic item.\n'+json.dumps(d,ensure_ascii=False,indent=2));documents[str(doc)]=sha256(doc.read_bytes()).hexdigest();d['source'].update(source_id='SYNTHETIC-'+floor+'-'+label,plan_ref=str(doc),detail_ref='مدرک مصنوعی؛ SHA-256: '+documents[str(doc)]);a['geometry']['source_ref']=str(doc)
  mapping={p['id']:floor+'-'+label+'-'+p['id'] for v in a.values() if isinstance(v,list) for p in v}
  for v in a.values():
   if not isinstance(v,list):continue
   for p in v:
    p.update(id=mapping[p['id']],physical_key=floor+'-'+label+'-'+p['physical_key'],source_ref=str(doc))
    for key in ('surface_id','stock_id','run_id'):
     if p.get(key):p[key]=mapping[p[key]]
    if p.get('opening_ids'):p['opening_ids']='|'.join(mapping[j] for j in p['opening_ids'].split('|'))
  inputs[floor+'-'+label]=deepcopy(d);app.save_aec_system_draft(pid,d,expected_revision=0);app.review_roof_system(pid,d['kind'],floor,d['system_id'],expected_revision=1,reviewer='بازبین مستقل',note='کنترل نرم‌افزاری مصنوعی؛ منبع و هندسه');app.commit_aec_system(pid,d['kind'],floor,d['system_id'],expected_revision=2)
 for i in range(1,6):
  floor='L'+str(i);old_floor=app.get_aec_system(pid,'floor_finish',floor,'F-'+floor)['data'];old_wall=app.get_aec_system(pid,'block_wall',floor,'W-'+floor)['data'];kind='stone_floor' if i in (2,4) else 'ceramic_finish';families[floor]=kind;d=cover_sample(kind);d.update(floor_id=floor,system_id='C-'+floor,axis=old_floor['axis']);a=d['architecture_detail'];g=a['geometry'];g.update(physical_surface_id='COVER-FLOOR-'+floor,host_id=old_floor['architecture_detail']['geometry']['physical_region_id'],space_id='ROOM-'+floor,length_m='5',width_m='4');a['openings']=[obj('H1',x='1',y='1',width_m='1',height_m='1')];a['surfaces'][0].update(width_m='5',height_m='4',layout_ref='چهار قطعه مستقل حول بازشو؛ خرید و برش مصنوعی مستند');a['stocks']=[];a['pieces']=[]
  for j,(x,y,w,h,stock_length) in enumerate([('0','0','5','1','6'),('0','1','1','1','1'),('2','1','3','1','3'),('0','2','5','2','5')],1):
   a['stocks'].append(obj('ST'+str(j),length_m=stock_length,width_m=h,material_ref=a['surfaces'][0]['material_ref']));a['pieces'].append(obj('P'+str(j),surface_id='LAYER',stock_id='ST'+str(j),piece_type='cut' if j==1 else 'full',x=x,y=y,width_m=w,height_m=h,stock_x='0',stock_y='0',cut_ref='دیتایل مصنوعی قطعه '+str(j)))
  add(d,'floor-cover')
  wall_kind='ceramic_finish' if i in (2,5) else 'stone_cladding';d=cover_sample(wall_kind);d.update(floor_id=floor,system_id='CW-'+floor,axis=old_wall['axis']);a=d['architecture_detail'];wg=old_wall['architecture_detail']['geometry'];face=next(p for p in old_wall['architecture_detail']['surfaces'] if p['face']=='outside');a['geometry'].update(physical_surface_id=face['surface_id'],host_id=wg['physical_wall_id'],space_id='ROOM-'+floor,face='outside',plane='vertical',length_m=wg['length_m'],width_m=wg['height_m']);a['openings']=[{k:v for k,v in p.items() if k!='penetration'} for p in old_wall['architecture_detail']['openings']];a['surfaces'][0].update(width_m=wg['length_m'],height_m=wg['height_m'],opening_ids='|'.join(p['id'] for p in a['openings']),layout_status='area_only',layout_ref='فقط مساحت مستند؛ چیدمان و خرید قطعات نامعلوم');a['stocks']=[];a['pieces']=[];add(d,'wall-cover')
  d=skirt_sample();d.update(floor_id=floor,system_id='K-'+floor,axis=old_floor['axis']);d['architecture_detail']['geometry'].update(physical_space_id='SKIRT-'+floor,space_id='ROOM-'+floor);add(d,'skirting')
 before=deepcopy(app.open_project(pid));kind=families['L3'];d=deepcopy(app.get_aec_system(pid,kind,'L3','C-L3')['data']);d.pop('roof_review');a=d['architecture_detail'];a['surfaces'][0].update(width_m='4.75',coverage_scope='partial',scope_ref='حذف مستند نوار انتهایی عرض ۰٫۲۵ متر',layout_status='area_only',layout_ref='طرح قطعات جدید تعیین نشده؛ فقط سطح مستند');a['stocks']=[];a['pieces']=[]
 doc=docs/'L3-cover-revision.txt';doc.write_text('EXPLICIT SYNTHETIC: L3 floor cover width 5 -> 4.75 m with same full 1 m2 opening; net area 19 -> 18 m2. Other floors and prior wall/floor/insulation unchanged. New purchase layout unknown.');documents[str(doc)]=sha256(doc.read_bytes()).hexdigest();am=app.create_roof_amendment(pid,kind,'L3','C-L3',d,expected_revision=2,created_by='تهیه‌کننده',reason='کاهش مستند سطح پوشش فقط طبقه سوم؛ مصنوعی',evidence=dict(evidence_path=str(doc),evidence_sha256=documents[str(doc)],evidence_reference='دیتایل جدید مصنوعی'))
 app.review_beam_amendment(pid,am['id'],expected_revision=1,reviewer='بازبین مستقل دوم',note='کنترل اختلاف و حفظ تمام سوابق قبلی');app.apply_beam_amendment(pid,am['id'],expected_revision=1);after=app.open_project(pid)
 assert after['takeoffs']==before['takeoffs'];assert all(after['reviewed_aec_systems'][k]==v for k,v in previous['reviewed_aec_systems'].items());assert comparable([r for r in after['boq'] if r['source_id'] in old_boq])==old_boq
 for i in (1,2,4,5):
  floor='L'+str(i);old=comparable([r for r in before['boq'] if r['source_id'].startswith('aec:') and r['source_id'].split(':')[2]==floor]);new=comparable([r for r in after['boq'] if r['source_id'].startswith('aec:') and r['source_id'].split(':')[2]==floor]);assert old==new
 floor_area=wall_area=skirt_length=Decimal(0)
 for r in after['boq']:
  if any(':C-L'+str(i)+':' in r['source_id'] for i in range(1,6)):floor_area+=Decimal(str(r['quantity']))
  if any(':CW-L'+str(i)+':' in r['source_id'] for i in range(1,6)):wall_area+=Decimal(str(r['quantity']))
  if r['item_code']=='skirting_work':skirt_length+=Decimal(str(r['quantity']))
 assert floor_area==94 and wall_area==Decimal('54.93') and skirt_length==20;assert len(after['boq'])==58 and len({r['source_id'] for r in after['boq']})==58
 for fmt in ('pdf','xlsx','docx','csv'):
  export(app,pid,'ceramic_finish','L1','C-L1',out/('cover.'+fmt),format=fmt);export(app,pid,'floor_finish','L3','K-L3',out/('skirting.'+fmt),format=fmt)
 export_project(app,pid,out/'all_architecture.csv',format='csv')
 for i in range(1,6):export_project(app,pid,out/('architecture_L'+str(i)+'.csv'),format='csv',floor='L'+str(i))
 (out/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2));result=dict(synthetic=True,project_id=pid,reference_directory=str(reference),previous_records_preserved=True,previous_boq_preserved=True,previous_amendments_preserved=True,other_four_floor_quantities_unchanged=True,original_takeoffs_preserved=True,floors=5,boq_rows=58,cover_floor_area_m2=str(floor_area),cover_wall_area_m2=str(wall_area),skirting_length_m=str(skirt_length),amendment_id=am['id'],amendment_delta_m2='-1',documents=documents,blocked_operations=['irregular/rotated cuts and stairs','paint and putty specialist','suspended ceiling specialist','package3 unfinished roof/facade work'],sqlite_integrity=app.store.db.execute('pragma integrity_check').fetchone()[0]);app.store.close();reopened=StructuralProApp(out/'previous/package2/package1/db');assert reopened.get_aec_system(pid,kind,'L3','C-L3')['revision']==3;assert reopened.get_aec_system(pid,'thermal_insulation','L3','I-L3')['revision']==3;reopened.store.close();(out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference-dir',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);args=p.parse_args();print(json.dumps(extend_sample(args.reference_dir,args.output_dir),ensure_ascii=False,indent=2))
