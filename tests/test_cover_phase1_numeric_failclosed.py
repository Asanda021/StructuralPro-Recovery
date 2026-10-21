"""Phase-one exact takeoff guards for documented ceramic and stone covers.

Only synthetic dimensions: no source drawings, payment authority or design
acceptance is inferred from these tests.
"""
from copy import deepcopy
from decimal import Decimal

import pytest

from test_architecture_specialist_work import obj
from test_cover_specialist_work import sample, result


KINDS = ('ceramic_finish', 'stone_floor', 'stone_cladding')


def _adhesive(document, *, rate='1.25', unit='kg'):
    document['architecture_detail']['consumptions'] = [
        obj('BOND', surface_id='LAYER', operation='adhesive',
            basis='area_rate', thickness_m='', rate=rate,
            rate_ref='مدرک مستقل مصرف مصنوعی',
            material_ref='مصالح مستقل مصنوعی', quantity_unit=unit)
    ]


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('where', [
    'geometry_length', 'geometry_count', 'opening_width', 'surface_height',
    'stock_length', 'installed_piece_width', 'piece_stock_x', 'material_rate',
    'material_thickness',
])
def test_float_is_not_documented_measurement(kind, where):
    data = sample(kind)
    detail = data['architecture_detail']
    _adhesive(data)
    if where == 'geometry_length':
        detail['geometry']['length_m'] = 3.0
    elif where == 'geometry_count':
        detail['geometry']['count'] = 1.0
    elif where == 'opening_width':
        detail['openings'][0]['width_m'] = 1.0
    elif where == 'surface_height':
        detail['surfaces'][0]['height_m'] = 2.0
    elif where == 'stock_length':
        detail['stocks'][0]['length_m'] = 2.0
    elif where == 'installed_piece_width':
        detail['pieces'][0]['width_m'] = 2.0
    elif where == 'piece_stock_x':
        detail['pieces'][0]['stock_x'] = 0.0
    elif where == 'material_rate':
        detail['consumptions'][0]['rate'] = 1.25
    elif where == 'material_thickness':
        detail['consumptions'][0].update(
            basis='constant_thickness', rate='', thickness_m=0.01,
            quantity_unit='m3')
    preview = result(data)
    assert preview['ready'] is False
    assert preview['rows'] == []
    assert preview['blockers']


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('where', ['geometry_count', 'stock_length', 'material_rate'])
def test_boolean_is_not_a_measurement(kind, where):
    data = sample(kind)
    _adhesive(data)
    if where == 'geometry_count':
        data['architecture_detail']['geometry']['count'] = True
    elif where == 'stock_length':
        data['architecture_detail']['stocks'][0]['length_m'] = False
    else:
        data['architecture_detail']['consumptions'][0]['rate'] = True
    preview = result(data)
    assert not preview['ready'] and preview['rows'] == []


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('fault', [
    'unknown_unit', 'wrong_material_rate', 'late_duplicate_consumption',
    'unreferenced_stock', 'uncovered_layout',
])
def test_late_validation_failure_never_exposes_partial_area_or_procurement(kind, fault):
    data = sample(kind)
    detail = data['architecture_detail']
    if fault == 'unknown_unit':
        _adhesive(data, unit='litre')
    elif fault == 'wrong_material_rate':
        _adhesive(data, rate='not-measured')
    elif fault == 'late_duplicate_consumption':
        _adhesive(data)
        duplicate = deepcopy(detail['consumptions'][0])
        duplicate.update(id='BOND2', physical_key='physical-BOND2')
        detail['consumptions'].append(duplicate)
    elif fault == 'unreferenced_stock':
        detail['stocks'].append(obj('EXTRA', length_m='1', width_m='1',
                                    material_ref='مشخصات قطعه مصنوعی'))
    elif fault == 'uncovered_layout':
        detail['pieces'].pop()
    preview = result(data)
    assert preview['ready'] is False
    assert preview['rows'] == []
    assert preview['blockers']


@pytest.mark.parametrize('kind', KINDS)
def test_precision_preserved_without_float_rate_or_assumed_thickness(kind):
    data = sample(kind)
    _adhesive(data, rate='1.250000000000000000000001')
    original = deepcopy(data)
    preview = result(data)
    assert preview['ready'], preview['blockers']
    adhesive = next(row for row in preview['rows'] if row['item_code'] == 'adhesive')
    assert Decimal(str(adhesive['quantity'])) == Decimal('6.250000000000000000000005')
    assert adhesive['role'] == 'material'
    assert data == original
    works = [row for row in preview['rows'] if row['role'] == 'work']
    assert len(works) == 1 and Decimal(str(works[0]['quantity'])) == 5


def test_opening_deduction_is_not_applied_twice_to_any_cover():
    data = sample('ceramic_finish')
    p = deepcopy(data['architecture_detail']['surfaces'][0])
    p.update(id='LAYER-2', physical_key='OTHER-SURFACE', layer_key='OTHER-LAYER')
    data['architecture_detail']['surfaces'].append(p)
    preview = result(data)
    assert not preview['ready'] and preview['rows'] == []


@pytest.mark.parametrize('kind', KINDS)
def test_invalid_material_can_remain_a_draft_but_never_reaches_review_or_boq(kind, tmp_path):
    from core.platform.application import StructuralProApp

    app = StructuralProApp(tmp_path / 'db')
    app.create_project('پروژه مصنوعی کنترل کاشی و سنگ', 'P')
    documented = sample(kind)
    first = app.save_aec_system_draft('P', documented, expected_revision=0)
    assert first['revision'] == 1
    changed = deepcopy(documented)
    _adhesive(changed, rate=0.85)
    # The generic workflow intentionally supports incomplete editable drafts.
    # Numeric validation belongs at preview, independent review and commit.
    second = app.save_aec_system_draft('P', changed, expected_revision=1)
    assert second['revision'] == 2 and second['status'] == 'draft'
    preview = app.aec_workflow().preview('P', kind, 'L1', 'C1')
    assert preview['ready'] is False and preview['rows'] == []
    with pytest.raises(ValueError):
        app.review_roof_system('P', kind, 'L1', 'C1', expected_revision=2,
                               reviewer='بازبین مستقل', note='کنترل سند عددی')
    with pytest.raises(ValueError):
        app.commit_aec_system('P', kind, 'L1', 'C1', expected_revision=2)
    after = app.open_project('P')
    assert len(after['reviewed_aec_systems']) == 1
    assert after['takeoffs'] == [] and after['boq'] == []
    assert app.store.db.execute('pragma integrity_check').fetchone()[0] == 'ok'
    app.store.close()
