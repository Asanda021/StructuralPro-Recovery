"""Stage 2.3 source-backed synthetic quantity acceptance, not structural design."""
from copy import deepcopy
from decimal import Decimal
import pytest
from core.takeoff.reviewed_structural import empty_member, preview_member, KINDS
from core.takeoff.engine import TakeoffEngine
from core.platform.application import StructuralProApp


def sample(kind='tie_beam', member='T1', count='2'):
    d=empty_member(kind,'L1',member)
    d.update(building_id='B1',measurement_policy='foundation_tie_specialist_v1')
    d['source']={'mode':'manual','source_id':f'synthetic:{kind}:{member}',
                 'plan_ref':'plan synthetic','detail_ref':'detail synthetic'}
    is_tie=kind=='tie_beam'
    geom={'length':'6' if is_tie else '2','width':'.3' if is_tie else '1.5',
          ('depth' if is_tie else 'thickness'):'.5','count':count,
          'shape':'rectangular','source_ref':'section synthetic',
          'approved_by':'geometry reviewer','repeat_scope':'identical_members',
          'intersection_scope':'per_member' if is_tie else 'total_group',
          'intersection_ref':'joint schedule synthetic',
          'intersections':[{'id':'joint-1','volume_m3':'.2' if is_tie else '.1',
                            'source_ref':'joint synthetic','approved_by':'geometry reviewer'}]}
    geom['variable_units']={k:('عدد' if k=='count' else 'm') for k in ('length','width',('depth' if is_tie else 'thickness'),'count')}
    d['geometry']=geom
    d['formwork']={'status':'confirmed','source_ref':'form schedule synthetic',
        'approved_by':'form reviewer','area_scope':'per_member','area_scope_ref':'per member synthetic',
        'surfaces':[{'id':'side1','contact':True,'gross_area_m2':'2.4','source_ref':'form section','approved_by':'form reviewer',
                     'deductions':[{'id':'void1','area_m2':'.4','source_ref':'form section','approved_by':'form reviewer'}]},
                    {'id':'side2','contact':False,'gross_area_m2':'3','source_ref':'earth contact','approved_by':'form reviewer','deductions':[]}]}
    for k in d['rebars']:
        d['rebars'][k]={'status':'not_applicable','reason':'only a synthetic reviewed schedule',
            'source_ref':f'{k} schedule synthetic','approved_by':'rebar reviewer'}
    d['rebars']['longitudinal' if is_tie else 'bottom_x']={
        'status':'confirmed','source_ref':'steel synthetic','approved_by':'steel reviewer',
        'count_scope':'per_member','count_scope_ref':'per member',
        'segments':[{'id':'steel-1','count':'4','nominal_diameter_mm':'10',
                     'shape_ref':'cut-detail-1','cut_length_m':'6.7' if is_tie else '2.4',
                     'cut_length_ref':'cut schedule','unit_weight_kg_m':'.617',
                     'unit_weight_source':'reviewed artificial table','source_ref':'detail synthetic',
                     'approved_by':'steel reviewer'}]}
    if is_tie:
        d['rebars']['stirrups']={'status':'confirmed','source_ref':'ties schedule','approved_by':'steel reviewer',
          'count_scope':'per_member','count_scope_ref':'per physical tie beam',
          'segments':[{'id':f'station-{i}', 'count':'5','nominal_diameter_mm':'8','shape_ref':'tie detail',
                       'cut_length_m':'1.4','cut_length_ref':'tie cut schedule',
                       'unit_weight_kg_m':'.395','unit_weight_source':'reviewed artificial table',
                       'source_ref':'ties detail','approved_by':'steel reviewer',
                       'start_m':str(i*3),'end_m':str((i+1)*3),
                       'first_bar_m':str(Decimal(i*3)+Decimal('.2')),
                       'last_bar_m':str(Decimal(i*3)+Decimal('2.6')),
                       'spacing_m':'.6'} for i in range(2)]}
    return d


def amounts(d):
    r=preview_member(d,TakeoffEngine())
    assert r['ready'],r['blockers']
    return {row['source_id'].split(':')[-1]:Decimal(str(row['quantity'])) for row in r['rows']}


def test_tie_beam_decimal_volume_form_and_steel():
    q=amounts(sample())
    assert q['concrete']==Decimal('1.4')
    assert q['formwork']==Decimal('4.0')
    assert q['longitudinal']==Decimal('33.0712')
    assert q['stirrups']==Decimal('11.06')


@pytest.mark.parametrize('kind', ['isolated_footing','strip_footing','mat_footing','pile_cap'])
def test_foundations_explicit_volume_formwork_and_rebar(kind):
    q=amounts(sample(kind))
    assert q['concrete']==Decimal('2.9')
    assert q['formwork']==Decimal('4')
    assert q['bottom_x']==Decimal('11.8464')


