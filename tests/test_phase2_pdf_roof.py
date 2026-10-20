"""Transparent vector-PDF fixtures; these are software, not design approvals."""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import fitz
import pytest
from core.platform.application import StructuralProApp
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.drawings.graphical_takeoff import Point
from core.takeoff.reviewed_aec import preview_system
from test_roof_specialist_work import sample, KINDS


def fixture(tmp_path, kind='joist_block'):
    path=tmp_path/'plan.pdf'
    with fitz.open() as pdf:
        for _ in range(2):
            page=pdf.new_page(width=400,height=400)
            page.draw_rect(fitz.Rect(48,48,240,240))
        pdf.save(path)
    app=StructuralProApp(tmp_path/'db');app.create_project('آزمون مصنوعی نقشه','P')
    session=DrawingTakeoffSession(str(path));session.calibrate(1,400,4)
    item=session.add_area([Point(100,100),Point(500,100),Point(500,500),Point(100,500)],source='explicit-roof')
    saved=app.save_drawing_takeoff_session('P',session)
    return app, session, item, saved


def bound(tmp_path, kind='joist_block'):
    from core.drawings.roof_region import bind_source, detail_payload
    app,s,item,rec=fixture(tmp_path,kind)
    d=sample(kind)
    d['source']=bind_source(app.load_drawing_takeoff_session('P',rec['session_id']),item.id)
    d['source'].update(plan_ref='پلان مصنوعی',detail_ref='جدول صریح مصنوعی')
    doc=tmp_path/'schedule.json';doc.write_text(json.dumps(detail_payload(d),ensure_ascii=False),encoding='utf8')
    d['source'].update(detail_path=str(doc),detail_sha256=sha256(doc.read_bytes()).hexdigest())
    return app,s,item,rec,d


@pytest.mark.parametrize('kind',KINDS)
def test_bound_three_roofs_sqlite_review_boq_reopen(tmp_path,kind):
    app,s,item,rec,d=bound(tmp_path,kind)
    result=preview_system(d,app.takeoff);assert result['ready'],result['blockers']
    totals={}
    for row in result['rows']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
    assert totals['concrete']==Decimal('3.2' if kind=='solid_slab' else '1.04')
    assert totals['rebar']==Decimal('71.040') and totals['formwork']==16
    if kind!='solid_slab':assert totals['joists']==2 and totals['blocks' if kind=='joist_block' else 'foam']==4
    app.save_aec_system_draft('P',d,expected_revision=0)
    app.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='بازبین مستقل آزمون',note='مقایسه مرجع مصنوعی')
    app.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
    before=deepcopy(app.open_project('P'));assert before['boq']
    with pytest.raises(ValueError):app.commit_aec_system('P',kind,'L1','S1',expected_revision=2)
    assert app.open_project('P')==before
    app.store.close();app=StructuralProApp(tmp_path/'db')
    assert app.get_aec_system('P',kind,'L1','S1')['data']['source']==json.loads(json.dumps(d['source']))
    assert app.open_project('P')['boq']==before['boq']
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    assert not app.store.db.execute('pragma foreign_key_check').fetchall();app.store.close()


@pytest.mark.parametrize('fault',['pdf','scale','page','dimensions','count','detail','detail_content','missing_detail','nonrectangle'])
def test_bound_source_faults_fail_closed(tmp_path,fault):
    app,s,item,rec,d=bound(tmp_path)
    if fault=='pdf':(tmp_path/'plan.pdf').write_bytes(b'changed')
    elif fault=='scale':d['source']['roof_binding']['session']['calibrations']['1']['meters_per_pixel']=.02
    elif fault=='page':d['source']['page']=2
    elif fault=='dimensions':d['roof_detail']['geometry']['length']='5'
    elif fault=='count':d['roof_detail']['geometry']['count']='2'
    elif fault=='detail':(tmp_path/'schedule.json').write_text('changed')
    elif fault=='detail_content':
        p=tmp_path/'schedule.json';p.write_text('{}');d['source']['detail_sha256']=sha256(p.read_bytes()).hexdigest()
    elif fault=='missing_detail':d['source'].pop('detail_path')
    elif fault=='nonrectangle':d['source']['roof_binding']['session']['items'][0]['geometry']=[[0,0],[400,0],[200,400]]
    before=app.store.current_digest('P');result=preview_system(d,app.takeoff)
    assert not result['ready'],fault
    assert app.store.current_digest('P')==before and not app.open_project('P')['boq'];app.store.close()


def test_session_stale_cas_and_generic_double_count(tmp_path):
    app,s,item,rec,d=bound(tmp_path)
    app.save_aec_system_draft('P',d,expected_revision=0)
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('P',rec['session_id'],[item.id],expected_session_revision=1)
    assert app.store.current_digest('P')==before
    app.save_drawing_takeoff_session('P',s,session_id=rec['session_id'],expected_revision=1)
    before=app.store.current_digest('P')
    with pytest.raises(RuntimeError):app.save_aec_system_draft('P',d,expected_revision=1)
    assert app.store.current_digest('P')==before
    with pytest.raises(RuntimeError):app.save_drawing_takeoff_session('P',s,session_id=rec['session_id'],expected_revision=1)
    assert app.store.current_digest('P')==before;app.store.close()


