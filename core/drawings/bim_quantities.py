"""IFC/BIM quantity extraction with optional local IfcOpenShell support."""
from __future__ import annotations
from typing import Any, Iterable
from pathlib import Path
import math

def _quantity_value(name: str, value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}")
    try:
        number=float(value)
    except (TypeError,ValueError) as exc:
        raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"مقدار کمیت IFC باید متناهی و نامنفی باشد: {name}")
    return number

def classify_objects(objects:Iterable[Any])->dict[str,int]:
    out={}
    for o in objects:
        k=str(getattr(o,"ifc_type",None) or getattr(o,"type",None) or "Unknown")
        out[k]=out.get(k,0)+1
    return out

def extract_quantities(objects:Iterable[Any])->list[dict[str,Any]]:
    rows=[]; seen=set()
    for o in objects:
        gid=str(getattr(o,"global_id","") or "")
        if not gid.strip(): raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        props=dict(getattr(o,"properties",{}) or {}); q={}
        for k in ("Length","Width","Height","Area","Volume","NetVolume","GrossVolume","Count"):
            if k in props:
                q[k]=_quantity_value(k,props[k])
        rows.append({"global_id":gid,"ifc_type":getattr(o,"ifc_type",""),
                     "name":getattr(o,"name",""),"quantities":q})
    return rows

def read_ifc(path:str|Path)->list[dict[str,Any]]:
    try: import ifcopenshell
    except ImportError as exc: raise RuntimeError("Install ifcopenshell for local IFC parsing") from exc
    model=ifcopenshell.open(str(path)); rows=[]; seen=set()
    for obj in model.by_type("IfcProduct"):
        gid=str(getattr(obj,"GlobalId","") or "")
        if not gid.strip(): raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        q={}
        for rel in getattr(obj,"IsDefinedBy",[]) or []:
            definition=getattr(rel,"RelatingPropertyDefinition",None)
            for prop in getattr(definition,"Quantities",[]) or []:
                name=str(getattr(prop,"Name","") or "").strip()
                if not name: raise ValueError("نام کمیت IFC نامشخص است")
                for attr in ("LengthValue","AreaValue","VolumeValue","CountValue"):
                    value=getattr(prop,attr,None)
                    if value is not None:
                        if name in q: raise ValueError(f"نام کمیت IFC تکراری است: {name}")
                        q[name]=_quantity_value(name,value); break
        rows.append({"global_id":gid,"ifc_type":obj.is_a(),"name":getattr(obj,"Name","") or "",
                     "quantities":q})
    return rows

def link_2d_3d(two_d:Iterable[dict[str,Any]],three_d:Iterable[dict[str,Any]])->list[dict[str,Any]]:
    by_id={}; out=[]
    for x in three_d:
        gid=str(x.get("global_id") or "")
        if not gid: raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in by_id: raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        by_id[gid]=x
    for x in two_d:
        m=by_id.get(str(x.get("global_id",""))); out.append({"two_d":x,"three_d":m,"linked":m is not None})
    return out



def compare_volume_qto(path, *, revision, global_id):
    """Diagnostic QTO/geometry comparison; never a payable material quantity.

    IfcOpenShell evaluates actual IfcRelVoidsElement subtraction. Gross and net
    meshes are evaluated separately. This is a floating tessellation diagnostic,
    with a fixed 1e-8 m3 absolute + 1e-8 relative tolerance, not exact geometry or
    an engineering acceptance certificate. Unknown QTO bases stay unverified.
    """
    from decimal import Decimal,localcontext
    from hashlib import sha256
    from core.drawings.bim_adapter import BIMAdapter
    import ifcopenshell
    import ifcopenshell.geom
    import ifcopenshell.util.shape
    p=Path(path);doc=BIMAdapter().read_document(p,revision=revision)
    element=next((x for x in doc['elements'] if x['global_id']==global_id),None)
    if element is None:raise ValueError('عضو IFC یافت نشد')
    model=ifcopenshell.open(str(p));obj=model.by_guid(global_id)
    def volume(gross):
        settings=ifcopenshell.geom.settings()
        # Local SI geometry avoids cancellation from large world origins.
        settings.set('use-world-coords',False)
        settings.set('disable-opening-subtractions',gross)
        shape=ifcopenshell.geom.create_shape(settings,obj)
        value=ifcopenshell.util.shape.get_volume(shape.geometry)
        if not math.isfinite(value) or value<0:raise ValueError('حجم هندسی IFC معتبر نیست')
        return Decimal(str(value))
    gross,net=volume(True),volume(False)
    comparisons=[]
    with localcontext() as context:
        context.prec=80
        if net>gross+Decimal('0.00000001')+abs(gross)*Decimal('0.00000001'):
            raise ValueError('حجم خالص IFC از حجم ناخالص بیشتر است')
        for q in element['quantities']:
            if q['unit']!='m3' or q['basis'] not in ('gross','net'):continue
            observed=gross if q['basis']=='gross' else net
            expected=Decimal(q['value_si']);delta=observed-expected
            bound=Decimal('0.00000001')+abs(expected)*Decimal('0.00000001')
            comparisons.append({'qto_step_id':q['step_id'],'name':q['name'],'basis':q['basis'],
                'qto_m3':str(expected),'geometry_m3':str(observed),'difference_m3':str(delta),
                'tolerance_m3':str(bound),'within_tolerance':abs(delta)<=bound})
    if sha256(p.read_bytes()).hexdigest()!=doc['source_sha256']:
        raise ValueError('منبع IFC حین کنترل هندسه تغییر کرده است')
    return {'source_sha256':doc['source_sha256'],'revision':doc['revision'],'global_id':global_id,
        'opening_ids':sorted(rel.RelatedOpeningElement.GlobalId for rel in getattr(obj,'HasOpenings',())),
        'gross_volume_m3':str(gross),'net_volume_m3':str(net),'comparisons':comparisons,
        'within_tolerance':bool(comparisons) and all(x['within_tolerance'] for x in comparisons),
        'numeric_policy':'IfcOpenShell local SI mesh diagnostic; abs 1e-8 m3 + rel 1e-8',
        'commit_allowed':False,'payable_rows':[],
        'warning':'مقایسه تشخیصی هندسه است؛ تأیید مصالح یا مجوز پرداخت نیست'}
