"""Create a reproducible, explicitly synthetic FIVE-floor package-one acceptance.

No price, waste, wall reinforcement or unsupported finish is manufactured.
The other Step 6 packages remain explicitly outside this scenario's acceptance.
"""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_architecture_specialist_work import sample,with_openings
from core.platform.application import StructuralProApp
from core.reports.architecture_detail_report import export_project
from core.commercial.exact_values import exact

@exact
def create_sample(out):
 out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
 if (out/'db').exists():raise ValueError('پوشه نمونه باید جدید باشد؛ بازنویسی ممنوع است')
 docs=out/'documents';docs.mkdir();app=StructuralProApp(out/'db');app.create_project('ساختمان پنج‌طبقه؛ صرفاً داده مصنوعی و آزمون نرم‌افزاری','ARCH-5');inputs={};documents={}
 for i in range(1,6):
  floor='L'+str(i);d=with_openings() if i==1 else sample();d['floor_id']=floor;d['system_id']='W-'+floor;d['axis']='اتاق مصنوعی مستقل طبقه '+str(i);d['source']['source_id']='SYNTHETIC-WALL-'+floor
  doc=docs/(floor+'.txt');doc.write_text('EXPLICIT SYNTHETIC SOFTWARE FIXTURE; NOT A DESIGN OR REAL PROJECT.\nFloor '+floor+'; rectangular wall 3.9 x 2.9 x 0.2 m.\nActual unit envelope .9 x .9 x .2 m; full external head/bed joint .1 m.\nEntered layouts only. No waste/price/material recipe.\nInside base .02 m, white .005 m; outside cement .015 m.\n'+('Two explicit .9 x .9 m openings at (0,0),(2,1).\n' if i==1 else 'No openings.\n'),encoding='utf-8');documents[str(doc)]=sha256(doc.read_bytes()).hexdigest()
  d['source'].update(plan_ref=str(doc),detail_ref='مصنوعی؛ SHA-256: '+documents[str(doc)]);a=d['architecture_detail'];a['geometry'].update(physical_wall_id='SYNTHETIC-PHYSICAL-'+floor,source_ref=str(doc),repeat_ref='یک دیوار مستقل همین طبقه')
  replacements={p['id']:floor+'-'+p['id'] for name in ('openings','masonry_layers','unit_regions','surfaces') for p in a[name]}
  for name in ('openings','masonry_layers','unit_regions','surfaces'):
   for p in a[name]:
    p.update(id=replacements[p['id']],physical_key=floor+'-'+p['physical_key'],source_ref=str(doc))
    if 'layer_id' in p:p['layer_id']=replacements[p['layer_id']]
    if 'surface_id' in p:p['surface_id']=floor+'-'+p['surface_id']
    if p.get('opening_ids'):p['opening_ids']='|'.join(replacements[j] for j in p['opening_ids'].split('|'))
  a['surfaces'][0]['payment_unit']='m3';inputs[floor]=deepcopy(d)
  app.save_aec_system_draft('ARCH-5',d,expected_revision=0);app.review_roof_system('ARCH-5','block_wall',floor,d['system_id'],expected_revision=1,reviewer='بازبین مستقل نمونه مصنوعی',note='کنترل جانمایی و وجه مستقل مصنوعی');app.commit_aec_system('ARCH-5','block_wall',floor,d['system_id'],expected_revision=2)
 before=deepcopy(app.open_project('ARCH-5'));old_boq=deepcopy(before['boq']);floor='L3';sid='W-L3';d=deepcopy(app.get_aec_system('ARCH-5','block_wall',floor,sid)['data']);d.pop('roof_review');d['architecture_detail']['surfaces'][0]['thickness_m']='.03'
 evidence=docs/'L3-revision.txt';evidence.write_text('EXPLICIT SYNTHETIC revision: only inside base plaster thickness .02 -> .03 m in L3. No other floor or material changed.');documents[str(evidence)]=sha256(evidence.read_bytes()).hexdigest()
 am=app.create_roof_amendment('ARCH-5','block_wall',floor,sid,d,expected_revision=2,created_by='تهیه‌کننده مصنوعی',reason='تغییر مستند ضخامت اندود داخلی فقط طبقه سوم',evidence=dict(evidence_path=str(evidence),evidence_sha256=documents[str(evidence)],evidence_reference='مدرک اصلاحی مستقل و کاملاً مصنوعی'))
 app.review_beam_amendment('ARCH-5',am['id'],expected_revision=1,reviewer='بازبین مستقل دوم',note='کنترل اختلاف و عدم تغییر چهار طبقه دیگر');app.apply_beam_amendment('ARCH-5',am['id'],expected_revision=1)
 after=app.open_project('ARCH-5');assert after['takeoffs']==before['takeoffs']
 for i in (1,2,4,5):
  marker=':L'+str(i)+':'
  # Rebuilding may renumber rows; every physical, financial and quantity field must stay identical.
  def unchanged(rows):return {r['source_id']:{k:v for k,v in r.items() if k!='item_no'} for r in rows if marker in r['source_id']}
  assert unchanged(old_boq)==unchanged(after['boq'])
 totals={}
 for row in after['boq']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
 assert totals=={'masonry_work':Decimal('54.93'),'base_plaster':Decimal('1.2117'),'white_plaster':Decimal('54.93'),'cement_render':Decimal('54.93')}
 assert len(after['boq'])==20 and len({r['source_id'] for r in after['boq']})==20
 for fmt in ('pdf','xlsx','docx','csv'):export_project(app,'ARCH-5',out/('five_floors.'+fmt),format=fmt)
 for i in range(1,6):export_project(app,'ARCH-5',out/('floor_L'+str(i)+'.csv'),format='csv',floor='L'+str(i))
 (out/'inputs.json').write_text(json.dumps(inputs,ensure_ascii=False,indent=2),encoding='utf-8')
 result=dict(synthetic=True,scope='package1 rectangular masonry and independently measured plaster only',project_id='ARCH-5',floors=5,boq_rows=20,effective_totals={k:str(v) for k,v in totals.items()},amendment_id=am['id'],amendment_delta_m3='.1131',other_four_floors_unchanged=True,originals_unchanged=True,document_sha256=documents,blocked=['paint','floor layers','ceramic cut layouts','waterproofing','suspended ceiling','facade','wall reinforcement and connectors'],database_integrity=app.store.db.execute('pragma integrity_check').fetchone()[0])
 app.store.close();reopened=StructuralProApp(out/'db');assert reopened.get_aec_system('ARCH-5','block_wall','L3','W-L3')['revision']==3;reopened.store.close()
 (out/'scenario.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');return result
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',required=True,type=Path);args=parser.parse_args();print(json.dumps(create_sample(args.output_dir),ensure_ascii=False,indent=2))
