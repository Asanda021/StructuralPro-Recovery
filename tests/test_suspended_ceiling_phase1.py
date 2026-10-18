"""Synthetic documented suspended-ceiling phase-one engine and SQLite gates."""
from copy import deepcopy
from decimal import Decimal
import pytest

from core.takeoff.reviewed_aec import empty_system,preview_system
from core.takeoff.engine import TakeoffEngine
from core.takeoff.suspended_ceiling_detail import CONTRACT


def part(ident,**fields):
    return dict(id=ident,physical_key='CEIL-PH-'+ident,source_ref='مدرک قطعه '+ident,
                approved_by='مهندس مستقل '+ident,**fields)


def group(name,items,reason=''):
    return dict(status='confirmed' if items else 'not_applicable',source_ref='مدرک گروه '+name,
                approved_by='بازبین گروه '+name,reason=reason if not items else '',items=items)


def sample():
    data=empty_system('suspended_ceiling','L1','SC1')
    data.update(building_id='B1',axis='محور یک',measurement_policy='architecture_specialist_v1',
                source=dict(mode='manual',source_id='SRC-SC1',plan_ref='پلان مصنوعی',detail_ref='دیتایل مصنوعی'))
    geom=dict(physical_surface_id='CEIL1',host_id='SLAB1',space_id='ROOM1',face='ceiling',plane='horizontal',
              shape='rectangle',unit='m',length_m='6',width_m='4',count='1',repeat_ref='یک دهانه واقعی',
              source_ref='هندسه مصنوعی',approved_by='مهندس هندسه')
    holes=[part('O1',x='2',y='1',width_m='2',height_m='2')]
    panels=[part('P1',x='0',y='0',width_m='2',height_m='4',material_ref='پانل',stock_ref='برش مستند',placement_ref='جانمایی'),
            part('P2',x='4',y='0',width_m='2',height_m='4',material_ref='پانل',stock_ref='برش مستند',placement_ref='جانمایی'),
            part('P3',x='2',y='0',width_m='2',height_m='1',material_ref='پانل',stock_ref='برش مستند',placement_ref='جانمایی'),
            part('P4',x='2',y='3',width_m='2',height_m='1',material_ref='پانل',stock_ref='برش مستند',placement_ref='جانمایی')]
    main=[part('MAIN',axis='x',fixed_m='0',start_m='0',end_m='6',profile_ref='پروفیل M',detail_ref='طول M')]
    cross=[part('C1',axis='y',fixed_m='1',start_m='0',end_m='4',profile_ref='پروفیل C1',detail_ref='طول C1'),
           part('C2',axis='y',fixed_m='5',start_m='0',end_m='4',profile_ref='پروفیل C2',detail_ref='طول C2')]
    hang=[part('H1',x='1',y='0',rail_id='MAIN',hanger_ref='H1-ref',anchorage_ref='Anchor1'),
          part('H2',x='5',y='0',rail_id='MAIN',hanger_ref='H2-ref',anchorage_ref='Anchor2')]
    joints=[part('J1',x='1',y='0',main_id='MAIN',cross_id='C1',connection_ref='جزییات J1'),
            part('J2',x='5',y='0',main_id='MAIN',cross_id='C2',connection_ref='جزییات J2')]
    trims=[part('T1',axis='x',fixed_m='4',start_m='0',end_m='6',trim_ref='نبشی واقعی')]
    groups=dict(panels=group('panels',panels),main_rails=group('main_rails',main),cross_rails=group('cross_rails',cross),
                hangers=group('hangers',hang),connectors=group('connectors',joints),edge_trims=group('edge_trims',trims))
    data['architecture_detail']=dict(contract=CONTRACT,geometry=geom,openings=holes,groups=groups)
    return data


def preview(data):return preview_system(data,TakeoffEngine())


def test_precise_net_layout_materials_and_no_duplicate_payment():
    d=sample();before=deepcopy(d);r=preview(d)
    assert r['ready'],r['blockers']
    assert len(r['rows'])==7
    assert [(row['item_code'],Decimal(str(row['quantity']))) for row in r['rows']]==[
      ('ceiling_work',Decimal(20)),('panels',Decimal(4)),('main_rails',Decimal(6)),
      ('cross_rails',Decimal(8)),('hangers',Decimal(2)),('connectors',Decimal(2)),('edge_trims',Decimal(6))]
    assert r['rows'][0]['role']=='work' and all(v['role']=='material' for v in r['rows'][1:])
    assert d==before


