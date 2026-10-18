"""Engineering phase-one: documented, rectangular stone stair faces only."""
from copy import deepcopy
from decimal import Decimal
import pytest

from core.takeoff.reviewed_aec import empty_system, preview_system
from core.takeoff.engine import TakeoffEngine
from core.takeoff.stone_stair_finish_detail import CONTRACT


def item(ident,**kw):
    return dict(id=ident,physical_key='physical-ST-'+ident,
                source_ref='مدرک مستقل '+ident,approved_by='مهندس مستقل '+ident,**kw)


def sample():
    d=empty_system('stone_floor','FND','STONE-ST1')
    d.update(measurement_policy='architecture_specialist_v1',building_id='B1',axis='پله مصنوعی',
             source=dict(mode='manual',source_id='SRC-ST1',plan_ref='پلان پله',detail_ref='برش سنگ پله'))
    steps=[item('S1',tread_face_id='T1',riser_face_id='R1',riser_status='covered',riser_reason='')]
    faces=[item('T1',step_id='S1',face_kind='tread',length_m='1',width_m='.30',
                material_ref='سنگ تراورتن مصنوعی',payment_ref='مترمربع کف پله',
                layout_status='documented',layout_ref='نقشه T1'),
           item('R1',step_id='S1',face_kind='riser',length_m='1',width_m='.16',
                material_ref='سنگ تراورتن مصنوعی',payment_ref='مترمربع پیشانی',
                layout_status='documented',layout_ref='نقشه R1'),
           item('L1',step_id='none',face_kind='landing',length_m='2',width_m='1',
                material_ref='سنگ تراورتن مصنوعی',payment_ref='مترمربع پاگرد',
                layout_status='documented',layout_ref='نقشه L1')]
    stocks=[item('ST-'+f['id'],length_m=f['length_m'],width_m=f['width_m'],material_ref=f['material_ref']) for f in faces]
    pieces=[item('P-'+f['id'],face_id=f['id'],stock_id='ST-'+f['id'],piece_type='full',
                 x='0',y='0',width_m=f['length_m'],height_m=f['width_m'],
                 stock_x='0',stock_y='0',cut_ref='برش حقیقی '+f['id']) for f in faces]
    d['architecture_detail']=dict(contract=CONTRACT,geometry=dict(
        physical_stair_id='PHYSICAL-STAIR1',host_id='STRUCT-STAIR1',unit='m',count='1',
        repeat_ref='یک پله با یک کف و یک پیشانی و یک پاگرد مستقل',
        source_ref='برداشت پله مصنوعی',approved_by='مهندس'),
        steps=steps,faces=faces,openings=[],stocks=stocks,pieces=pieces,joints=[],
        consumptions=[item('BED',face_id='T1',operation='bedding',basis='constant_thickness',
              thickness_m='.02',rate='',rate_ref='ضخامت واقعی بستر مصنوعی',
              material_ref='ملات مصنوعی',quantity_unit='m3')])
    return d


def preview(data):return preview_system(data,TakeoffEngine())


def test_tread_riser_landing_are_separate_documented_area_and_material():
    d=sample();before=deepcopy(d);r=preview(d)
    assert r['ready'],r['blockers']
    paid={row['item_code']:Decimal(str(row['quantity'])) for row in r['rows'] if row['role']=='work'}
    assert paid=={'tread':Decimal('.30'),'riser':Decimal('.16'),'landing':Decimal('2')}
    assert all(row['role']=='material' for row in r['rows'] if row['item_code'] not in paid)
    assert any(v['item_code']=='bedding' and Decimal(str(v['quantity']))==Decimal('.006') for v in r['rows'])
    assert len({r['source_id'] for r in r['rows']})==len(r['rows'])
    assert d==before


