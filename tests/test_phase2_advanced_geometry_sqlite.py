"""Real ProjectStore and BOQ; explicit synthetic vector fixtures, not engineering approval."""
from copy import deepcopy
import json
from decimal import Decimal
import pytest
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point
from test_phase2_pdf_roof import fixture,bound
from core.platform.application import StructuralProApp

P=[(100,100),(600,100),(600,300),(300,300),(300,600),(100,600)]


def polygon(app,path,points=P,owner='documented synthetic surface owner',member='P1'):
 project=app.open_project('P')
 if not project.get('floors'):app.add_project_floor('P','طبقه صریح مصنوعی',level='L1')
 if not any(m['id']==member for m in app.open_project('P').get('members',[])):app.add_project_member('P',member,'L1','سقف')
 s=DrawingTakeoffSession(str(path));s.calibrate(1,100,1)
 item=s.add_polygon([Point(*p) for p in points],source='explicit synthetic P1',quantity_owner=owner,floor_id='L1',member_id=member,takeoff_code='SURFACE')
 saved=app.save_drawing_takeoff_session('P',s)
 return s,item,saved


def test_polygon_holes_boq_exact_and_independent_reopen(tmp_path):
 app,_,_,_=fixture(tmp_path)
 s,item,r=polygon(app,tmp_path/'plan.pdf')
 s.add_polygon_opening(item.id,[(150,150),(250,150),(250,250),(150,250)],'O1 explicit source')
 r=app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=1)
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=2)
 before=deepcopy(app.open_project('P'));assert Decimal(str(before['boq'][0]['quantity']))==15
 assert before['takeoffs'][0]['params']['geometry_evidence']['member_id']=='P1'
 app.store.close();app=StructuralProApp(tmp_path/'db')
 assert app.open_project('P')==before
 loaded=app.load_drawing_takeoff_session('P',r['session_id'])
 assert loaded['session']['items'][0]['geometry_evidence']['opening_refs']==['O1 explicit source']
 assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
 app.store.close()

@pytest.mark.parametrize('points',[
 P[2:]+P[:2],P[::-1],[(200,200),(700,200),(700,400),(200,400)],
 [(200,200),(240,230),(210,270),(170,240)],
])
def test_cross_session_duplicate_or_overlap_preserves_nonempty_boq(tmp_path,points):
 app,_,_,_=fixture(tmp_path);s,item,r=polygon(app,tmp_path/'plan.pdf')
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 s2,i2,r2=polygon(app,tmp_path/'plan.pdf',points)
 before=deepcopy(app.open_project('P'));digest=app.store.current_digest('P')
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r2['session_id'],[i2.id],expected_session_revision=1)
 assert app.open_project('P')==before and app.store.current_digest('P')==digest
 app.store.close()


def test_adjacent_and_inside_hole_are_distinct_surfaces(tmp_path):
 app,_,_,_=fixture(tmp_path)
 outer=[(100,100),(600,100),(600,600),(100,600)]
 s,item,r=polygon(app,tmp_path/'plan.pdf',outer)
 s.add_polygon_opening(item.id,[(200,200),(500,200),(500,500),(200,500)],'void O1')
 app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=1)
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=2)
 for member,pts in [('P2',[(250,250),(450,250),(450,450),(250,450)]),('P3',[(600,100),(800,100),(800,600),(600,600)])]:
  _,item,r=polygon(app,tmp_path/'plan.pdf',pts,member=member)
  app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 assert len(app.open_project('P')['takeoffs'])==3
 app.store.close()

@pytest.mark.parametrize('fault',['revision','sha','metadata','outside','quantity','owner'])
def test_polygon_failure_is_atomic(tmp_path,fault):
 app,_,_,_=fixture(tmp_path);s,item,r=polygon(app,tmp_path/'plan.pdf',owner='' if fault=='owner' else 'surface owner')
 before=deepcopy(app.open_project('P'));digest=app.store.current_digest('P')
 if fault=='sha':(tmp_path/'plan.pdf').write_bytes(b'changed')
 if fault in ('metadata','outside','quantity'):
  data=json.loads(s.to_json());row=data['items'][0]
  if fault=='metadata':row['geometry_evidence']['net_m2']='999'
  if fault=='outside':row['geometry'][0]=(-1,100)
  if fault=='quantity':row['quantity']=999
  with pytest.raises(ValueError):app.save_drawing_takeoff_session('P',data,session_id=r['session_id'],expected_revision=1)
 else:
  with pytest.raises((ValueError,RuntimeError)):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=0 if fault=='revision' else 1)
 assert app.open_project('P')==before and app.store.current_digest('P')==digest
 app.store.close()


