"""Phase-one documented paint/putty/prep and physical overlap acceptance.

Synthetic evidence, not a client drawing or an automatic bill/payment approval.
"""
from copy import deepcopy
from decimal import Decimal

import pytest
from core.takeoff.reviewed_aec import empty_system, preview_system
from core.takeoff.engine import TakeoffEngine


def part(name, **kwargs):
    return dict(id=name, physical_key='PAINT-'+name,
                source_ref='مصنوعی '+name, approved_by='مهندس مصنوعی', **kwargs)


def group(op, passes, status='confirmed'):
    return dict(status=status, source_ref='دامنه مصنوعی '+op,
                approved_by='مهندس تأییدکننده مستقل '+op,
                reason='' if status=='confirmed' else 'عدم کاربرد مستند', passes=passes)


def coat(name, zone='Z1', index='1', rate='0.25', op='putty'):
    consumable=op != 'surface_preparation'
    return part(name, zone_id=zone, pass_no=index,
                material_basis='documented_rate' if consumable else 'not_applicable',
                quantity_per_m2=rate if consumable else '',
                quantity_unit='kg' if consumable else 'none',
                material_ref='مصالح مصنوعی '+op if consumable else '',
                rate_ref='مدرک مصرف مصنوعی '+op if consumable else '',
                no_material_reason='' if consumable else 'تمیزکاری خشک بدون ماده')


def sample(face='inside'):
    d=empty_system('paint_finish','L1','P1')
    d.update(measurement_policy='architecture_specialist_v1',
             building_id='B1',axis='محور مستند',
             source=dict(mode='manual',source_id='SOURCE-PAINT',
                         plan_ref='پلان مصنوعی',detail_ref='دیتایل مصنوعی'))
    g=dict(physical_surface_id='SURFACE-PAINT',host_id='WALL-1',space_id='ROOM-1',
           face=face,plane='horizontal' if face=='ceiling' else 'vertical',
           shape='rectangle',unit='m',length_m='3',width_m='2',count='1',
           repeat_ref='یک وجه واقعی',source_ref='هندسه مصنوعی',approved_by='مهندس مصنوعی')
    opening=part('O1',x='2',y='1',width_m='1',height_m='1')
    zone=part('Z1',x='0',y='0',width_m='3',height_m='2',
              opening_ids=['O1'],scope_ref='دامنه کل وجه با کسر بازشوی واقعی')
    stages={
        'surface_preparation':group('surface_preparation',[coat('PREP',op='surface_preparation')]),
        'putty':group('putty',[coat('PUTTY')]),
        'primer':group('primer',[coat('PRIMER',op='primer')]),
        'finish_coat':group('finish_coat',[coat('PAINT1',op='finish_coat'),
                                            coat('PAINT2',index='2',op='finish_coat')]),
    }
    d['architecture_detail']=dict(contract='paint_surface_v1',geometry=g,
                                  openings=[opening],zones=[zone],stages=stages)
    return d


def result(d):return preview_system(d,TakeoffEngine())


def test_documented_net_area_each_coat_and_materials_are_informational():
    d=sample();old=deepcopy(d);out=result(d)
    assert out['ready'],out['blockers']
    work=[r for r in out['rows'] if r['role']=='work']
    materials=[r for r in out['rows'] if r['role']=='material']
    assert len(work)==5 and len(materials)==4
    assert all(Decimal(str(r['quantity']))==5 and r['unit']=='m2' for r in work)
    assert all(Decimal(str(r['quantity']))==Decimal('1.25') for r in materials)
    assert d==old
    assert len({r['source_id'] for r in out['rows']})==len(out['rows'])


def test_ceiling_independent_geometry_and_explicit_no_putty():
    d=sample(face='ceiling');d['architecture_detail']['stages']['putty']=group('putty',[],status='not_applicable')
    out=result(d);assert out['ready'],out['blockers'];assert len([r for r in out['rows'] if r['role']=='work'])==4


