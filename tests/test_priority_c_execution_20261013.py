"""Independent physical schedule and AEC material routing regressions."""
from copy import deepcopy

import pytest

from core.projects.store import ProjectStore
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import SPECS, ReviewedAECWorkflow, empty_system, preview_system


def reviewed(kind, identity='S1'):
    data = empty_system(kind, 'L1', identity)
    data['source'] = {'mode': 'manual', 'source_id': f'manual:{kind}:{identity}'}
    for name in SPECS[kind].components:
        data['components'][name] = {'status': 'not_applicable', 'approved_by': 'independent-checker',
            'reason': 'absent in schedule', 'source_ref': f'A1:{name}'}
    return data


def detail(name, method, entries):
    return {'status': 'confirmed', 'approved_by': 'independent-checker', 'items': [{
        'line_id': name, 'item_code': name, 'description': name, 'domain': 'building',
        'mode': 'detail', 'detail_type': method, 'details': {'entries': entries},
        'source_ref': f'A1:{name}'}]}


def physical(identity, **values):
    return {'id': identity, 'source_ref': f'A1:{identity}', 'approved_by': 'independent-checker', **values}


def engine_part(name, route, params):
    return {'status': 'confirmed', 'approved_by': 'independent-checker', 'items': [{
        'line_id': name, 'item_code': name, 'description': name, 'domain': route[0],
        'mode': 'engine', 'item': route[1], 'params': params, 'source_ref': f'A1:{name}'}]}


@pytest.mark.parametrize('component', ['columns', 'beams', 'plates'])
def test_rebar_weight_cannot_be_billed_as_structural_steel(component):
    data = reviewed('steel_frame')
    for name in ('columns', 'beams'):
        data['components'][name] = detail(name, 'steel_profile_schedule', [physical(name,
            count=1, length_m=3, unit_weight_kg_m=20, unit_weight_source='supplier-schedule')])
    data['components'][component] = engine_part(component, ('building', 'rebar'),
        {'length': 3, 'unit_weight': 20, 'count': 1})
    result = preview_system(data, TakeoffEngine())
    assert not result['ready'], 'Rebar and structural steel both use kg but are different materials'
    assert any('مصالح' in blocker for blocker in result['blockers'])


def test_concrete_engine_cannot_be_billed_as_timber_volume(tmp_path):
    store = ProjectStore(tmp_path / 'project.db')
    store.save('P1', {'id': 'P1', 'takeoffs': [], 'boq': []})
    workflow = ReviewedAECWorkflow(store, TakeoffEngine())
    data = reviewed('timber_frame')
    data['components']['members'] = engine_part('members', ('advanced', 'footing_concrete'),
        {'length': 3, 'width': .1, 'thickness': .2, 'count': 4})
    workflow.save_draft('P1', data)
    before = deepcopy(store.get('P1'))
    with pytest.raises(ValueError, match='مصالح'):
        workflow.commit('P1', 'timber_frame', 'L1', 'S1', expected_revision=1)
    assert store.get('P1') == before
    store.close()


def test_independent_steel_schedule_survives_database_reopen(tmp_path):
    # Independent explicit reference schedule (not an engine-generated oracle):
    # columns 2*3.2*23.4=149.76 kg; beams 3*4.5*18.8=253.8 kg;
    # plates 8*.25*.20*.012*7850=37.68 kg; total 441.24 kg.
    path = tmp_path / 'steel.db'
    store = ProjectStore(path)
    store.save('P1', {'id': 'P1', 'takeoffs': [], 'boq': []})
    workflow = ReviewedAECWorkflow(store, TakeoffEngine())
    data = reviewed('steel_frame')
    data['components']['columns'] = detail('columns', 'steel_profile_schedule', [physical('C1-C2',
        count=2, length_m=3.2, unit_weight_kg_m=23.4, unit_weight_source='explicit-column-certificate')])
    data['components']['beams'] = detail('beams', 'steel_profile_schedule', [physical('B1-B3',
        count=3, length_m=4.5, unit_weight_kg_m=18.8, unit_weight_source='explicit-beam-certificate')])
    data['components']['plates'] = detail('plates', 'steel_plate_schedule', [physical('P1-P8',
        count=8, length_m=.25, width_m=.20, thickness_m=.012,
        density_kg_m3=7850, density_source='explicit-density-certificate')])
    workflow.save_draft('P1', data)
    assert workflow.commit('P1', 'steel_frame', 'L1', 'S1', expected_revision=1)['takeoff_rows'] == 3
    store.close()
    reopened = ProjectStore(path)
    project = reopened.get('P1')
    amounts = {row['review']['component']: row['quantities'][0]['amount'] for row in project['takeoffs']}
    assert amounts == pytest.approx({'columns': 149.76, 'beams': 253.8, 'plates': 37.68})
    assert sum(row['quantity'] for row in project['boq']) == pytest.approx(441.24)
    assert all(row['unit'] == 'kg' and row.get('unit_price') is None for row in project['boq'])
    assert project['takeoffs'][2]['params']['details'][0]['input']['density_source'] == 'explicit-density-certificate'
    reopened.close()