def test_same_geometry_other_session_or_family_rejected(tmp_path):
    from core.drawings.roof_region import bind_source
    app,s,item,rec,d=bound(tmp_path);app.save_aec_system_draft('P',d,expected_revision=0)
    other=app.save_drawing_takeoff_session('P',s)
    duplicate=deepcopy(d);duplicate['system_id']='OTHER';duplicate['kind']='joist_foam'
    duplicate['source']=bind_source(app.load_drawing_takeoff_session('P',other['session_id']),item.id)
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.save_aec_system_draft('P',duplicate,expected_revision=0)
    assert app.store.current_digest('P')==before;app.store.close()


def test_binding_missing_module_red(tmp_path):
    import core.drawings.roof_region as module
    assert callable(module.bind_source)

@pytest.mark.parametrize('pixels,meters',[(1e-308,1e308),(1e308,1e-308)])
def test_calibration_ratio_range_is_atomic(pixels,meters):
    s=DrawingTakeoffSession();before=s.to_dict()
    with pytest.raises(ValueError):s.calibrate(1,pixels,meters)
    assert s.to_dict()==before and not s.can_undo

@pytest.mark.parametrize('page',[1.5,True,float('nan'),float('inf')])
def test_pdf_page_does_not_silently_truncate(tmp_path,page):
    from core.drawings.pdf_engine import PDFDrawingEngine
    app,s,item,rec=fixture(tmp_path)
    with PDFDrawingEngine(tmp_path/'plan.pdf') as pdf:
        with pytest.raises((ValueError,TypeError)):pdf.text(page)
    app.store.close()


def test_opening_edit_undo_and_duplicate_fail_closed(tmp_path):
    app,s,item,rec=fixture(tmp_path)
    from core.drawings.roof_region import add_rectangular_opening
    add_rectangular_opening(s,item.id,[(200,200),(300,200),(300,300),(200,300)],'explicit opening A')
    assert s.find(item.id).quantity==15
    before=s.to_dict()
    for points in ([(200,200),(300,200),(300,300),(200,300)],[(50,50),(250,50),(250,250),(50,250)]):
        with pytest.raises(ValueError):add_rectangular_opening(s,item.id,points,'bad opening')
        assert s.to_dict()==before
    assert s.undo() and s.find(item.id).quantity==16
    assert s.redo() and s.find(item.id).quantity==15
    app.store.close()


def test_forged_reference_scale_is_rejected(tmp_path):
    from core.drawings.roof_region import bind_source
    app,s,item,rec=fixture(tmp_path);record=app.load_drawing_takeoff_session('P',rec['session_id'])
    record['session']['calibrations']['1']['reference_meters']=8
    with pytest.raises(ValueError):bind_source(record,item.id)
    app.store.close()


def test_generic_boq_before_roof_is_rejected(tmp_path):
    app,s,item,rec,d=bound(tmp_path)
    app.commit_drawing_takeoff_to_boq('P',rec['session_id'],[item.id],expected_session_revision=1)
    # Rebind to the current session after generic commit revision increment.
    from core.drawings.roof_region import bind_source
    updated=app.load_drawing_takeoff_session('P',rec['session_id']);d['source'].update(bind_source(updated,item.id))
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.save_aec_system_draft('P',d,expected_revision=0)
    assert app.store.current_digest('P')==before;app.store.close()


def test_pdf_roof_financial_lock_preserved(tmp_path):
    app,s,item,rec,d=bound(tmp_path);app.save_aec_system_draft('P',d,expected_revision=0)
    app.review_roof_system('P','joist_block','L1','S1',expected_revision=1,reviewer='بازبین',note='آزمون')
    p=app.open_project('P');p['contract']={'id':'locked'};app.store.save('P',p);before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.commit_aec_system('P','joist_block','L1','S1',expected_revision=2)
    assert app.store.current_digest('P')==before and not app.open_project('P')['boq'];app.store.close()


def test_missing_dimension_still_returns_blocked_preview(tmp_path):
    app,s,item,rec,d=bound(tmp_path);d['roof_detail']['geometry'].pop('length')
    r=preview_system(d,app.takeoff);assert not r['ready'] and r['blockers'];app.store.close()

@pytest.mark.parametrize('operation',['strip_service','strip_store','copy'])
def test_binding_cannot_be_stripped_or_copied(tmp_path,operation):
    app,s,item,rec,d=bound(tmp_path);app.save_aec_system_draft('P',d,expected_revision=0);before=app.store.current_digest('P')
    with pytest.raises(ValueError):
        if operation=='copy':app.aec_workflow().copy_roof('P','joist_block','L1','S1',new_system_id='COPY',new_source_id='NEW',reason='test')
        elif operation=='strip_service':
            d['source']={'mode':'manual','source_id':'manual','plan_ref':'x','detail_ref':'x'};app.save_aec_system_draft('P',d,expected_revision=1)
        else:
            p=app.open_project('P');next(iter(p['reviewed_aec_systems'].values()))['data']['source']={'mode':'manual','source_id':'x'};app.store.save('P',p)
    assert app.store.current_digest('P')==before;app.store.close()


