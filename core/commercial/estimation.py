"""Deterministic estimate, factors and progress primitives."""
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class EstimateLine:
    code:str; description:str; quantity:float; unit_price:float; unit:str=""; factor:float=1.0
    @property
    def amount(self)->float: return max(0.0,self.quantity)*max(0.0,self.unit_price)*max(0.0,self.factor)

def estimate(lines:Iterable[EstimateLine])->dict:
    rows=[{"code":x.code,"description":x.description,"quantity":x.quantity,"unit":x.unit,"unit_price":x.unit_price,"factor":x.factor,"amount":x.amount} for x in lines]
    return {"lines":rows,"subtotal":sum(x["amount"] for x in rows),"currency":"IRR"}

def progress_claim(lines:Iterable[EstimateLine], progress:dict[str,float])->dict:
    rows=[]
    for x in lines:
        pct=min(100.0,max(0.0,float(progress.get(x.code,0))))
        rows.append({"code":x.code,"quantity":x.quantity,"progress_percent":pct,"executed_quantity":x.quantity*pct/100,"executed_amount":x.amount*pct/100})
    return {"lines":rows,"executed_amount":sum(x["executed_amount"] for x in rows)}
