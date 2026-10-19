"""Explicit numeric counterexamples for legacy float adapters (not design acceptance)."""
import pytest
from core.takeoff.modules.building import calculate_building_item as building
from core.takeoff.modules.advanced import calculate_advanced_item as advanced

@pytest.mark.parametrize('calc,item,params', [
    (building, 'column', dict(width='1e308', depth=2, height=3)),
    (advanced, 'footing_concrete', dict(length='1e308', width=2, thickness=3)),
    (building, 'door', dict(count='9007199254740993')),
    (advanced, 'steel', dict(length=2, unit_weight=3, count='9007199254740993')),
    (building, 'wall', dict(length=2, height=3, openings='1e-400')),
    (advanced, 'facade', dict(length=2, height=3, openings='1e-400')),
    (advanced, 'excavation', dict(length='1e-200', width='1e-200', depth=2)),
    (building, 'tile', dict(length='1e-12', height='1e-12', waste='1e-310')),
])
def test_invalid_float_conversion_or_arithmetic_is_rejected(calc, item, params):
    with pytest.raises(ValueError):
        calc(item, **params)

@pytest.mark.parametrize('calc,item,params,expected,unit', [
    (building, 'column', dict(width='0.4', depth='0.5', height=3, count=2), 1.2, 'm3'),
    (advanced, 'footing_concrete', dict(length=2, width=3, thickness='0.5', count=2), 6, 'm3'),
    (building, 'door', dict(count=3), 3, 'عدد'),
    (advanced, 'steel', dict(length=2, unit_weight=3, count=4), 24, 'kg'),
    (building, 'wall', dict(length=2, height=3, openings=0), 6, 'm2'),
    (advanced, 'facade', dict(length=2, height=3, openings=6), 0, 'm2'),
    (advanced, 'excavation', dict(length=0, width=3, depth=2), 0, 'm3'),
    (building, 'tile', dict(length=2, height=3, waste=0), 0, 'm2'),
])
def test_explicit_normal_and_true_zero_quantities_survive(calc,item,params,expected,unit):
    result = calc(item, **params)
    assert result.quantity == pytest.approx(expected)
    assert result.unit == unit

@pytest.mark.parametrize('domain,item,params,bad,expected,unit', [
    ('civil', 'curb', dict(length='5.5', count='2'), dict(length='1e308', count='2'), '11', 'm'),
    ('building', 'door', dict(count='3'), dict(count='9007199254740993'), '3', 'عدد'),
    ('advanced', 'footing_concrete', dict(length='2', width='3', thickness='0.5', count='2'),
     dict(length='1e308', width='2', thickness='3', count='2'), '6', 'm3'),
])
def test_real_sqlite_boq_numeric_rejection_duplicate_and_reopen(tmp_path,domain,item,params,bad,expected,unit):
    from copy import deepcopy
    from decimal import Decimal
    from core.platform.application import StructuralProApp
    app = StructuralProApp(tmp_path/'db')
    try:
        app.create_project('نمونه عددی صریح؛ فاقد پذیرش طراحی', 'P')
        before = deepcopy(app.open_project('P'))
        digest = app.store.current_digest('P')
        with pytest.raises(ValueError):
            app.add_takeoff('P', domain, item, source_id='SYNTHETIC:BAD', **bad)
        assert app.open_project('P') == before
        assert app.store.current_digest('P') == digest
        app.add_takeoff('P', domain, item, source_id='SYNTHETIC:EXPLICIT',
                        manual_location_id='PHYSICAL-01', system='L1', **params)
        saved = deepcopy(app.open_project('P'))
        assert len(saved['boq']) == 1
        assert Decimal(str(saved['boq'][0]['quantity'])) == Decimal(expected)
        assert saved['boq'][0]['unit'] == unit
        for source in ('SYNTHETIC:EXPLICIT', 'SYNTHETIC:OTHER'):
            with pytest.raises(ValueError):
                app.add_takeoff('P', domain, item, source_id=source,
                                manual_location_id='PHYSICAL-01', system='L1', **params)
            assert app.open_project('P') == saved
    finally:
        app.store.close()
    app = StructuralProApp(tmp_path/'db')
    try:
        assert app.open_project('P') == saved
        assert app.store.db.execute('pragma integrity_check').fetchone()[0] == 'ok'
        assert app.store.db.execute('pragma foreign_key_check').fetchall() == []
    finally:
        app.store.close()