def test_bound_slab_opening_exact_deduction_and_reopen(tmp_path):
    from core.drawings.roof_region import add_rectangular_opening,bind_source,detail_payload
    app,s,item,rec,d=bound(tmp_path,'solid_slab')
    add_rectangular_opening(s,item.id,[(200,200),(300,200),(300,300),(200,300)],'O1 explicit')
    r=app.save_drawing_takeoff_session('P',s,session_id=rec['session_id'],expected_revision=1)
    d['source'].update(bind_source(app.load_drawing_takeoff_session('P',r['session_id']),item.id))
    d['roof_detail']['deductions']=[{'id':'O1','kind':'opening','x':'1','y':'1','z':'0','length':'1','width':'1','height':'.2','source_ref':'explicit opening','approved_by':'synthetic reviewer'}]
    d['roof_detail']['rebars']['opening']=deepcopy(d['roof_detail']['rebars']['main_x'])
    bar=d['roof_detail']['rebars']['opening']['series'][0];bar['id']='opening-bar';bar['physical_key']='opening-physical'
    d['roof_detail']['formwork']['faces'][0]['deduction_m2']='1'
    p=tmp_path/'schedule.json';p.write_text(json.dumps(detail_payload(d),ensure_ascii=False),encoding='utf8');d['source']['detail_sha256']=sha256(p.read_bytes()).hexdigest()
    result=preview_system(d,app.takeoff);assert result['ready'],result['blockers']
    totals={}
    for row in result['rows']:totals[row['item_code']]=totals.get(row['item_code'],Decimal(0))+Decimal(str(row['quantity']))
    assert totals['concrete']==3 and totals['formwork']==15 and totals['rebar']==Decimal('106.56')
    app.save_aec_system_draft('P',d,expected_revision=0);app.store.close();app=StructuralProApp(tmp_path/'db')
    assert app.preview_aec_system('P','solid_slab','L1','S1')['rows']==result['rows'];app.store.close()


def test_roof_drawing_amendment_retains_original_and_boq(tmp_path):
    from core.drawings.roof_region import detail_payload
    app,s,item,rec,d=bound(tmp_path,'solid_slab')
    app.save_aec_system_draft('P',d,expected_revision=0);app.review_roof_system('P','solid_slab','L1','S1',expected_revision=1,reviewer='reviewer',note='test')
    app.commit_aec_system('P','solid_slab','L1','S1',expected_revision=2);before=deepcopy(app.open_project('P'))
    proposal=deepcopy(d);proposal['roof_detail']['geometry']['depth']='.3';proposal['roof_detail']['regions'][0]['height']='.3'
    p=tmp_path/'revised.json';p.write_text(json.dumps(detail_payload(proposal)),encoding='utf8');h=sha256(p.read_bytes()).hexdigest()
    proposal['source'].update(detail_path=str(p),detail_sha256=h)
    amendment=app.create_roof_amendment('P','solid_slab','L1','S1',proposal,expected_revision=2,created_by='author',reason='explicit revised thickness',evidence={'evidence_path':str(p),'evidence_sha256':h,'evidence_reference':'synthetic new detail'})
    app.review_beam_amendment('P',amendment['id'],expected_revision=1,reviewer='independent',note='test')
    app.apply_beam_amendment('P',amendment['id'],expected_revision=1)
    after=app.open_project('P');assert after['takeoffs']==before['takeoffs']
    assert after['reviewed_aec_systems']==before['reviewed_aec_systems'] and after['boq']!=before['boq']
    assert app.get_aec_system('P','solid_slab','L1','S1')['revision']==3;app.store.close()

@pytest.mark.parametrize('kind',['length','area'])
def test_measurement_underflow_cannot_become_zero(kind):
    s=DrawingTakeoffSession();s.calibrate(1,1,1e-200);before=s.to_dict()
    with pytest.raises(ValueError):
        if kind=='length':s.add_length([Point(0,0),Point(1e-200,0)])
        else:s.add_area([Point(0,0),Point(1,0),Point(1,1),Point(0,1)])
    assert s.to_dict()==before


def test_pdf_rectangle_must_be_inside_rendered_page(tmp_path):
    from core.drawings.roof_region import bind_source
    app,s,item,rec=fixture(tmp_path)
    s.add_area([Point(900,900),Point(950,900),Point(950,950),Point(900,950)],source='outside')
    r=app.save_drawing_takeoff_session('P',s,session_id=rec['session_id'],expected_revision=1)
    with pytest.raises(ValueError):bind_source(app.load_drawing_takeoff_session('P',r['session_id']),s.items[-1].id)
    app.store.close()
