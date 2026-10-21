from core.platform.application import StructuralProApp
from copy import deepcopy
from fractions import Fraction
import pytest
from core.drawings.planar_geometry import region
from core.drawings.roof_region import bind_source
from test_phase2_pdf_roof import fixture
from test_phase2_advanced_geometry_sqlite import polygon

def test_rotated_hole_independent_area():
 _,_,g,d=region([(0,0),(10,0),(10,10),(0,10)],[[(3,5),(5,3),(7,5),(5,7)]])
 assert g==100 and d==8 and g-d==92

def test_rotated_outer_independent_area():
 _,_,g,d=region([(0,0),(4,3),(1,7),(-3,4)],[[(0,3),(1,3),(1,4),(0,4)]])
 assert g==25 and d==1 and g-d==24

def test_different_member_overlap_is_atomic(tmp_path):
 app,_,_,_=fixture(tmp_path);_,i,r=polygon(app,tmp_path/'plan.pdf')
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 _,i,r=polygon(app,tmp_path/'plan.pdf',[(200,200),(700,200),(700,400),(200,400)],member='OTHER')
 before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError,match='هم‌پوشان|همپوشان|هم‌پوشانی|همپوشانی'):
  app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 assert app.open_project('P')==before
 app.store.close()

def test_concave_specialist_remains_blocked(tmp_path):
 app,_,_,_=fixture(tmp_path);_,i,r=polygon(app,tmp_path/'plan.pdf');before=deepcopy(app.open_project('P'))
 with pytest.raises(ValueError):bind_source(app.load_drawing_takeoff_session('P',r['session_id']),i.id)
 assert app.open_project('P')==before
 app.store.close()
