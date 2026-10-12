"""P39 Iranian Takeoff Engine v2: source-bound pricing, BOQ and execution rules."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
from .data import IranDataRegistry
from .boq import concrete_to_boq

@dataclass(frozen=True)
class ExecutionRule:
    code:str; description:str; factor:float=1.0; unit:str=""
    def __post_init__(self):
        if not self.code.strip() or not self.description.strip() or self.factor < 0:
            raise ValueError("invalid execution rule")

def build_iranian_boq(member_type:str, geometry:dict[str,float], rebar:Iterable[dict[str,Any]]=(), *,
                      waste_factor:float=0.0, rules:Iterable[ExecutionRule]=()):
    if waste_factor < 0 or waste_factor > 1: raise ValueError("waste_factor must be 0..1")
    rows=concrete_to_boq(member_type, geometry, rebar)
    multiplier=1.0+waste_factor
    for rule in rules: multiplier*=rule.factor
    for row in rows:
        if "quantity" in row: row["quantity"]=float(row["quantity"])*multiplier
        row["source"]="iranian-takeoff-engine-v2"; row["waste_factor"]=waste_factor
    return rows

def price_boq(rows, registry:IranDataRegistry, *, year:int, quarter:int, discipline:str):
    out=[]
    for row in rows:
        unit_price=row.get("unit_price")
        if unit_price is None:
            out.append({**row,"pricing_status":"missing_unit_price","amount":None}); continue
        adjusted=registry.apply_adjustment(float(unit_price),year=year,quarter=quarter,discipline=discipline)
        amount=None if adjusted["status"]!="ok" else float(row["quantity"])*adjusted["adjusted_amount"]
        out.append({**row,"amount":amount,"pricing_status":adjusted["status"],
                    "price_source_id":adjusted.get("source_id")})
    return out