@pytest.mark.parametrize('fault',[
  'float_dimension','float_count','float_panel','boolean_hanger','missing_panel','overlap_panel','panel_in_opening',
  'opening_overlap','duplicate_physical','rail_out_of_bounds','rail_overlap','hanger_off_rail',
  'duplicate_hanger','unknown_rail','missing_connector','duplicate_connector','wrong_connector_point',
  'no_hanger','no_main','no_cross','edge_off_boundary','unknown_profile','unknown_stock',
  'unknown_approval','legacy_contract','extra_field','different_rail_source','float_connector',
  'double_profile_kind','duplicated_edge'
])
def test_incomplete_or_ambiguous_layout_never_exposes_partial_rows(fault):
    d=sample();a=d['architecture_detail'];g=a['geometry'];groups=a['groups']
    panels=groups['panels']['items'];main=groups['main_rails']['items'];cross=groups['cross_rails']['items']
    hang=groups['hangers']['items'];joints=groups['connectors']['items'];edge=groups['edge_trims']['items']
    if fault=='float_dimension':g['length_m']=6.0
    elif fault=='float_count':g['count']=1.0
    elif fault=='float_panel':panels[0]['width_m']=2.0
    elif fault=='boolean_hanger':hang[0]['x']=True
    elif fault=='missing_panel':panels.pop()
    elif fault=='overlap_panel':panels[0]['width_m']='3'
    elif fault=='panel_in_opening':panels[2]['height_m']='2'
    elif fault=='opening_overlap':a['openings'].append(part('O2',x='2',y='1',width_m='1',height_m='1'))
    elif fault=='duplicate_physical':panels[1]['physical_key']=panels[0]['physical_key']
    elif fault=='rail_out_of_bounds':main[0]['end_m']='7'
    elif fault=='rail_overlap':main.append(part('M2',axis='x',fixed_m='0',start_m='1',end_m='4',profile_ref='P',detail_ref='D'))
    elif fault=='hanger_off_rail':hang[0]['y']='1'
    elif fault=='duplicate_hanger':hang[1]['x']='1'
    elif fault=='unknown_rail':hang[1]['rail_id']='missing'
    elif fault=='missing_connector':joints.pop()
    elif fault=='duplicate_connector':joints.append(deepcopy(joints[0]));joints[-1].update(id='J3',physical_key='J3')
    elif fault=='wrong_connector_point':joints[0]['x']='2'
    elif fault=='no_hanger':groups['hangers']=group('hangers',[],reason='none')
    elif fault=='no_main':groups['main_rails']=group('main_rails',[],reason='none')
    elif fault=='no_cross':groups['cross_rails']=group('cross_rails',[],reason='none')
    elif fault=='edge_off_boundary':edge[0]['fixed_m']='2'
    elif fault=='unknown_profile':cross[0]['profile_ref']=''
    elif fault=='unknown_stock':panels[0]['stock_ref']=''
    elif fault=='unknown_approval':panels[0]['approved_by']=''
    elif fault=='legacy_contract':a['contract']='unapproved_old'
    elif fault=='extra_field':g['assumed_spacing_m']='0.6'
    elif fault=='different_rail_source':main[0]['source_ref']=''
    elif fault=='float_connector':joints[0]['x']=1.0
    elif fault=='double_profile_kind':
        cross[0].update(axis='x',fixed_m='0',start_m='0',end_m='4')
    elif fault=='duplicated_edge':
        edge.append(part('T2',axis='x',fixed_m='4',start_m='1',end_m='4',trim_ref='تکراری'))
    r=preview(d);assert not r['ready'] and r['rows']==[] and r['blockers'],(fault,r)


