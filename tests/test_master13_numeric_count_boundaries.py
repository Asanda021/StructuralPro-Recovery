"""Fail-closed numeric source-only regression for verified main module snapshots."""
import math
import pytest

from core.takeoff.units import convert, canonical_quantity
from core.takeoff.modules.mechanical import calculate_mechanical_item
from core.takeoff.modules.electrical import calculate_electrical_item


@pytest.mark.parametrize('quantity,source,destination,expected', [
    (1000,'mm','m',1), (10000,'cm2','m2',1), (1000000,'cm3','m3',1),
    (2.5,'ton','kg',2500), (1e308,'ton','ton',1e308), (50,'m','cm',5000),
])
def test_conversions_agree_with_independent_known_metric_ratios(quantity,source,destination,expected):
    assert convert(quantity,source,destination) == pytest.approx(expected)
    result,unit=canonical_quantity(quantity,source,destination)
    assert result == pytest.approx(expected)
    assert unit == destination


@pytest.mark.parametrize('quantity,source,destination', [
    (1e308,'m','mm'), (1e-323,'mm','m'),
    (float('inf'),'m','mm'), (float('nan'),'m','mm'),
    (True,'m','mm'), (False,'m','mm'),
])
def test_overflow_underflow_bool_and_invalid_inputs_fail_closed(quantity,source,destination):
    with pytest.raises(ValueError):
        convert(quantity,source,destination)


@pytest.mark.parametrize('module,item,params',[
    ('mechanical','equipment',{'count':1.5}),
    ('mechanical','valve',{'count':2.5}),
    ('mechanical','pipe',{'count':1.5,'length':5}),
    ('electrical','panel',{'count':1.5}),
    ('electrical','lighting',{'count':.5}),
    ('electrical','cable',{'count':2.5,'length':5}),
])
def test_fractional_item_counts_are_never_invented(module,item,params):
    fn=calculate_mechanical_item if module=='mechanical' else calculate_electrical_item
    with pytest.raises(ValueError,match='عدد صحیح'):
        fn(item,**params)


def test_fractional_length_with_integer_count_remains_valid():
    assert calculate_mechanical_item('pipe',length=12.5,count=2).quantity==25
    assert calculate_electrical_item('cable',length=7.5,count=2).quantity==15
