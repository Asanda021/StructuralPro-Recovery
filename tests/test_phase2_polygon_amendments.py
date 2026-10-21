"""Existing correction journal + real SQLite, no pricing or approval fabrication."""
from copy import deepcopy
from hashlib import sha256
from decimal import Decimal
import json
import pytest
from core.platform.application import StructuralProApp
from core.drawings.takeoff_session import DrawingTakeoffSession
from test_phase2_pdf_roof import fixture
from test_phase2_topology_v2_sqlite import measured


def setup(tmp_path):
 app,_,_,_=fixture(tmp_path);s,i=measured(app,tmp_path/'plan.pdf');r=app.save_drawing_takeoff_session('P',s)
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 root=app.open_project('P')['takeoffs'][0]['source_id']
 return app,s,i,r,root


def propose(app,s,i,r,root,tmp_path,change='vertex',base=1):
 assert hasattr(app,'create_drawing_amendment'),'missing existing-journal drawing correction adapter'
 if change=='vertex':s.edit_polygon(i.id,[(100,100),(550,100),(550,600),(100,600)])
 if change=='opening':s.add_polygon_opening(i.id,[(100,200),(200,200),(200,300),(100,300)],'revised explicit synthetic opening')
 doc=app.drawing_amendment_document('P',root,s.to_dict(),expected_revision=base,expected_session_revision=2)
 path=tmp_path/('correction-'+str(base)+'.json');path.write_text(json.dumps(doc,ensure_ascii=False))
 evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':'SYNTHETIC correction schedule'}
 return app.create_drawing_amendment('P',root,s.to_dict(),expected_revision=base,expected_session_revision=2,created_by='synthetic author',reason='explicit synthetic correction',evidence=evidence)

@pytest.mark.parametrize('change,expected',[('vertex',90),('opening',96),('document',100)])
def test_drawing_correction_original_immutable_and_effective_boq(tmp_path,change,expected):
 app,s,i,r,key=setup(tmp_path);before=deepcopy(app.open_project('P'));a=propose(app,s,i,r,key,tmp_path,change)
 assert Decimal(str(a['delta'][key]))==expected-100
 with pytest.raises(ValueError):app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='synthetic author',note='self review forbidden')
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='independent synthetic reviewer',note='explicit oracle comparison')
 app.apply_beam_amendment('P',a['id'],expected_revision=1)
 after=deepcopy(app.open_project('P'));assert after['takeoffs']==before['takeoffs'] and after['drawing_sessions']==before['drawing_sessions']
 assert Decimal(str(after['boq'][0]['quantity']))==expected
 with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==after
 assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok';app.store.close()

@pytest.mark.parametrize('fault',['stale','evidence','concurrent','financial','direct'])
def test_drawing_correction_failures_are_atomic(tmp_path,fault):
 app,s,i,r,key=setup(tmp_path);before=deepcopy(app.open_project('P'))
 if fault=='direct':
  p=deepcopy(before);p['takeoffs'][0]['quantities'][0]['amount']=1
  with pytest.raises(ValueError):app.store.save('P',p)
 else:
  a=propose(app,s,i,r,key,tmp_path)
  if fault=='stale':
   with pytest.raises(RuntimeError):app.review_beam_amendment('P',a['id'],expected_revision=0,reviewer='other',note='stale')
  elif fault=='concurrent':
   with pytest.raises(ValueError):propose(app,s,i,r,key,tmp_path,'document')
  else:
   if fault=='evidence':(tmp_path/'correction-1.json').write_text('changed')
   if fault=='evidence':
    with pytest.raises(ValueError):app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='bad bytes')
   else:
    app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='review')
    p=app.open_project('P');p['contract']={'id':'existing financial lock'};app.store.save('P',p)
    snap=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
    assert app.open_project('P')==snap
 assert app.open_project('P')['takeoffs']==before['takeoffs'] and app.open_project('P')['boq']==before['boq'];app.store.close()


