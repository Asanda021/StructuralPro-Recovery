"""Deterministic, auditable technical-office/contract records.

This module records commercial/administrative quantities and payments; it does
not perform structural design or infer missing contract values.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import math

def _text(v,n):
    s=str(v or "").strip()
    if not s: raise ValueError(f"{n} is required")
    return s

def _num(v,n,minimum=0.0):
    try: x=float(v)
    except (TypeError,ValueError) as e: raise ValueError(f"{n} must be numeric") from e
    if not math.isfinite(x) or x<minimum: raise ValueError(f"{n} must be finite and >= {minimum}")
    return x

@dataclass(frozen=True)
class MeasurementRecord:
    id:str; item_code:str; description:str; quantity:float; unit:str
    date:str=""; source_id:str=""; location:str=""; notes:str=""
    def __post_init__(self):
        _text(self.id,"id"); _text(self.item_code,"item_code"); _text(self.description,"description"); _text(self.unit,"unit"); _num(self.quantity,"quantity")

@dataclass(frozen=True)
class MeetingMinute:
    id:str; date:str; subject:str; attendees:tuple[str,...]=(); decisions:tuple[str,...]=(); actions:tuple[str,...]=(); attachments:tuple[str,...]=()
    def __post_init__(self): _text(self.id,"id"); _text(self.date,"date"); _text(self.subject,"subject")

@dataclass(frozen=True)
class ProgressStatement:
    id:str; period:str; rows:tuple[dict[str,Any],...]; retention_rate:float=0.0
    def __post_init__(self):
        _text(self.id,"id"); _text(self.period,"period"); _num(self.retention_rate,"retention_rate");
        if self.retention_rate>100: raise ValueError("retention_rate must be <= 100")

@dataclass(frozen=True)
class AdjustmentRecord:
    id:str; base_amount:float; index:float; reference_index:float
    def __post_init__(self):
        _text(self.id,"id"); _num(self.base_amount,"base_amount"); _num(self.index,"index"); _num(self.reference_index,"reference_index")
        if self.reference_index<=0: raise ValueError("reference_index must be > 0")
    @property
    def amount(self): return self.base_amount*(self.index/self.reference_index-1.0)

@dataclass(frozen=True)
class Deduction:
    id:str; description:str; amount:float; category:str="other"
    def __post_init__(self): _text(self.id,"id"); _text(self.description,"description"); _num(self.amount,"amount")

@dataclass(frozen=True)
class AdvancePayment:
    id:str; amount:float; recovered_amount:float=0.0
    def __post_init__(self): _text(self.id,"id"); _num(self.amount,"amount"); _num(self.recovered_amount,"recovered_amount")
    @property
    def outstanding(self): return max(0.0,self.amount-self.recovered_amount)

@dataclass(frozen=True)
class SiteMaterial:
    id:str; item_code:str; description:str; received_quantity:float; consumed_quantity:float=0.0; unit:str=""
    def __post_init__(self):
        _text(self.id,"id"); _text(self.item_code,"item_code"); _text(self.description,"description")
        _num(self.received_quantity,"received_quantity"); _num(self.consumed_quantity,"consumed_quantity")
        if self.consumed_quantity > self.received_quantity:
            raise ValueError("consumed_quantity cannot exceed received_quantity")
    @property
    def balance(self): return self.received_quantity-self.consumed_quantity
    def __post_init_post_parse(self): pass

@dataclass(frozen=True)
class QuantityChange:
    id:str; item_code:str; original_quantity:float; revised_quantity:float; reason:str
    def __post_init__(self):
        _text(self.id,"id"); _text(self.item_code,"item_code"); _text(self.reason,"reason"); _num(self.original_quantity,"original_quantity"); _num(self.revised_quantity,"revised_quantity")
    @property
    def delta(self): return self.revised_quantity-self.original_quantity

@dataclass(frozen=True)
class WorkOrder:
    id:str; title:str; date:str; description:str; amount:float=0.0
    def __post_init__(self): _text(self.id,"id"); _text(self.title,"title"); _text(self.date,"date"); _text(self.description,"description"); _num(self.amount,"amount")

@dataclass(frozen=True)
class Variation:
    id:str; title:str; amount:float; reason:str; status:str="proposed"
    def __post_init__(self): _text(self.id,"id"); _text(self.title,"title"); _text(self.reason,"reason"); _num(self.amount,"amount")

@dataclass(frozen=True)
class Claim:
    id:str; title:str; amount:float; basis:str; status:str="submitted"
    def __post_init__(self): _text(self.id,"id"); _text(self.title,"title"); _text(self.basis,"basis"); _num(self.amount,"amount")

@dataclass(frozen=True)
class PaymentCertificate:
    id:str; gross_amount:float; deductions:tuple[Deduction,...]=(); advance_recovery:float=0.0; adjustment:float=0.0; retention_rate:float=0.0
    def __post_init__(self):
        _text(self.id,"id"); _num(self.gross_amount,"gross_amount"); _num(self.advance_recovery,"advance_recovery"); _num(self.adjustment,"adjustment"); _num(self.retention_rate,"retention_rate")
        if self.retention_rate>100: raise ValueError("retention_rate must be <= 100")
    @property
    def retention(self): return (self.gross_amount+self.adjustment)*self.retention_rate/100
    @property
    def net_amount(self): return max(0.0,self.gross_amount+self.adjustment-self.retention-self.advance_recovery-sum(d.amount for d in self.deductions))

class TechnicalOfficeEngine:
    """Stateless calculators/serializers for technical-office workflows."""
    @staticmethod
    def progress_amount(rows, *, previous=None):
        previous=previous or {}
        total=0.0
        details=[]
        for row in rows:
            code=_text(row.get("item_code"),"item_code")
            q=_num(row.get("quantity",0),"quantity")
            price=_num(row.get("unit_price",0),"unit_price")
            prev=_num(previous.get(code,0),"previous quantity")
            current=max(0.0,q-prev)
            amount=current*price; total+=amount
            details.append({"item_code":code,"current_quantity":q,"previous_quantity":prev,"period_quantity":current,"amount":amount})
        return {"total":total,"rows":details}
    @staticmethod
    def payment_certificate(gross_amount, deductions=(), advance_recovery=0, adjustment=0, retention_rate=0):
        cert=PaymentCertificate("generated",_num(gross_amount,"gross_amount"),tuple(deductions),_num(advance_recovery,"advance_recovery"),_num(adjustment,"adjustment"),_num(retention_rate,"retention_rate"))
        return {"gross_amount":cert.gross_amount,"adjustment":cert.adjustment,"retention":cert.retention,"deductions":sum(d.amount for d in cert.deductions),"advance_recovery":cert.advance_recovery,"net_amount":cert.net_amount}
    @staticmethod
    def serialize(record): return asdict(record)