@pytest.mark.parametrize('fault',[
 'tread_float','riser_boolean','count_float','count_unidentified_repeat','wrong_unit','missing_step','missing_tread',
 'missing_riser','missing_riser_status','orphan_face','orphan_piece','opening_unknown',
 'opening_conflict','piece_overlap','piece_missing','stock_missing','stock_mismatch',
 'stock_doubled','piece_outside','cut_ref_missing','false_full','purchase_unused',
 'repeated_identity','repeated_step','repeat_face','change_contract','missing_face_approval',
 'rate_float','rate_missing','invalid_rate_unit','invalid_thickness','two_beddings',
 'material_without_face','riser_without_reason','missing_material','face_layout_unknown',
 'wrong_stair_type','stock_float','piece_float','undercovered_face','bad_step_ref',
 'extra_assumed_waste','unsupported_geometry','unmeasured_nosing'
])
def test_unknown_geometry_or_material_is_fail_closed(fault):
    d=sample();a=d['architecture_detail'];steps=a['steps'];faces=a['faces'];pieces=a['pieces'];stocks=a['stocks']
    if fault=='tread_float':faces[0]['length_m']=1.0
    elif fault=='riser_boolean':faces[1]['width_m']=True
    elif fault=='count_float':a['geometry']['count']=1.0
    elif fault=='count_unidentified_repeat':a['geometry']['count']='2'
    elif fault=='wrong_unit':a['geometry']['unit']='cm'
    elif fault=='missing_step':steps.pop()
    elif fault=='missing_tread':steps[0]['tread_face_id']='WRONG'
    elif fault=='missing_riser':steps[0]['riser_face_id']='none'
    elif fault=='missing_riser_status':steps[0]['riser_status']='unknown'
    elif fault=='orphan_face':faces.append(item('OTHER',step_id='S2',face_kind='tread',length_m='1',width_m='1',material_ref='X',payment_ref='X',layout_status='documented',layout_ref='X'))
    elif fault=='orphan_piece':pieces[0]['face_id']='OTHER'
    elif fault=='opening_unknown':a['openings'].append(item('O1',face_id='OTHER',x='0',y='0',width_m='.1',height_m='.1'))
    elif fault=='opening_conflict':a['openings'].append(item('O1',face_id='T1',x='0',y='0',width_m='.1',height_m='.1'))
    elif fault=='piece_overlap':pieces.append(deepcopy(pieces[0]));pieces[-1].update(id='P2',physical_key='physical-P2')
    elif fault=='piece_missing':pieces.pop()
    elif fault=='stock_missing':pieces[0]['stock_id']='MISSING'
    elif fault=='stock_mismatch':stocks[0]['material_ref']='MISSING'
    elif fault=='stock_doubled':pieces[1]['stock_id']='ST-T1'
    elif fault=='piece_outside':pieces[0]['x']='.1'
    elif fault=='cut_ref_missing':pieces[0]['cut_ref']=''
    elif fault=='false_full':pieces[0]['piece_type']='cut'
    elif fault=='purchase_unused':stocks.append(item('EXTRA',length_m='1',width_m='1',material_ref='M'))
    elif fault=='repeated_identity':pieces[1]['physical_key']=pieces[0]['physical_key']
    elif fault=='repeated_step':steps.append(deepcopy(steps[0]));steps[-1]['id']='S2';steps[-1]['physical_key']='S2'
    elif fault=='repeat_face':faces[1]['id']='T1'
    elif fault=='change_contract':a['contract']='old_stair'
    elif fault=='missing_face_approval':faces[0]['approved_by']=''
    elif fault=='rate_float':a['consumptions'][0].update(basis='area_rate',thickness_m='',rate=.2,quantity_unit='kg')
    elif fault=='rate_missing':a['consumptions'][0]['rate_ref']=''
    elif fault=='invalid_rate_unit':a['consumptions'][0].update(basis='area_rate',thickness_m='',rate='2',quantity_unit='m3')
    elif fault=='invalid_thickness':a['consumptions'][0]['thickness_m']='-1'
    elif fault=='two_beddings':a['consumptions'].append(deepcopy(a['consumptions'][0]));a['consumptions'][-1].update(id='BED2',physical_key='BED2')
    elif fault=='material_without_face':a['consumptions'][0]['face_id']='MISSING'
    elif fault=='riser_without_reason':steps[0].update(riser_status='not_applicable',riser_face_id='none',riser_reason='')
    elif fault=='missing_material':faces[0]['material_ref']=''
    elif fault=='face_layout_unknown':faces[0]['layout_status']='area_only'
    elif fault=='wrong_stair_type':d['kind']='stone_cladding'
    elif fault=='stock_float':stocks[0]['length_m']=1.0
    elif fault=='piece_float':pieces[0]['x']=0.0
    elif fault=='undercovered_face':pieces[0]['height_m']='.20'
    elif fault=='bad_step_ref':faces[0]['step_id']='OTHER'
    elif fault=='extra_assumed_waste':stocks[0]['waste_pct']='.10'
    elif fault=='unsupported_geometry':a['geometry']['shape']='curved'
    elif fault=='unmeasured_nosing':faces[0]['nosing']='.02'
    r=preview(d)
    assert not r['ready'] and r['rows']==[] and r['blockers'],(fault,r)


