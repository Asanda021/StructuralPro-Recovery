"""Reject a material part or deduction that disappears in a float aggregate."""
import pytest
from core.takeoff.reviewed_components import cut_length,net_concrete,net_formwork,reviewed_steel
from core.takeoff.engine import TakeoffEngine

def deduction(v):return {'id':'I','volume_m3':v,'source_ref':'SYNTHETIC:JOINT','approved_by':'Reviewer'}
def faces(values):return {'approved_by':'Reviewer','surfaces':[{'id':str(i),'net_area_m2':v,'source_ref':'SYNTHETIC:FACE'} for i,v in enumerate(values)]}
def parts(values):return {'source_ref':'SYNTHETIC:CUT','approved_by':'Reviewer','length_parts_m':[{'kind':'straight' if i==0 else 'hook','length_m':v,'source_ref':'SYNTHETIC:PART'} for i,v in enumerate(values)]}
def steel(values):return {'status':'confirmed','approved_by':'Reviewer','source_ref':'SYNTHETIC:BAR','segments':[{'count':1,'unit_weight_kg_m':1,'unit_weight_source':'SYNTHETIC:CATALOG','cut_length_m':v,'source_ref':'SYNTHETIC:CUT','approved_by':'Reviewer'} for v in values]}

@pytest.mark.parametrize('operation', ['deduction','formwork','cut','steel'])
def test_nonzero_part_cannot_disappear_from_float_aggregate(operation):
    with pytest.raises(ValueError):
        if operation=='deduction':net_concrete(1e16,[deduction(1)])
        elif operation=='formwork':net_formwork(faces([1e16,1]))
        elif operation=='cut':cut_length(parts([1e16,1]))
        else:reviewed_steel(steel([1e16,1]),label='explicit synthetic',engine=TakeoffEngine())

@pytest.mark.parametrize('operation', ['deduction','formwork','cut','steel'])
def test_explicit_small_decimal_aggregate_survives(operation):
    if operation=='deduction':value=net_concrete(3,[deduction('0.25')])[0];assert value==2.75
    elif operation=='formwork':assert net_formwork(faces(['0.1','0.2']))[0]==0.3
    elif operation=='cut':assert cut_length(parts(['0.1','0.2']))[0]==0.3
    else:assert reviewed_steel(steel(['0.1','0.2']),label='synthetic',engine=TakeoffEngine())[0]==0.3
