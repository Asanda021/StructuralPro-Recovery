"""Explicit synthetic framed opening between full-span joists; no real design claim."""
from copy import deepcopy
from pathlib import Path
from decimal import Decimal
from hashlib import sha256
import json,sys
import pytest
sys.path.insert(0,str(Path.cwd()/'tests'))
from test_phase2_pdf_roof import bound
from core.drawings.roof_region import add_rectangular_opening,bind_source,detail_payload
from core.takeoff.reviewed_aec import preview_system

@pytest.mark.parametrize('kind',['joist_block','joist_foam'])
def test_explicit_opening_layout_to_boq_reopens(tmp_path,kind):
    app,s,item,rec,d=bound(tmp_path,kind)
    add_rectangular_opening(s,item.id,[(200,120),(300,120),(300,220),(200,220)],'synthetic framed opening schedule O1')
    app.save_drawing_takeoff_session('P',s,session_id=rec['session_id'],expected_revision=1)
    d['source'].update(bind_source(app.load_drawing_takeoff_session('P',rec['session_id']),item.id))
    rd=d['roof_detail'];template=next(p for p in rd['regions'] if p['id']=='V0');rd['regions']=[p for p in rd['regions'] if p['id']!='V0']
    for ident,component,x,y,l,w in [('VA','void','0','.2','1','1.8'),('VB','void','1','1.2','1','.8'),('VC','void','2','.2','2','1.8'),('OPEN','solid_zones','1','.2','1','1')]:
        region=deepcopy(template);region.update(id=ident,component=component,x=x,y=y,length=l,width=w,source_ref='explicit synthetic partition v2');rd['regions'].append(region)
    piece=deepcopy(rd['pieces'][0]);rd['pieces']=[p for p in rd['pieces'] if p['region_id']!='V0']
    for ident,l,w in [('VA','1','1.8'),('VB','1','.8'),('VC','2','1.8')]:
        p=deepcopy(piece);p.update(id='PIECE-'+ident,region_id=ident,count='1',length=l,width=w,nx='1',ny='1',nz='1',spec_ref='explicit custom piece dimensions; no waste assumption');rd['pieces'].append(p)
    rd['deductions']=[{'id':'O1','kind':'opening','x':'1','y':'.2','z':'0','length':'1','width':'1','height':'.25','source_ref':'explicit synthetic full-depth opening','approved_by':'synthetic reviewer'}]
    rd['rebars']['opening']=deepcopy(rd['rebars']['thermal']);bar=rd['rebars']['opening']['series'][0];bar.update(id='OPEN-BAR',physical_key='OPEN-BAR-PHYSICAL')
    rd['formwork']['faces'][0]['deduction_m2']='1'
    path=tmp_path/'opening-detail.json';path.write_text(json.dumps(detail_payload(d),ensure_ascii=False),encoding='utf8');d['source'].update(detail_path=str(path),detail_sha256=sha256(path.read_bytes()).hexdigest())
    result=preview_system(d,app.takeoff);assert result['ready'],result['blockers']
    totals={}
    for row in result['rows']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
    assert totals['concrete']==Decimal('.99') and totals['precast_concrete']==Decimal('.08')
    assert totals['rebar']==Decimal('106.56') and totals['formwork']==15 and totals['joists']==2 and totals['blocks' if kind=='joist_block' else 'foam']==5
    app.save_aec_system_draft('P',d,expected_revision=0);app.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='independent test reviewer',note='explicit schedule validation')
    app.commit_aec_system('P',kind,'L1','S1',expected_revision=2);before=deepcopy(app.open_project('P'))
    app.export_roof_detail_report('P',kind,'L1','S1',str(tmp_path/'opening.csv'),format='csv');app.store.close()
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');assert app.open_project('P')['boq']==before['boq'];app.store.close()
