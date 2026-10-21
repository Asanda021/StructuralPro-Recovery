"""Explicit local schedules and independent analytic quantities, synthetic only."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import pytest
from core.platform.application import StructuralProApp
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point
from core.drawings.roof_region import bind_source,detail_payload
from test_phase2_pdf_roof import fixture
from test_roof_specialist_work import sample,KINDS
L=[[0,0],[4,0],[4,2],[2,2],[2,4],[0,4]]
FRAME={'origin_pdf':['200','100'],'axis_x':['.8','.6'],'source_ref':'explicit synthetic 3-4-5 survey frame','approved_by':'synthetic frame reviewer'}


def planar_sample(kind,outer=L):
 d=sample(kind);rd=d['roof_detail'];g=rd['geometry'];g.update(shape='documented_planar',planar={'policy':'roof_planar_partition_v1','outer':outer})
 if kind=='solid_slab':rd['regions'][0]['footprint']=outer
 else:
  rd['regions'][0]['footprint']=outer
  rd['regions']=[rd['regions'][0]]+[p for p in rd['regions'][1:]]
  for p in rd['regions']:
   if p['id'] in ('R1','P1','V1'):p['length']='2'
  rd['joist_layout'][1]['length']='2'
  for j in rd['joist_layout']:j.update(physical_key='PH-'+j['id'],run_id='RUN-'+j['id'],span_ref='explicit synthetic installed span')
  rd['pieces'][1].update(count='1',nx='1')
  for p in rd['pieces']:p['physical_key']='PH-'+p['id']
 rd['formwork']['faces'][0].update(footprint=outer)
 return d


def bound_planar(tmp_path,kind,outer=L):
 app,_,_,_=fixture(tmp_path,kind);app.add_project_floor('P','مصنوعی',level='L1');app.add_project_member('P','S1','L1','سقف')
 s=DrawingTakeoffSession(str(tmp_path/'plan.pdf'));s.calibrate(1,50,1)
 pts=[(200+(Decimal(str(x))*Decimal('.8')-Decimal(str(y))*Decimal('.6'))*50,100+(Decimal(str(x))*Decimal('.6')+Decimal(str(y))*Decimal('.8'))*50) for x,y in outer]
 item=s.add_polygon([Point(float(x),float(y)) for x,y in pts],topology='exact_planar_region_v2',source='explicit synthetic rotated L',floor_id='L1',member_id='S1',quantity_owner='explicit synthetic owner')
 rec=app.save_drawing_takeoff_session('P',s);record=app.load_drawing_takeoff_session('P',rec['session_id'])
 d=planar_sample(kind,outer);d['source']=bind_source(record,item.id,local_frame=FRAME)
 d['source'].update(plan_ref='explicit synthetic plan',detail_ref='explicit synthetic schedule')
 path=tmp_path/'detail.json';path.write_text(json.dumps(detail_payload(d),ensure_ascii=False));d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 return app,s,item,rec,d

@pytest.mark.parametrize('kind',KINDS)
def test_three_planar_roofs_exact_oracle_sqlite_review_and_boq(tmp_path,kind):
 app,_,_,_,d=bound_planar(tmp_path,kind)
 app.save_aec_system_draft('P',d,expected_revision=0);r=app.preview_aec_system('P',kind,'L1','S1');assert r['ready'],r['blockers']
 totals={}
 for row in r['rows']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
 assert totals['concrete']==Decimal('2.4' if kind=='solid_slab' else '.78')
 assert totals['formwork']==12 and totals['rebar']==Decimal('71.040')
 if kind!='solid_slab':assert totals['joists']==2 and totals['blocks' if kind=='joist_block' else 'foam']==3 and totals['precast_concrete']==Decimal('.06')
 app.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='independent synthetic reviewer',note='analytical local quantities')
 app.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
 p=deepcopy(app.open_project('P'));assert p['boq'];assert not any(r['item_code']=='precast_concrete' for r in p['boq'])
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==p;app.store.close()

@pytest.mark.parametrize('fault',['frame','partition','outside','pieces','span','joist','unit'])
def test_planar_roof_missing_or_changed_detail_is_failclosed(tmp_path,fault):
 app,_,_,_,d=bound_planar(tmp_path,'joist_block');before=deepcopy(app.open_project('P'))
 if fault=='frame':d['source']['roof_binding']['local_frame']['axis_x']=['.7','.6']
 if fault=='partition':d['roof_detail']['regions'].pop()
 if fault=='outside':d['roof_detail']['regions'][1]['x']='3.9'
 if fault=='pieces':d['roof_detail']['pieces'][1]['count']='2'
 if fault=='span':d['roof_detail']['joist_layout'][1].pop('span_ref')
 if fault=='joist':d['roof_detail']['joist_layout'][1]['length']='4'
 if fault=='unit':d['roof_detail']['geometry']['unit']='cm'
 # Bind changed schedule bytes too, so rejection tests engineering, not only hash.
 path=tmp_path/'bad-detail.json';path.write_text(json.dumps(detail_payload(d)));d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 from core.takeoff.reviewed_aec import preview_system
 assert not preview_system(d,app.takeoff)['ready']
 assert app.open_project('P')==before;app.store.close()


def test_independent_slab_thickness_zones_are_not_bounding_box_volume(tmp_path):
 app,_,_,_,d=bound_planar(tmp_path,'solid_slab');rd=d['roof_detail'];g=rd['geometry'];g['depth']='.3'
 def part(i,x,y,l,w,h):return {'id':i,'component':'concrete','x':str(x),'y':str(y),'z':'0','length':str(l),'width':str(w),'height':str(h),'source_ref':'explicit synthetic zone','approved_by':'synthetic independent checker'}
 rd['regions']=[part('C-low',0,0,4,2,'.2'),part('C-high',0,2,2,2,'.3')]
 g['planar']['thickness_zones']=[{'id':p['id'],'footprint':[[p['x'],p['y']],[str(Decimal(p['x'])+Decimal(p['length'])),p['y']],[str(Decimal(p['x'])+Decimal(p['length'])),str(Decimal(p['y'])+Decimal(p['width']))],[p['x'],str(Decimal(p['y'])+Decimal(p['width']))]],'depth':p['height'],'source_ref':p['source_ref'],'approved_by':p['approved_by']} for p in rd['regions']]
 path=tmp_path/'zone-detail.json';path.write_text(json.dumps(detail_payload(d)));d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 from core.takeoff.reviewed_aec import preview_system
 r=preview_system(d,app.takeoff);assert r['ready'],r['blockers']
 assert sum(Decimal(str(v['quantity'])) for v in r['rows'] if v['item_code']=='concrete')==Decimal('2.8')
 app.store.close()


def test_explicit_cut_foam_piece_uses_one_documented_stock_piece(tmp_path):
 outline=[[0,0],[4,0],[4,'1.5'],['3.5',2],[2,2],[2,4],[0,4]]
 app,_,_,_,d=bound_planar(tmp_path,'joist_foam',outline);rd=d['roof_detail']
 footprint=[[0,'.2'],[4,'.2'],[4,'1.5'],['3.5',2],[0,2]]
 next(p for p in rd['regions'] if p['id']=='V0')['footprint']=footprint
 rd['pieces'][0].update(count='1',nx='1',length='4',cut_footprint=footprint,cut_ref='explicit synthetic finished cut',approved_by='synthetic cut reviewer')
 path=tmp_path/'cut-detail.json';path.write_text(json.dumps(detail_payload(d)));d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 from core.takeoff.reviewed_aec import preview_system
 r=preview_system(d,app.takeoff);assert r['ready'],r['blockers']
 assert sum(Decimal(str(v['quantity'])) for v in r['rows'] if v['item_code']=='foam')==2
 assert sum(Decimal(str(v['quantity'])) for v in r['rows'] if v['item_code']=='concrete')==Decimal('.77375')
 app.store.close()


def test_legacy_rectangle_binding_cannot_silently_authorize_different_planar_area(tmp_path):
 from test_phase2_pdf_roof import bound
 from core.takeoff.reviewed_aec import preview_system
 app,_,_,_,old=bound(tmp_path,'solid_slab');d=planar_sample('solid_slab');d['source']=old['source']
 path=tmp_path/'mismatch-planar.json';path.write_text(json.dumps(detail_payload(d)));d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 assert not preview_system(d,app.takeoff)['ready'];app.store.close()


def test_planar_pdf_geometry_correction_preserves_roof_history_and_ownership(tmp_path):
 from core.drawings import roof_region as rr
 from core.drawings.takeoff_session import DrawingTakeoffSession
 assert hasattr(rr,'source_signature'),'missing explicit PDF revision mapping'
 app,s,item,r,d,original,proposal,evidence,new,points=prepared_geometry_revision(tmp_path)
 a=app.create_roof_amendment('P','solid_slab','L1','S1',proposal,expected_revision=2,created_by='author',reason='one explicit vertex changes area by 1 m2',evidence=evidence)
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='13 m2, 2.6 m3 oracle');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 after=deepcopy(app.open_project('P'));assert after['takeoffs']==original['takeoffs'] and after['reviewed_aec_systems']==original['reviewed_aec_systems']
 assert sum(Decimal(str(v['quantity'])) for v in after['boq'] if v['item_code']=='concrete')==Decimal('2.6')
 app.add_project_member('P','OTHER','L1','سقف')
 other=DrawingTakeoffSession(str(tmp_path/'plan.pdf'));other.calibrate(1,50,1)
 local=[('2.5','2.1'),('2.7','2.1'),('2.7','2.2'),('2.5','2.2')]
 pts=[Point(float(200+(Decimal(x)*Decimal('.8')-Decimal(y)*Decimal('.6'))*50),float(100+(Decimal(x)*Decimal('.6')+Decimal(y)*Decimal('.8'))*50)) for x,y in local]
 j=other.add_polygon(pts,topology='exact_planar_region_v2',floor_id='L1',member_id='OTHER',quantity_owner='explicit other owner',source='explicit synthetic overlap of amended area')
 rec=app.save_drawing_takeoff_session('P',other);snapshot=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rec['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==snapshot
 # The new paid measurement snapshot is as immutable as the original.
 s.edit_polygon(item.id,[(float(x+1),float(y)) for x,y in points])
 with pytest.raises(ValueError):app.save_drawing_takeoff_session('P',s,session_id=new['session_id'],expected_revision=1)
 app.store.close()


@pytest.mark.parametrize('building',['B1','B۱'])
def test_same_physical_part_on_another_page_is_not_paid_again(tmp_path,building):
 app,s,item,rec,d=bound_planar(tmp_path,'solid_slab');app.save_aec_system_draft('P',d,expected_revision=0)
 app.review_roof_system('P','solid_slab','L1','S1',expected_revision=1,reviewer='other',note='oracle');app.commit_aec_system('P','solid_slab','L1','S1',expected_revision=2)
 app.add_project_member('P','S2','L1','سقف')
 second=DrawingTakeoffSession(str(tmp_path/'plan.pdf'));second.calibrate(2,50,1);second.current_page=2
 j=second.add_polygon([Point(*p) for p in item.geometry],page=2,topology='exact_planar_region_v2',source='explicit other drawing',floor_id='L1',member_id='S2',quantity_owner='other explicit owner')
 r=app.save_drawing_takeoff_session('P',second);copy=planar_sample('solid_slab');copy['system_id']='S2';copy['building_id']=building
 copy['source']=bind_source(app.load_drawing_takeoff_session('P',r['session_id']),j.id,local_frame=FRAME);copy['source'].update(plan_ref='synthetic page 2',detail_ref='same claimed physical bar')
 path=tmp_path/'same-physical-part.json';path.write_text(json.dumps(detail_payload(copy)));copy['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.save_aec_system_draft('P',copy,expected_revision=0)
 assert app.open_project('P')==before;app.store.close()

def prepared_geometry_revision(tmp_path):
 from core.drawings import roof_region as rr
 app,s,item,r,d=bound_planar(tmp_path,'solid_slab')
 app.save_aec_system_draft('P',d,expected_revision=0);app.review_roof_system('P','solid_slab','L1','S1',expected_revision=1,reviewer='other',note='12 m2 oracle');app.commit_aec_system('P','solid_slab','L1','S1',expected_revision=2)
 original=deepcopy(app.open_project('P'))
 revised=[[0,0],[4,0],[4,2],[3,2],[2,4],[0,4]] # analytic area 13 m2
 points=[(200+(Decimal(str(x))*Decimal('.8')-Decimal(str(y))*Decimal('.6'))*50,100+(Decimal(str(x))*Decimal('.6')+Decimal(str(y))*Decimal('.8'))*50) for x,y in revised]
 s.edit_polygon(item.id,[(float(x),float(y)) for x,y in points]);new=app.save_drawing_takeoff_session('P',s)
 proposal=deepcopy(app.get_aec_system('P','solid_slab','L1','S1')['data']);proposal.pop('roof_review',None)
 proposal['source']=bind_source(app.load_drawing_takeoff_session('P',new['session_id']),item.id,local_frame=FRAME)
 proposal['source'].update(plan_ref=d['source']['plan_ref'],detail_ref=d['source']['detail_ref'])
 rd=proposal['roof_detail'];rd['geometry']['planar']['outer']=revised;rd['regions'][0]['footprint']=revised;rd['formwork']['faces'][0]['footprint']=revised
 rd['geometry_change']={'policy':'pdf_roof_geometry_change_v1','previous_source_signature':rr.source_signature(d['source']),'new_source_signature':rr.source_signature(proposal['source']),'source_ref':'explicit synthetic amended plan','approved_by':'independent synthetic geometry reviewer'}
 path=tmp_path/'roof-geometry-amendment.json';path.write_text(json.dumps(detail_payload(proposal)));proposal['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':'explicit synthetic revision'}
 return app,s,item,r,d,original,proposal,evidence,new,points



def test_planar_formula_and_report_label_the_envelope_as_envelope(tmp_path):
 app,_,_,_,d=bound_planar(tmp_path,'solid_slab');app.save_aec_system_draft('P',d,expected_revision=0)
 r=app.preview_aec_system('P','solid_slab','L1','S1');assert 'چندضلعی' in r['rows'][0]['formula']
 path=tmp_path/'planar-report.csv';app.export_roof_detail_report('P','solid_slab','L1','S1',path,format='csv')
 text=path.read_text(encoding='utf-8-sig');assert 'پوش مختصات طول' in text and 'مساحت خالص هندسی' in text
 app.store.close()