def test_effective_expansion_blocks_second_member_payment(tmp_path):
 app,s,i,r,key=setup(tmp_path)
 s.edit_polygon(i.id,[(100,100),(650,100),(600,600),(100,600)])
 a=propose(app,s,i,r,key,tmp_path,'document')
 assert Decimal(str(a['delta'][key]))==5
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='105 square metre oracle')
 app.apply_beam_amendment('P',a['id'],expected_revision=1)
 app.add_project_member('P','M2','L1','سقف')
 extra=DrawingTakeoffSession(str(tmp_path/'plan.pdf'));extra.calibrate(1,50,1)
 from core.drawings.graphical_takeoff import Point
 j=extra.add_polygon([Point(610,110),Point(640,110),Point(640,160),Point(610,160)],topology='exact_planar_region_v2',source='explicit synthetic other region',floor_id='L1',member_id='M2',quantity_owner='other synthetic owner')
 rec=app.save_drawing_takeoff_session('P',extra);snap=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rec['session_id'],[j.id],expected_session_revision=1)
 assert app.open_project('P')==snap;app.store.close()


def test_successive_corrections_increase_then_remove_opening_without_history_loss(tmp_path):
 app,s,i,r,key=setup(tmp_path);a=propose(app,s,i,r,key,tmp_path,'opening')
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='96 m2 oracle');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 s.edit_polygon(i.id,s.find(i.id).geometry,holes=[],opening_refs=[])
 b=propose(app,s,i,r,key,tmp_path,'document',base=2)
 assert Decimal(str(b['delta'][key]))==4
 app.review_beam_amendment('P',b['id'],expected_revision=1,reviewer='another',note='100 m2 oracle');app.apply_beam_amendment('P',b['id'],expected_revision=1)
 project=app.open_project('P');assert len(project['takeoffs'])==1 and len(project['beam_amendments'])==2
 assert Decimal(str(project['boq'][0]['quantity']))==100
 assert project['beam_amendments'][b['id']]['boq_before_apply'][0]['quantity']==96
 app.store.close()


def test_new_pdf_bytes_need_documented_correction_and_preserve_original(tmp_path):
 import fitz
 app,s,i,r,key=setup(tmp_path);original=deepcopy(app.open_project('P'))
 new=tmp_path/'revised-plan.pdf'
 with fitz.open(tmp_path/'plan.pdf') as pdf:pdf[0].insert_text((20,20),'explicit synthetic drawing revision');pdf.save(new)
 changed=DrawingTakeoffSession(str(new));changed.calibrate(1,50,1)
 from core.drawings.graphical_takeoff import Point
 j=changed.add_polygon([Point(100,100),Point(550,100),Point(550,600),Point(100,600)],topology='exact_planar_region_v2',source='explicit synthetic revised source',floor_id='L1',member_id='M1',quantity_owner=i.geometry_evidence['quantity_owner'])
 a=propose(app,changed,j,r,key,tmp_path,'document');app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='new PDF and 90 m2 oracle');app.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert app.open_project('P')['takeoffs']==original['takeoffs'] and app.open_project('P')['drawing_sessions']==original['drawing_sessions']
 assert app.open_project('P')['boq'][0]['quantity']==90;app.store.close()


def test_drawing_session_revision_changed_after_proposal_is_atomic(tmp_path):
 app,s,i,r,key=setup(tmp_path);a=propose(app,s,i,r,key,tmp_path,'document')
 s.add_count(1,page=1,source='explicit unrelated draft count')
 app.save_drawing_takeoff_session('P',s,session_id=r['session_id'],expected_revision=2)
 before=deepcopy(app.open_project('P'))
 with pytest.raises(RuntimeError):app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='stale session')
 assert app.open_project('P')==before;app.store.close()


def test_source_file_changed_after_review_blocks_apply(tmp_path):
 app,s,i,r,key=setup(tmp_path);a=propose(app,s,i,r,key,tmp_path)
 app.review_beam_amendment('P',a['id'],expected_revision=1,reviewer='other',note='explicit source oracle');before=deepcopy(app.open_project('P'))
 (tmp_path/'plan.pdf').write_bytes(b'changed source, invalid PDF')
 with pytest.raises(ValueError):app.apply_beam_amendment('P',a['id'],expected_revision=1)
 assert app.open_project('P')==before;app.store.close()
