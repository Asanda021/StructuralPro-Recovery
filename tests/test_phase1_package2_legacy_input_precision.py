"""Legacy float contracts may reject exact inputs, never silently truncate them."""
from importlib import import_module
import pytest

@pytest.mark.parametrize('module',['civil','building','advanced','mechanical','electrical'])
@pytest.mark.parametrize('value',['9007199254740993','0.12345678901234567890123456789'])
def test_legacy_dimension_keeps_source_precision_or_fails_closed(module,value):
    with pytest.raises(ValueError):import_module('core.takeoff.modules.'+module)._n(value,'length')

@pytest.mark.parametrize('module',['civil','building','advanced','mechanical','electrical'])
def test_normal_explicit_dimensions_and_zero_policy_remain_valid(module):
    fn=import_module('core.takeoff.modules.'+module)._n
    assert fn('1.25','length')==1.25
    assert fn('0','openings')==0
