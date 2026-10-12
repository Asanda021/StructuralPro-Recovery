"""Reusable construction assemblies for takeoff -> estimate.

Assemblies deliberately stay deterministic: quantity comes from takeoff and the
assembly expands it into material/labour/waste components.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable

@dataclass(frozen=True)
class AssemblyComponent:
    code: str
    description: str
    unit: str
    factor: float
    unit_price: float = 0.0
    category: str = "material"
    def amount(self,base): return float(base)*self.factor
    def cost(self,base): return self.amount(base)*self.unit_price

@dataclass
class Assembly:
    code: str
    name: str
    base_unit: str
    components: list[AssemblyComponent] = field(default_factory=list)
    formula: str = "base quantity"
    def expand(self,quantity):
        q=float(quantity)
        if q<0: raise ValueError("مقدار پایه نمی‌تواند منفی باشد")
        return [{"code":c.code,"description":c.description,"unit":c.unit,
                 "quantity":c.amount(q),"unit_price":c.unit_price,
                 "cost":c.cost(q),"category":c.category} for c in self.components]

class AssemblyLibrary:
    def __init__(self,assemblies=None):
        self._items={a.code:a for a in (assemblies or self.defaults())}
    @staticmethod
    def defaults():
        return [
            Assembly("CON-WALL-20","دیوار بتنی ۲۰ سانتی","m2",[
                AssemblyComponent("CON","بتن","m3",0.20),
                AssemblyComponent("FORM","قالب","m2",2.0),
                AssemblyComponent("LAB-CON","دستمزد اجرای بتن","m2",1.0,category="labor")]),
            Assembly("SLAB-CON","دال بتنی","m2",[
                AssemblyComponent("CON","بتن دال","m3",0.15),
                AssemblyComponent("REBAR","آرماتور","kg",12.0),
                AssemblyComponent("LAB-CON","دستمزد بتن‌ریزی","m2",1.0,category="labor")]),
            Assembly("COL-CON","ستون بتنی","m3",[
                AssemblyComponent("CON","بتن ستون","m3",1.0),
                AssemblyComponent("REBAR","آرماتور","kg",110.0),
                AssemblyComponent("FORM","قالب ستون","m2",6.0)]),
            Assembly("FOOT-CON","پی بتنی","m3",[
                AssemblyComponent("CON","بتن پی","m3",1.0),
                AssemblyComponent("REBAR","آرماتور","kg",90.0),
                AssemblyComponent("FORM","قالب پی","m2",1.0)]),
        ]
    def get(self,code):
        if code not in self._items: raise KeyError(f"Assembly not found: {code}")
        return self._items[code]
    def search(self,text=""):
        q=(text or "").strip().casefold()
        return [a for a in self._items.values() if not q or q in a.code.casefold() or q in a.name.casefold()]
    def expand(self,code,quantity): return self.get(code).expand(quantity)