def test_independent_timber_schedule_survives_database_reopen(tmp_path):
    # Actual rectangular schedule: posts 4*2.8*.12*.12=.16128 m3;
    # beams 2*4.2*.10*.20=.168 m3; total .32928 m3.
    path = tmp_path / 'timber.db'
    store = ProjectStore(path)
    store.save('P1', {'id': 'P1', 'takeoffs': [], 'boq': []})
    workflow = ReviewedAECWorkflow(store, TakeoffEngine())
    data = reviewed('timber_frame')
    data['components']['members'] = detail('members', 'timber_volume_schedule', [
        physical('posts', count=4, length_m=2.8, width_m=.12, depth_m=.12),
        physical('beams', count=2, length_m=4.2, width_m=.10, depth_m=.20)])
    workflow.save_draft('P1', data)
    workflow.commit('P1', 'timber_frame', 'L1', 'S1', expected_revision=1)
    store.close()
    reopened = ProjectStore(path)
    project = reopened.get('P1')
    assert project['boq'][0]['quantity'] == pytest.approx(.32928)
    assert project['boq'][0]['unit'] == 'm3'
    parts = project['takeoffs'][0]['params']['details']
    assert [part['quantity'] for part in parts] == pytest.approx([.16128, .168])
    assert [part['id'] for part in parts] == ['posts', 'beams']
    reopened.close()


def test_independent_uboot_gross_minus_void_persists_once(tmp_path):
    # 6*5*.30=9 m3 gross; 40 verified voids *.035=1.4 m3;
    # independent reviewed net reference =7.6 m3, no positive void BOQ row.
    path = tmp_path / 'roof.db'
    store = ProjectStore(path)
    store.save('P1', {'id': 'P1', 'takeoffs': [], 'boq': []})
    workflow = ReviewedAECWorkflow(store, TakeoffEngine())
    data = reviewed('uboot')
    data['components']['gross_concrete'] = detail('gross_concrete', 'concrete_regions', [
        physical('bay-A', length_m=6, width_m=5, thickness_m=.30, voids=[])])
    for name, quantity, unit in [('verified_voids', 1.4, 'm3'), ('reinforcement', 240, 'kg')]:
        data['components'][name] = {'status': 'confirmed', 'approved_by': 'independent-checker', 'items': [{
            'line_id': name, 'item_code': name, 'description': name, 'domain': 'building', 'mode': 'measured',
            'quantity': quantity, 'unit': unit, 'formula': '40 x .035' if name == 'verified_voids' else 'approved bar schedule',
            'source_ref': f'A1:{name}', 'measurement_ref': f'independent:{name}'}]}
    workflow.save_draft('P1', data)
    workflow.commit('P1', 'uboot', 'L1', 'S1', expected_revision=1)
    store.close()
    reopened = ProjectStore(path)
    project = reopened.get('P1')
    rows = {row['review']['component']: row for row in project['takeoffs']}
    assert set(rows) == {'gross_concrete', 'reinforcement'}
    assert rows['gross_concrete']['quantities'][0]['amount'] == pytest.approx(7.6)
    assert rows['gross_concrete']['params']['gross_m3'] == 9
    assert rows['gross_concrete']['params']['deduction']['quantity_m3'] == 1.4
    assert len(project['boq']) == 2
    reopened.close()


def test_physical_steel_schedule_cannot_be_repeated_under_new_line_id():
    data = reviewed('steel_frame')
    for name in ('columns', 'beams'):
        data['components'][name] = detail(name, 'steel_profile_schedule', [physical(name,
            count=1, length_m=3, unit_weight_kg_m=20, unit_weight_source='supplier-schedule')])
    duplicate = deepcopy(data['components']['columns']['items'][0])
    duplicate['line_id'] = 'second-line-same-physical-columns'
    data['components']['columns']['items'].append(duplicate)
    result = preview_system(data, TakeoffEngine())
    assert not result['ready'], 'Changing a BOQ line label does not create a new physical member'
    assert any('تکراری' in blocker for blocker in result['blockers'])