def test_projectstore_review_commit_and_boq_without_material_double_charge(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('نمونه سقف کاذب','P')
    d=sample();save=a.save_aec_system_draft('P',d,expected_revision=0);assert save['revision']==1
    a.review_roof_system('P','suspended_ceiling','L1','SC1',expected_revision=1,reviewer='بازبین مستقل',note='جانمایی مصنوعی')
    r=a.commit_aec_system('P','suspended_ceiling','L1','SC1',expected_revision=2)
    assert r['status']=='committed'
    proj=a.open_project('P')
    assert len(proj['takeoffs'])==7
    assert len(proj['boq'])==1
    assert Decimal(str(proj['boq'][0]['quantity']))==20
    assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    a.store.close()


def test_real_project_cas_and_rejected_ambiguous_ceiling(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('پروژه سقف','P');d=sample()
    a.save_aec_system_draft('P',d,expected_revision=0)
    b=StructuralProApp(tmp_path/'db')
    a.save_aec_system_draft('P',d,expected_revision=1)
    with pytest.raises(RuntimeError):b.save_aec_system_draft('P',d,expected_revision=1)
    altered=deepcopy(d);altered['architecture_detail']['groups']['panels']['items'].pop()
    # An incomplete draft may be stored for correction; it must not be reviewed or paid.
    a.save_aec_system_draft('P',altered,expected_revision=2)
    assert a.aec_workflow().preview('P','suspended_ceiling','L1','SC1')['rows']==[]
    with pytest.raises(ValueError):
        a.review_roof_system('P','suspended_ceiling','L1','SC1',expected_revision=3,reviewer='Reviewer',note='Invalid')
    with pytest.raises(ValueError):
        a.commit_aec_system('P','suspended_ceiling','L1','SC1',expected_revision=3)
    assert a.open_project('P')['boq']==[]
    a.store.close();b.store.close()


def test_overlap_between_independent_ceiling_records_is_rejected(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('نمونه مشترک','P')
    first=sample();app.save_aec_system_draft('P',first,expected_revision=0)
    second=deepcopy(first);second['system_id']='SC2';second['source']['source_id']='SOURCE-SC2';second['architecture_detail']['geometry']['physical_surface_id']='CEIL2'
    with pytest.raises(ValueError):app.save_aec_system_draft('P',second,expected_revision=0)
    assert len(app.open_project('P')['reviewed_aec_systems'])==1
    app.store.close()


def test_ceiling_and_ceiling_paint_same_host_conflict(tmp_path):
    from core.platform.application import StructuralProApp
    from test_paint_finish_phase1 import sample as paint_sample
    app=StructuralProApp(tmp_path/'db');app.create_project('نمونه تضاد پوشش', 'P')
    app.save_aec_system_draft('P',sample(),expected_revision=0)
    paint=paint_sample(face='ceiling')
    paint['building_id']='B1';paint['floor_id']='L1'
    paint['architecture_detail']['geometry'].update(host_id='SLAB1',space_id='ROOM1',
                 length_m='6',width_m='4',count='1')
    # Different measurement zones still cannot claim the same host ceiling.
    before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError,match='سقف|پوشش'):
        app.save_aec_system_draft('P',paint,expected_revision=0)
    assert before==app.open_project('P')
    app.store.close()


def test_same_physical_ceiling_id_on_different_host_is_rejected(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('هویت تکراری','P')
    app.save_aec_system_draft('P',sample(),expected_revision=0)
    other=deepcopy(sample());other['system_id']='SC2';other['source']['source_id']='NEW-SOURCE'
    other['architecture_detail']['geometry']['host_id']='OTHER-SLAB'
    before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError,match='هویت|شناسه|فیزیکی'):
        app.save_aec_system_draft('P',other,expected_revision=0)
    assert app.open_project('P')==before
    app.store.close()


def test_shared_panel_physical_id_across_distinct_ceiling_hosts_is_blocked(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('کنترل قطعه مشترک', 'P')
    app.save_aec_system_draft('P',sample(),expected_revision=0)
    second=deepcopy(sample());second['system_id']='SC2';second['source']['source_id']='SOURCE-OTHER'
    second['architecture_detail']['geometry'].update(physical_surface_id='OTHER-CEIL',host_id='OTHER-SLAB',space_id='OTHER-ROOM')
    with pytest.raises(ValueError,match='فیزیکی|تکرار'):
        app.save_aec_system_draft('P',second,expected_revision=0)
    assert len(app.open_project('P')['reviewed_aec_systems'])==1
    app.store.close()
