"""P176-P185 deterministic estimate/cost control layer."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from typing import Sequence

@dataclass(frozen=True)
class EstimateControl:
    estimate_id:str; boq_id:str; amount:float; currency:str; status:str; flags:tuple[str,...]
    def validate(self):
        if not self.estimate_id or not self.boq_id or not self.currency: raise ValueError("estimate identity is required")
        if self.amount < 0: raise ValueError("amount cannot be negative")
        if self.status not in {"accepted","review","rejected"}: raise ValueError("invalid control status")
        return self

class EstimateCostControls:
    @staticmethod
    def _fp(*parts): return "ctl-"+sha256("|".join(str(x) for x in parts).encode()).hexdigest()[:16]

    def controls(self, estimates:Sequence[object], *, max_amount=None, required_currency=None):
        out=[]
        for e in estimates:
            flags=[]
            if not getattr(e,"source_ids",()): flags.append("missing_source")
            if getattr(e,"status","rejected")!="accepted": flags.append("upstream_review")
            if required_currency and getattr(e,"currency","")!=required_currency: flags.append("currency_mismatch")
            amount=float(getattr(e,"amount",0))
            if max_amount is not None and amount>max_amount: flags.append("amount_threshold")
            status="rejected" if "missing_source" in flags else "review" if flags else "accepted"
            out.append(EstimateControl(str(e.estimate_id),str(e.boq_id),amount,str(e.currency),status,tuple(sorted(set(flags)))).validate())
        return tuple(sorted(out,key=lambda x:x.estimate_id))

    @staticmethod
    def totals(estimates:Sequence[object]):
        totals={}
        for e in estimates:
            if getattr(e,"status","rejected")=="accepted":
                c=str(e.currency); totals[c]=totals.get(c,0.0)+float(e.amount)
        return dict(sorted(totals.items()))

    @staticmethod
    def unresolved(controls): return tuple(x for x in controls if x.status!="accepted")

    @staticmethod
    def fingerprints(controls):
        return tuple(sorted(EstimateCostControls._fp(x.estimate_id,x.boq_id,x.amount,x.currency,x.status,*x.flags) for x in controls))

    @staticmethod
    def duplicate_boqs(estimates):
        seen={}; dup=set()
        for e in estimates:
            k=str(e.boq_id)
            if k in seen: dup.add(k)
            seen[k]=1
        return tuple(sorted(dup))