def test_sibling_stair_or_piece_physical_collision_is_rejected(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('سنگ پله مصنوعی','P')
    one=sample();a.save_aec_system_draft('P',one,expected_revision=0)
    two=deepcopy(one);two['system_id']='STONE-ST2';two['source']['source_id']='SRC-ST2'
    with pytest.raises(ValueError):a.save_aec_system_draft('P',two,expected_revision=0)
    assert len(a.open_project('P')['reviewed_aec_systems'])==1
    a.store.close()


def test_projectstore_sqlite_review_commit_and_material_deduplication(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('سنگ پله مصنوعی','P')
    d=sample();saved=a.save_aec_system_draft('P',d,expected_revision=0)
    assert saved['revision']==1
    a.review_roof_system('P','stone_floor','FND','STONE-ST1',expected_revision=1,reviewer='بازبین مستقل',note='کنترل دیتایل')
    commit=a.commit_aec_system('P','stone_floor','FND','STONE-ST1',expected_revision=2)
    assert commit['status']=='committed'
    project=a.open_project('P')
    assert len(project['boq'])==3
    assert sum((Decimal(str(v['quantity'])) for v in project['boq']),Decimal(0))==Decimal('2.46')
    assert len(project['takeoffs'])>len(project['boq'])
    assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
    a.store.close()


def test_bad_stone_stair_draft_never_enters_boq(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('سنگ پله مصنوعی','P')
    d=sample();d['architecture_detail']['faces'][0]['length_m']=1.0
    a.save_aec_system_draft('P',d,expected_revision=0)
    result=a.aec_workflow().preview('P','stone_floor','FND','STONE-ST1')
    assert not result['ready'] and result['rows']==[]
    with pytest.raises(ValueError):a.review_roof_system('P','stone_floor','FND','STONE-ST1',expected_revision=1,reviewer='مستقل',note='نامعتبر')
    with pytest.raises(ValueError):a.commit_aec_system('P','stone_floor','FND','STONE-ST1',expected_revision=1)
    assert a.open_project('P')['boq']==[]
    a.store.close()


def test_draft_copy_resets_physical_ids_and_requires_new_approval(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('کپی پله', 'P')
    original=sample();app.save_aec_system_draft('P',original,expected_revision=0)
    copy=app.aec_workflow().copy_roof('P','stone_floor','FND','STONE-ST1',new_system_id='STONE-ST2',new_source_id='SRC-ST2',reason='پله مستقل جدید')['data']
    assert copy['architecture_detail']['geometry']['physical_stair_id']!='PHYSICAL-STAIR1'
    assert copy['architecture_detail']['geometry']['host_id']!='STRUCT-STAIR1'
    assert copy['architecture_detail']['faces'][0]['step_id']==copy['architecture_detail']['steps'][0]['id']
    assert copy['architecture_detail']['pieces'][0]['face_id']==copy['architecture_detail']['faces'][0]['id']
    assert not preview(copy)['ready']
    assert app.open_project('P')['boq']==[]
    app.store.close()


def test_amendment_stair_identity_is_immutable_after_commit(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'db');app.create_project('اصلاحیه پله', 'P')
    d=sample();app.save_aec_system_draft('P',d,expected_revision=0)
    app.review_roof_system('P','stone_floor','FND','STONE-ST1',expected_revision=1,reviewer='مستقل',note='کنترل')
    app.commit_aec_system('P','stone_floor','FND','STONE-ST1',expected_revision=2)
    r=app.open_project('P');prior=deepcopy(r['boq'])
    from core.takeoff.architecture_detail import validate_amendment
    bad=deepcopy(d);bad['architecture_detail']['geometry']['physical_stair_id']='ANOTHER'
    with pytest.raises(ValueError,match='هویت'):
        validate_amendment(d,bad,[],[])
    assert app.open_project('P')['boq']==prior
    app.store.close()
