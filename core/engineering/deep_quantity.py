"""Production-depth deterministic quantity calculations (not structural design checks)."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math

@dataclass(frozen=True)
class QuantityLine:
    code:str
    description:str
    quantity:float
    unit:str
    formula:str
    source:str="IR-NBR-09"

def _n(v,name):
    x=float(v)
    if not math.isfinite(x) or x<0: raise ValueError(f"{name} must be finite and non-negative")
    return x

def concrete_volume(length,width,depth,count=1,openings=0):
    gross=_n(length,"length")*_n(width,"width")*_n(depth,"depth")*_n(count,"count")
    cut=_n(openings,"openings")
    return max(0.0,gross-cut)

def rebar_unit_weight(diameter_mm):
    d=_n(diameter_mm,"diameter_mm")
    return d*d/162.0

def rebar_weight(length_m,diameter_mm,count=1,extra_length_m=0):
    return (_n(length_m,"length_m")+_n(extra_length_m,"extra_length_m"))*rebar_unit_weight(diameter_mm)*_n(count,"count")

def bar_cut_plan(cut_lengths_m,stock_length_m=12.0,waste_allowance=0.0):
    stock=_n(stock_length_m,"stock_length_m")
    waste=_n(waste_allowance,"waste_allowance")
    if stock<=0: raise ValueError("stock_length_m must be positive")
    pieces=sorted((_n(x,"cut_length") for x in cut_lengths_m),reverse=True)
    bins=[]
    for piece in pieces:
        need=piece*(1+waste)
        if need>stock+1e-9: raise ValueError("cut length exceeds stock bar")
        placed=False
        for b in bins:
            if b["remaining"]+1e-9>=need:
                b["cuts"].append(piece); b["remaining"]-=need; placed=True; break
        if not placed: bins.append({"remaining":stock-need,"cuts":[piece]})
    used=sum(stock-b["remaining"] for b in bins)
    return {"stock_length_m":stock,"stock_bar_count":len(bins),"used_length_m":used,
            "waste_length_m":len(bins)*stock-used,"cut_lists":[dict(stock_bar=i+1,cuts=b["cuts"],remaining_m=b["remaining"]) for i,b in enumerate(bins)]}

def roof_concrete_volume(area_m2,thickness_m,roof_type="slab"):
    a=_n(area_m2,"area_m2"); t=_n(thickness_m,"thickness_m")
    factors={"solid":1.0,"slab":1.0,"joist_single":0.18,"joist_double":0.23,
             "waffle":0.15,"u_boot":0.18}
    k=str(roof_type).strip().casefold()
    if k not in factors: raise KeyError(f"unsupported roof_type: {roof_type}")
    return a*t*factors[k]

def member_takeoff(member_type, **p):
    k=str(member_type).strip().casefold()
    if k=="concrete":
        return asdict(QuantityLine("CONC","بتن",concrete_volume(p["length"],p["width"],p["depth"],p.get("count",1),p.get("openings",0)),"m3","L×W×D×N−بازشو"))
    if k=="rebar":
        return asdict(QuantityLine("REBAR","میلگرد",rebar_weight(p["length_m"],p["diameter_mm"],p.get("count",1),p.get("extra_length_m",0)),"kg","L×(d²/162)×N"))
    if k=="roof":
        return asdict(QuantityLine("ROOF-CONC","بتن سقف",roof_concrete_volume(p["area_m2"],p["thickness_m"],p.get("roof_type","slab")),"m3","A×t×ضریب نوع سقف"))
    raise KeyError(f"unsupported member_type: {member_type}")
