"""Regression: stale desktop instances must not overwrite takeoffs or duplicate an identity."""
import pytest

from core.platform.application import StructuralProApp


FINISH = {
    'count': 1, 'length': 5, 'height': 3, 'openings': 0,
    'layers': 1, 'consumption_per_m2_per_layer': 2,
    'consumption_unit': 'kg', 'material_spec_ref': 'SPEC-001',
    'waste_factor': 0,
}


def test_separate_instance_cannot_duplicate_finishing_location(tmp_path):
    first = StructuralProApp(tmp_path)
    first.create_project('پروژه', 'p1')
    second = StructuralProApp(tmp_path)
    second.open_project('p1')  # prime a stale cache
    first.add_assembly_takeoff('p1', 'wall_tile', FINISH, floor_id='اول', location_id='حمام')
    with pytest.raises(ValueError, match='تکراری'):
        second.add_assembly_takeoff('p1', 'wall_tile', FINISH, floor_id='اول', location_id='حمام')
    stored = StructuralProApp(tmp_path).open_project('p1')
    assert len(stored['takeoff_assemblies']) == 1
    assert len(stored['takeoffs']) == 3
    assert len(stored['boq']) == 1
    first.store.close()
    second.store.close()


def test_second_instance_preserves_other_floor_and_payable_boq(tmp_path):
    first = StructuralProApp(tmp_path)
    first.create_project('پروژه', 'p1')
    second = StructuralProApp(tmp_path)
    second.open_project('p1')  # prime a stale cache
    first.add_assembly_takeoff('p1', 'wall_tile', FINISH, floor_id='اول', location_id='حمام')
    second.add_assembly_takeoff('p1', 'wall_tile', FINISH, floor_id='دوم', location_id='حمام')
    stored = StructuralProApp(tmp_path).open_project('p1')
    assert len(stored['takeoff_assemblies']) == 2
    assert len(stored['takeoffs']) == 6
    assert len(stored['boq']) == 1
    assert stored['boq'][0]['quantity'] == pytest.approx(30)
    assert sorted(x['floor_id'] for x in stored['takeoff_assemblies']) == ['اول', 'دوم']
    first.store.close()
    second.store.close()


def test_ordinary_takeoff_cross_instance_preserves_previous_rows(tmp_path):
    first = StructuralProApp(tmp_path)
    first.create_project('پروژه', 'p1')
    second = StructuralProApp(tmp_path)
    second.open_project('p1')
    first.add_takeoff('p1', 'building', 'slab_volume', length=2, width=2, thickness=1,
                      source_id='S1')
    second.add_takeoff('p1', 'building', 'slab_volume', length=3, width=3, thickness=1,
                       source_id='S2')
    stored = StructuralProApp(tmp_path).open_project('p1')
    assert len(stored['takeoffs']) == 2
    assert {t['source_id'] for t in stored['takeoffs']} == {'S1', 'S2'}
    first.store.close()
    second.store.close()


def test_optimistic_save_refuses_mid_operation_overwrite(tmp_path, monkeypatch):
    first = StructuralProApp(tmp_path)
    first.create_project('پروژه', 'p1')
    second = StructuralProApp(tmp_path)
    original_save = first.store.save
    injection = {'called': False}

    def overlapping_save(pid, project, *, expected_digest=None):
        if not injection['called']:
            injection['called'] = True
            second.add_takeoff('p1', 'building', 'slab_volume', length=2, width=2,
                               thickness=1, source_id='external')
        return original_save(pid, project, expected_digest=expected_digest)

    monkeypatch.setattr(first.store, 'save', overlapping_save)
    with pytest.raises(RuntimeError, match='project changed since write began'):
        first.add_assembly_takeoff('p1', 'wall_tile', FINISH,
                                   floor_id='اول', location_id='حمام')
    stored = StructuralProApp(tmp_path).open_project('p1')
    assert len(stored['takeoffs']) == 1
    assert stored['takeoffs'][0]['source_id'] == 'external'
    assert len(stored.get('takeoff_assemblies', [])) == 0
    first.store.close()
    second.store.close()