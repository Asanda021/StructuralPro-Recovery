"""Direct regression for civil/site arithmetic; source-backed module tests.

Fail-closed for arithmetic overflow and both input/derived underflow.
Normal explicit work and real zero-value routes must remain unchanged.
"""
import pytest
from core.takeoff.modules.civil import calculate_civil_item as calc

@pytest.mark.parametrize('operation,parameters',[
 ('excavation',{'length':'1e308','width':'2','depth':'3'}),
 ('paving',{'length':'1e308','width':'2','thickness':'0.5'}),
 ('asphalt',{'length':'1e308','width':'2','thickness':'2'}),
 ('curb',{'length':'1e308','count':'2'}),
 ('fence_wall',{'length':'1e308','height':'2'}),
])
def test_derived_overflow_must_fail_closed(operation,parameters):
    with pytest.raises(ValueError,match='finite'):
        calc(operation,**parameters)

@pytest.mark.parametrize('operation,parameters',[
 ('drainage',{'length':'1e-400'}),
 ('curb',{'length':'1e-400','count':1}),
])
def test_input_underflow_must_fail_closed(operation,parameters):
    with pytest.raises(ValueError,match='underflow'):
        calc(operation,**parameters)

@pytest.mark.parametrize('operation,parameters',[
 ('excavation',{'length':'1e-200','width':'1e-200','depth':'2'}),
 ('fence_wall',{'length':'1e-200','height':'1e-200'}),
])
def test_derived_underflow_must_fail_closed(operation,parameters):
    with pytest.raises(ValueError,match='underflow'):
        calc(operation,**parameters)

@pytest.mark.parametrize('count',['1.5','9007199254740993'])
def test_non_integral_or_rounded_count_rejected(count):
    with pytest.raises(ValueError,match='integer'):
        calc('curb',length='5',count=count)

@pytest.mark.parametrize('operation,params,expected,unit',[
 ('excavation',{'length':3,'width':2,'depth':1.5},9,'m3'),
 ('backfill',{'excavation':'9','deductions':'9'},0,'m3'),
 ('paving',{'length':3,'width':2,'thickness':0.1},0.6,'m3'),
 ('asphalt',{'length':2,'width':2,'thickness':0.05},0.2,'m3'),
 ('curb',{'length':5.5,'count':2},11,'m'),
 ('drainage',{'length':0},0,'m'),
 ('fence_wall',{'length':3,'height':2},6,'m2'),
])
def test_normal_operations_unchanged(operation,params,expected,unit):
    result=calc(operation,**params)
    assert result.quantity == pytest.approx(expected) and result.unit==unit