@pytest.mark.parametrize('mutate',[
  lambda d:d['geometry']['variable_units'].update(width='m2'),
  lambda d:d['geometry']['variable_units'].pop('width'),
  lambda d:d['geometry'].update(length='NaN'),
  lambda d:d['geometry'].update(width='-0.3'),
  lambda d:d['geometry'].update(count='1.5'),
  lambda d:d['geometry'].update(shape='reviewed_sections'),
  lambda d:d['geometry'].update(repeat_scope=None),
  lambda d:d['geometry'].update(intersection_scope=None),
  lambda d:d['geometry']['intersections'].append({'id':'joint-1','volume_m3':'.02','approved_by':'x','source_ref':'x'}),
  lambda d:d['formwork']['surfaces'][0].update(contact=None),
  lambda d:d['formwork']['surfaces'][0].update(gross_area_m2='0.1'),
  lambda d:d['formwork']['surfaces'].append(deepcopy(d['formwork']['surfaces'][0])),
  lambda d:d['rebars']['longitudinal']['segments'][0].update(id='station-0'),
  lambda d:d['rebars']['longitudinal']['segments'][0].update(cut_length_m='Infinity'),
  lambda d:d['rebars']['longitudinal']['segments'][0].update(length_parts_m=[{'kind':'straight','length_m':'6.7','source_ref':'x'}]),
  lambda d:d['rebars']['stirrups']['segments'][1].update(first_bar_m='2.6'),
  lambda d:d['rebars']['stirrups']['segments'][1].update(start_m='2.9'),
  lambda d:d['rebars']['stirrups']['segments'][0].update(count='4'),
  lambda d:d['rebars']['stirrups']['segments'][1].update(end_m='5.9'),
])
def test_fail_closed_bad_tie_beam(mutate):
    d=sample();mutate(d)
    assert not preview_member(d,TakeoffEngine())['ready']


def test_sqlite_boq_original_rows_and_double_count_guard(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('مثال فرضی','P')
    a=sample(); b=sample('isolated_footing',member='F1')
    app.save_structural_member_draft('P',a,expected_revision=0)
    app.save_structural_member_draft('P',b,expected_revision=0)
    app.commit_structural_member('P','tie_beam','L1','T1',expected_revision=1)
    before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError):app.commit_structural_member('P','tie_beam','L1','T1',expected_revision=1)
    with pytest.raises(ValueError):app.save_structural_member_draft('P',a,expected_revision=1)
    with pytest.raises(ValueError):app.commit_structural_member('P','isolated_footing','L1','F1',expected_revision=1)
    assert app.open_project('P')['takeoffs']==before['takeoffs']
    assert app.open_project('P')['boq']==before['boq']
    app.store.close()
    reopened=StructuralProApp(tmp_path)
    p=reopened.open_project('P')
    assert p['boq']==before['boq']
    assert p['reviewed_structural_members']==before['reviewed_structural_members']
    reopened.store.close()


def test_multiple_distinct_intersections_allow_two_members(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('مثال فرضی','P')
    for d in (sample(),sample('isolated_footing',member='F1')):
        d['geometry']['intersections'][0]['id']+=d['member_id']
        app.save_structural_member_draft('P',d,expected_revision=0)
        app.commit_structural_member('P',d['kind'],d['floor_id'],d['member_id'],expected_revision=1)
    p=app.open_project('P');assert len(p['takeoffs'])==7
    assert p['boq']
    app.store.close()


def test_revised_draft_cannot_keep_unreviewed_components(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('مثال فرضی','P')
    a=sample();app.save_structural_member_draft('P',a,expected_revision=0)
    other=deepcopy(a);other['geometry']['width']='.31'
    with pytest.raises(ValueError):app.save_structural_member_draft('P',other,expected_revision=1)
    app.store.close()


def test_stage23_cannot_downgrade_or_swap_member_identity(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('مثال فرضی','P')
    first=sample();app.save_structural_member_draft('P',first,expected_revision=0)
    downgrade=deepcopy(first);downgrade.pop('measurement_policy')
    with pytest.raises(ValueError,match='حذف قرارداد'):
        app.save_structural_member_draft('P',downgrade,expected_revision=1)
    mismatch=deepcopy(first);mismatch['building_id']='other building'
    with pytest.raises(ValueError,match='هویت'):
        app.save_structural_member_draft('P',mismatch,expected_revision=1)
    assert app.get_structural_member('P','tie_beam','L1','T1')['revision']==1
    app.store.close()


def test_stage23_exact_cm_mm_conversion_and_long_decimals():
    d=sample('isolated_footing')
    g=d['geometry']
    g.update(length='200',width='150',thickness='500')
    g['variable_units'].update(length='cm',width='cm',thickness='mm')
    assert amounts(d)['concrete']==Decimal('2.9')
    g['width']='150.000000000000000000000000000000001'
    assert amounts(d)['concrete']>Decimal('2.9')


def test_stage23_invalid_policy_on_column_fails_closed():
    d=sample('tie_beam');d['kind']='column'
    assert not preview_member(d,TakeoffEngine())['ready']