@pytest.mark.parametrize('fault',[
    'float_length','float_count','float_rate','boolean_rate','missing_source','missing_stage',
    'bad_face','wrong_plane','opening_overlap','missing_opening_claim','duplicate_opening_claim',
    'zone_overlap','out_of_bounds','zero_area','duplicate_physical','pass_gap',
    'duplicate_pass','no_primer_reason','finish_not_applicable','unknown_rate',
    'missing_rate_source','wrong_unit','invented_waste','unreferenced_zone',
    'negative_count','missing_paint','putty_no_material','missing_material_reason',
    'duplicate_zone_identity','material_rate_zero', 'extra_geometry_field',
])
def test_bad_evidence_returns_no_partial_rows(fault):
    d=sample();a=d['architecture_detail'];g=a['geometry'];st=a['stages'];p=st['finish_coat']['passes'][1]
    if fault=='float_length':g['length_m']=3.0
    elif fault=='float_count':g['count']=1.0
    elif fault=='float_rate':p['quantity_per_m2']=0.25
    elif fault=='boolean_rate':p['quantity_per_m2']=True
    elif fault=='missing_source':p['source_ref']=''
    elif fault=='missing_stage':st.pop('primer')
    elif fault=='bad_face':g['face']='floor'
    elif fault=='wrong_plane':g['plane']='horizontal'
    elif fault=='opening_overlap':a['openings'].append(part('O2',x='2',y='1',width_m='1',height_m='1'))
    elif fault=='missing_opening_claim':a['zones'][0]['opening_ids']=[]
    elif fault=='duplicate_opening_claim':a['zones'][0]['opening_ids']=['O1','O1']
    elif fault=='zone_overlap':a['zones'].append(part('Z2',x='0',y='0',width_m='1',height_m='1',opening_ids=[],scope_ref='مستند'))
    elif fault=='out_of_bounds':a['zones'][0]['width_m']='4'
    elif fault=='zero_area':a['zones'][0]['height_m']='0'
    elif fault=='duplicate_physical':p['physical_key']=st['primer']['passes'][0]['physical_key']
    elif fault=='pass_gap':p['pass_no']='3'
    elif fault=='duplicate_pass':p['pass_no']='1'
    elif fault=='no_primer_reason':st['primer']=group('primer',[],status='not_applicable');st['primer']['reason']=''
    elif fault=='finish_not_applicable':st['finish_coat']=group('finish_coat',[],status='not_applicable')
    elif fault=='unknown_rate':p['material_basis']='unknown'
    elif fault=='missing_rate_source':p['rate_ref']=''
    elif fault=='wrong_unit':p['quantity_unit']='m3'
    elif fault=='invented_waste':p['waste_percent']='0.1'
    elif fault=='unreferenced_zone':p['zone_id']='NONE'
    elif fault=='negative_count':g['count']='-1'
    elif fault=='missing_paint':st['finish_coat']['passes']=[]
    elif fault=='putty_no_material':st['putty']['passes'][0].update(material_basis='not_applicable',quantity_per_m2='',quantity_unit='none',material_ref='',rate_ref='',no_material_reason='none')
    elif fault=='missing_material_reason':st['surface_preparation']['passes'][0]['no_material_reason']=''
    elif fault=='duplicate_zone_identity':a['zones'][0]['physical_key']=a['openings'][0]['physical_key']
    elif fault=='material_rate_zero':p['quantity_per_m2']='0'
    elif fault=='extra_geometry_field':g['assumed_waste']='0.1'
    out=result(d);assert out['ready'] is False and out['rows']==[] and out['blockers'], fault


def test_sqlite_review_and_boq_without_second_material_payment(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('آزمون مصنوعی رنگ','P');d=sample()
    one=app.save_aec_system_draft('P',d,expected_revision=0);assert one['revision']==1
    app.review_roof_system('P','paint_finish','L1','P1',expected_revision=1,reviewer='بازبین مستقل',note='کنترل دیتایل مصنوعی')
    committed=app.commit_aec_system('P','paint_finish','L1','P1',expected_revision=2)
    assert committed['status']=='committed'
    data=app.open_project('P');assert len(data['boq'])==4
    assert sorted(Decimal(str(v['quantity'])) for v in data['boq'])==[5,5,5,10]
    assert app.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    app.store.close()


def test_real_cas_stale_revision_rejected(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('پروژه آزمایشی','P');d=sample()
    a.save_aec_system_draft('P',d,expected_revision=0)
    b=StructuralProApp(tmp_path/'db');a.save_aec_system_draft('P',d,expected_revision=1)
    with pytest.raises(RuntimeError):b.save_aec_system_draft('P',d,expected_revision=1)
    assert len(a.open_project('P')['boq'])==0
    a.store.close();b.store.close()


def test_cover_and_paint_same_host_conflict(tmp_path):
    from core.platform.application import StructuralProApp
    from test_cover_specialist_work import sample as cover_sample
    app=StructuralProApp(tmp_path/'db');app.create_project('پروژه آزمایشی','P')
    cover=cover_sample('stone_cladding')
    cover['architecture_detail']['geometry'].update(host_id='WALL-1',face='inside',plane='vertical')
    app.save_aec_system_draft('P',cover,expected_revision=0)
    paint=sample();before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError,match='رنگ|مشترک'):
        app.save_aec_system_draft('P',paint,expected_revision=0)
    assert app.open_project('P')==before
    app.store.close()


def test_disjoint_paint_and_cover_can_coexist(tmp_path):
    from core.platform.application import StructuralProApp
    from test_cover_specialist_work import sample as cover_sample
    app=StructuralProApp(tmp_path/'db');app.create_project('پروژه آزمایشی','P')
    cover=cover_sample('stone_cladding')
    g=cover['architecture_detail']['geometry'];g.update(host_id='WALL-1',face='inside',plane='vertical',length_m='6',width_m='2')
    for p in cover['architecture_detail']['surfaces']:
        p['x']='3';p['opening_ids']=''
    for table in ('pieces','joints'):
        for p in cover['architecture_detail'][table]:p['x']=str(Decimal(p['x'])+3)
    for p in cover['architecture_detail']['openings']:
        p['x']='5'
    app.save_aec_system_draft('P',cover,expected_revision=0)
    paint=sample();paint['architecture_detail']['geometry'].update(length_m='6',space_id=g['space_id']);paint['axis']=cover['axis']
    app.save_aec_system_draft('P',paint,expected_revision=0)
    assert len(app.open_project('P')['reviewed_aec_systems'])==2
    app.store.close()


def test_copy_draft_remaps_zone_ids_without_leaking_approvals(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('مصنوعی','P')
    app.save_aec_system_draft('P',sample(),expected_revision=0)
    entry=app.aec_workflow().copy_roof('P','paint_finish','L1','P1',
        new_system_id='P2',new_source_id='COPY',reason='کپی صریح آزمایشی')
    detail=entry['data']['architecture_detail']
    assert entry['status']=='draft' and entry['revision']==1
    assert detail['geometry']['host_id']!='WALL-1'
    zone=detail['zones'][0]['id']
    assert zone!='Z1'
    assert all(p['zone_id']==zone for g in detail['stages'].values() for p in g['passes'])
    assert not result(entry['data'])['ready']
    assert app.open_project('P')['boq']==[]
    app.store.close()
