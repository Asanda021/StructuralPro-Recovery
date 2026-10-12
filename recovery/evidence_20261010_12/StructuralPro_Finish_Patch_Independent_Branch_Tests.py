"""Standalone execution of exact added calculate_assembly branch under GitHub helper contracts.
Not full repository pytest, nor integration/GUI testing.
"""
from pathlib import Path
import math
import pytest

PATCH = Path('/mnt/data/StructuralPro_Manual_Finishing_Assemblies_Validated.patch').read_text()

def added_branch():
    # Exact '+' lines inserted into calculate_assembly in current patch (no copied body).
    part=PATCH.split('diff --git a/core/takeoff/assembly.py b/core/takeoff/assembly.py')[1].split('diff --git a/core/takeoff/assembly_templates.py')[0]
    lines=[]
    for line in part.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
    text='\n'.join(lines)
    assert 'if k in wall_finishes:' in text
    assert 'return AssemblyResult(k, title, tuple(components), tuple(used))' in text
    return text

prefix='''
from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping
@dataclass(frozen=True)
class AssemblyComponent:
    code: str
    title: str
    unit: str
    formula: str
    quantity: float
    source: str = "derived"
    warning: str = ""
    def __post_init__(self):
        value=float(self.quantity)
        if not isfinite(value) or value < 0:
            raise ValueError(f"مقدار جزء {self.code} باید متناهی و غیرمنفی باشد")
@dataclass(frozen=True)
class AssemblyResult:
    code: str
    title: str
    components: tuple[AssemblyComponent, ...]
    inputs_used: tuple[str, ...]
    missing_inputs: tuple[str, ...] = ()
    @property
    def complete(self): return not self.missing_inputs
def _n(p: Mapping[str, Any], name: str, minimum: float=0.0)->float:
    try: value = float(p[name])
    except (KeyError,TypeError,ValueError): raise ValueError(f"{name} must be numeric")
    if not isfinite(value): raise ValueError(f"{name} must be finite")
    if value < minimum: raise ValueError(f"{name} must be >= {minimum}")
    return value
def _count(p: Mapping[str, Any], name: str) -> int:
    if name not in p or p[name] in (None, ""): raise ValueError(f"{name} must be supplied explicitly")
    value=_n(p,name,1)
    if not value.is_integer(): raise ValueError(f"{name} must be an integer")
    return int(value)
def _optional(p: Mapping[str, Any], name: str)->float | None:
    if name not in p or p[name] in (None, ""): return None
    return _n(p,name)
def _waste(q: float, factor:float | None)->float:
    if factor is None:return q
    if not isfinite(factor):raise ValueError("waste_factor must be finite")
    if factor<0:raise ValueError("waste_factor must be >= 0")
    result=q*(1+factor)
    if not isfinite(result):raise ValueError("مقدار نهایی پس از اعمال پرت متناهی نیست")
    return result
def calculate_assembly(code:str, **p:Any)->AssemblyResult:
    k=code.strip().casefold().replace(" ", "_")
'''
# Added lines are indented four spaces and should run after existing branches.
code=prefix + added_branch() + '\n    raise KeyError(f"unsupported assembly: {code}")\n'
ns={}
exec(compile(code,'<exact_patch_branch_with_main_helpers>', 'exec'),ns)
calc=ns['calculate_assembly']
wall=['gypsum_scratch','gypsum_finish','cement_render','wall_tile','wall_paint','waterproofing_wall','facade_finish']
floor=['floor_tile','floor_screed','ceiling_paint','false_ceiling','waterproofing_floor']
all_items=wall+floor+['skirting']

@pytest.mark.parametrize('item',all_items)
@pytest.mark.parametrize('floor_no',range(1,6))
def test_65_items(item,floor_no):
    inp={'count':1,'length':10,'height':3,'openings':2} if item in wall else ({'count':1,'length':6,'width':4,'openings':2} if item in floor else {'count':1,'length':40,'deductions':8})
    val=calc(item,**inp)
    assert val.complete
    assert len(val.components)==1
    assert val.components[0].quantity == (28 if item in wall else 22 if item in floor else 32)
    assert val.components[0].unit == ('m' if item=='skirting' else 'm²')

def test_material_rate_and_waste():
    r=calc('wall_tile',count=1,length=10,height=3,openings=2,layers=2,consumption_per_m2_per_layer=4,consumption_unit='kg',material_spec_ref='SPEC-T01',waste_factor=.1)
    assert [x.quantity for x in r.components]==pytest.approx([28,30.8,224])

def test_missing_explicit_material_unit_rejected():
    with pytest.raises(ValueError,match='واحد مصرف'):
        calc('wall_tile',count=1,length=10,height=3,openings=2,consumption_per_m2_per_layer=4)

def test_missing_layer_rejected():
    with pytest.raises(ValueError,match='تعداد لایه'):
        calc('wall_tile',count=1,length=10,height=3,openings=2,consumption_per_m2_per_layer=4,consumption_unit='kg',material_spec_ref='SPEC-T01')

def test_invalid_openings():
    with pytest.raises(ValueError):calc('floor_tile',count=1,length=6,width=4,openings=25)

def test_invalid_layers():
    with pytest.raises(ValueError,match='عدد صحیح مثبت'):
        calc('wall_paint',count=1,length=10,height=3,openings=0,layers=1.5)

def test_nonfinite():
    with pytest.raises(ValueError):calc('wall_tile',count=1,length=float('inf'),height=3,openings=0)

def test_waste_no_default():
    r=calc('floor_tile',count=1,length=6,width=4,openings=2)
    assert len(r.components)==1

def test_unknown_code():
    with pytest.raises(KeyError):calc('some_other_code')

if __name__=='__main__':
    raise SystemExit(pytest.main(['-q',__file__]))
