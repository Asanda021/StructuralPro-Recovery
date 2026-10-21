from copy import deepcopy
from decimal import Decimal
import pytest
from core.platform.application import StructuralProApp
from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from test_phase2_pdf_roof import fixture


def measured(app,path,member='M1'):
 app.add_project_floor('P','طبقه مصنوعی صریح',level='L1');app.add_project_member('P',member,'L1','سقف')
 s=DrawingTakeoffSession(str(path));s.calibrate(1,50,1)
 i=s.add_polygon([Point(100,100),Point(600,100),Point(600,600),Point(100,600)],topology='exact_planar_region_v2',source='explicit synthetic geometry',floor_id='L1',member_id=member,quantity_owner='synthetic drawing schedule owner')
 return s,i

@pytest.mark.parametrize('opening,net,parts',[
 ([(100,200),(250,200),(250,300),(100,300)],94,1),
 ([(300,100),(400,100),(400,600),(300,600)],80,2),
])
def test_real_v2_sqlite_boq_roundtrip_and_components(tmp_path,opening,net,parts):
 app,_,_,_=fixture(tmp_path);s,i=measured(app,tmp_path/'plan.pdf')
 s.add_polygon_opening(i.id,opening,'explicit synthetic cut drawing')
 assert Decimal(s.find(i.id).geometry_evidence['net_m2'])==net
 r=app.save_drawing_takeoff_session('P',s)
 app.commit_drawing_takeoff_to_boq('P',r['session_id'],[i.id],expected_session_revision=1)
 before=deepcopy(app.open_project('P'));assert Decimal(str(before['boq'][0]['quantity']))==net
 assert len(before['takeoffs'][0]['params']['geometry_evidence']['components'])==parts
 app.store.close();app=StructuralProApp(tmp_path/'db');assert app.open_project('P')==before
 assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
 app.store.close()