def test_specialist_reserved_rectangle_blocks_generic_polygon(tmp_path):
 app,_,_,_,data=bound(tmp_path);app.save_aec_system_draft('P',data,expected_revision=0)
 _,item,r=polygon(app,tmp_path/'plan.pdf',[(150,150),(550,150),(350,350)])
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 assert app.open_project('P')==before
 app.store.close()


def test_new_pdf_bytes_do_not_authorize_second_payment_for_same_member(tmp_path):
 import fitz
 app,_,_,_=fixture(tmp_path);_,item,r=polygon(app,tmp_path/'plan.pdf')
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 changed=tmp_path/'revised-plan.pdf'
 with fitz.open(tmp_path/'plan.pdf') as pdf:
  pdf[0].insert_text((10,20),'explicit synthetic new revision');pdf.save(changed)
 _,item,r=polygon(app,changed,[(100,100),(300,100),(300,300),(100,300)])
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 assert app.open_project('P')==before
 app.store.close()


def test_committed_polygon_geometry_cannot_be_rewritten_by_session_revision(tmp_path):
 app,_,_,_=fixture(tmp_path);s,item,r=polygon(app,tmp_path/'plan.pdf')
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[item.id],expected_session_revision=1)
 current=app.load_drawing_takeoff_session('P',r['session_id'])
 s.edit_polygon(item.id,[(100,100),(300,100),(300,300),(100,300)])
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=current['revision'])
 assert app.open_project('P')==before
 app.store.close()

@pytest.mark.parametrize('kind',['solid_slab','joist_block','joist_foam'])
def test_axis_polygon_reuses_existing_specialist_and_mismatched_member_is_rejected(tmp_path,kind):
 from core.drawings.roof_region import bind_source,detail_payload
 from test_roof_specialist_work import sample
 from hashlib import sha256
 app,_,_,_=fixture(tmp_path)
 _,item,r=polygon(app,tmp_path/'plan.pdf',[(100,100),(500,100),(500,500),(100,500)],member='S1')
 source=bind_source(app.load_drawing_takeoff_session('P',r['session_id']),item.id)
 data=sample(kind);data['source']=source;source.update(plan_ref='explicit synthetic plan',detail_ref='explicit synthetic schedule')
 path=tmp_path/'advanced-roof.json';path.write_text(json.dumps(detail_payload(data)));source.update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 app.save_aec_system_draft('P',data,expected_revision=0)
 assert app.preview_aec_system('P',kind,'L1','S1')['ready']
 app.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='independent synthetic reviewer',note='explicit schedule comparison')
 app.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
 before=deepcopy(app.open_project('P'));assert before['boq']
 changed=deepcopy(data);changed['system_id']='DIFFERENT';path=tmp_path/'mismatch.json';path.write_text(json.dumps(detail_payload(changed)));changed['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
 from core.takeoff.reviewed_aec import preview_system
 assert not preview_system(changed,app.takeoff)['ready']
 assert app.open_project('P')==before
 app.store.close()


def test_unregistered_polygon_owner_does_not_authorize_boq(tmp_path):
 app,_,_,_=fixture(tmp_path)
 s=DrawingTakeoffSession(str(tmp_path/'plan.pdf'));s.calibrate(1,100,1)
 i=s.add_polygon([Point(100,100),Point(200,100),Point(200,200),Point(100,200)],source='explicit synthetic unlinked region',quantity_owner='typed owner claim only')
 r=app.save_drawing_takeoff_session('P',s);before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 assert app.open_project('P')==before
 app.store.close()
