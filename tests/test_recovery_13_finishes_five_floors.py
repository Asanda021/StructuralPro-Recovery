"""Actual application/SQLite/BOQ acceptance for 13 finishing operations × 5 floors.

Inputs are explicit SYNTHETIC fixtures, not inferred engineering quantities.
The test does not validate Persian Windows GUI or visually inspect reports.
"""
import pytest

from core.platform.application import StructuralProApp

WALL = (
    'gypsum_scratch', 'gypsum_finish', 'cement_render', 'wall_tile',
    'wall_paint', 'waterproofing_wall', 'facade_finish',
)
HORIZONTAL = (
    'floor_tile', 'floor_screed', 'ceiling_paint',
    'false_ceiling', 'waterproofing_floor',
)
LINEAR = ('skirting',)
CODES = WALL + HORIZONTAL + LINEAR


def explicit_inputs(code):
    common = dict(count=1, waste_factor=0.1, consumption_unit='kg',
                  material_spec_ref='SYNTHETIC-SPEC-001')
    if code in WALL:
        return {**common, 'length':10, 'height':3, 'openings':2,
                'layers':2, 'consumption_per_m2_per_layer':4}
    if code in HORIZONTAL:
        return {**common, 'length':5, 'width':4, 'openings':1,
                'layers':2, 'consumption_per_m2_per_layer':4}
    return {**common, 'length':7, 'deductions':1, 'consumption_per_m':3}


@pytest.mark.parametrize('code', CODES)
def test_each_finishing_operation_cross_floor_round_trip_and_no_double_boq(code, tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project('پروژه آزمایشی', 'p')
    for floor in range(1, 6):
        result = app.add_assembly_takeoff(
            'p', code, explicit_inputs(code), floor_id=f'طبقه {floor}',
            location_id='موقعیت نمونه')
        assert {row['component_role'] for row in result['rows']} == {
            'work', 'procurement', 'material'}
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    project = reopened.open_project('p')
    assert len(project['takeoff_assemblies']) == 5
    assert len(project['takeoffs']) == 15
    assert len(project['boq']) == 1
    boq = project['boq'][0]
    expected_unit = 'm' if code in LINEAR else 'm2'
    expected_per_floor = 6 if code in LINEAR else (19 if code in HORIZONTAL else 28)
    assert boq['item_code'] == code+'_work'
    assert boq['unit'] == expected_unit
    assert boq['quantity'] == pytest.approx(expected_per_floor*5)
    assert len([t for t in project['takeoffs'] if t['component_role']=='material'])==5
    with pytest.raises(ValueError, match='تکراری'):
        reopened.add_assembly_takeoff('p', code, explicit_inputs(code),
                                      floor_id='طبقه 1', location_id='موقعیت نمونه')
    reopened.store.close()


def test_all_13_operations_in_single_five_floor_project_preserve_units_and_roles(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project('پروژه جامع آزمایشی', 'p')
    for floor in range(1, 6):
        for code in CODES:
            app.add_assembly_takeoff('p', code, explicit_inputs(code),
                                    floor_id=f'طبقه {floor}', location_id='موقعیت نمونه')
    app.store.close()
    reopened = StructuralProApp(tmp_path)
    project = reopened.open_project('p')
    assert len(project['takeoff_assemblies']) == 65
    assert len(project['takeoffs']) == 195
    assert len(project['boq']) == 13
    by_code = {r['item_code']:r for r in project['boq']}
    assert set(by_code)=={code+'_work' for code in CODES}
    assert by_code['skirting_work']['unit']=='m'
    assert by_code['wall_tile_work']['unit']=='m2'
    assert by_code['floor_tile_work']['unit']=='m2'
    assert by_code['wall_tile_work']['quantity']==pytest.approx(140)
    assert by_code['floor_tile_work']['quantity']==pytest.approx(95)
    assert by_code['skirting_work']['quantity']==pytest.approx(30)
    assert {r['component_role'] for r in project['takeoffs']} == {'work','procurement','material'}
    assert len({r['source_id'] for r in project['takeoffs']}) == 195
    reopened.store.close()
