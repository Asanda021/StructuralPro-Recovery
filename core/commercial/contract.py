"""Contract model and deterministic commercial controls."""
from __future__ import annotations
from dataclasses import dataclass,asdict
from core.commercial.exact_values import number,wire,exact

@dataclass(frozen=True)
class ContractItem:
    code:str; description:str; unit:str; quantity:float; unit_price:float
    @property
    @exact
    def amount(self): return number(self.quantity,"quantity")*number(self.unit_price,"unit_price")

@dataclass
class Contract:
    contract_id:str; title:str; items:list[ContractItem]; advance_paid:float=0.0
    overhead_rate:float=0.0; regional_rate:float=0.0; retention_rate:float=0.0
    tax_rate:float=0.0; insurance_rate:float=0.0
    def validate(self)->list[str]:
        e=[]
        if not self.contract_id.strip(): e.append("missing_contract_id")
        if not self.title.strip(): e.append("missing_title")
        for i,x in enumerate(self.items,1):
            try:number(x.quantity,"quantity");number(x.unit_price,"unit_price")
            except ValueError:e.append(f"item_{i}_negative_value")
            if not x.code.strip(): e.append(f"item_{i}_missing_code")
        for n,r in (("overhead_rate",self.overhead_rate),("regional_rate",self.regional_rate),
                    ("retention_rate",self.retention_rate),("tax_rate",self.tax_rate),
                    ("insurance_rate",self.insurance_rate)):
            try:
                if number(r,n)>1:e.append(f"{n}_out_of_range")
            except ValueError:e.append(f"{n}_out_of_range")
        try:number(self.advance_paid,"advance")
        except ValueError:e.append("negative_advance")
        return e
    @exact
    def total(self): return sum(x.amount for x in self.items)
    @exact
    def commercial_total(self,base=None):
        base=self.total() if base is None else number(base,"base")
        return base*(1+number(self.overhead_rate,"overhead")+number(self.regional_rate,"regional"))
    def to_dict(self): return wire({**asdict(self),"items":[asdict(x) for x in self.items],"total":self.total(),"commercial_total":self.commercial_total()})
