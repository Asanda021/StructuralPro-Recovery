"""Validated project finance domain: parties, documents, obligations, costs, receipts and payments."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import math
from typing import Any, Iterable

STATUSES={"unpaid","partial","paid"}

def _amount(value: Any, label="amount"):
    value=float(value)
    if not math.isfinite(value) or value<0: raise ValueError(f"{label} must be finite and non-negative")
    return value

def _text(value: Any, label, required=False):
    value=" ".join(str(value or "").strip().split())
    if required and not value: raise ValueError(f"{label} is required")
    return value

@dataclass(frozen=True)
class FinanceParty:
    id:str; name:str; role:str=""

@dataclass(frozen=True)
class FinanceDocument:
    id:str; number:str; kind:str; amount:float; party_id:str=""; due_date:str=""; status:str="unpaid"

@dataclass(frozen=True)
class FinanceEntry:
    id:str; amount:float; date:str=""; reference:str=""; party_id:str=""; document_id:str=""

class FinanceLedger:
    """UI-agnostic validated finance ledger used by desktop/reporting adapters."""
    def __init__(self,*,parties:Iterable[FinanceParty]=(),documents:Iterable[FinanceDocument]=(),
                 obligations:Iterable[FinanceEntry]=(),costs:Iterable[FinanceEntry]=(),
                 receipts:Iterable[FinanceEntry]=(),payments:Iterable[FinanceEntry]=()):
        self.parties=list(parties); self.documents=list(documents); self.obligations=list(obligations)
        self.costs=list(costs); self.receipts=list(receipts); self.payments=list(payments); self.validate()

    @staticmethod
    def _unique(items,label):
        ids=set()
        for x in items:
            if not str(x.id).strip(): raise ValueError(f"{label} id is required")
            if x.id in ids: raise ValueError(f"duplicate {label} id: {x.id}")
            ids.add(x.id)
        return ids

    def validate(self):
        party_ids=self._unique(self.parties,"party"); document_ids=self._unique(self.documents,"document")
        for p in self.parties: _text(p.name,"party name",True)
        for d in self.documents:
            _text(d.number,"document number",True); _text(d.kind,"document kind",True); _amount(d.amount,"document amount")
            if d.party_id and d.party_id not in party_ids: raise ValueError(f"unknown party: {d.party_id}")
            if d.status not in STATUSES: raise ValueError(f"invalid document status: {d.status}")
        for label,items in (("obligation",self.obligations),("cost",self.costs),("receipt",self.receipts),("payment",self.payments)):
            self._unique(items,label)
            for x in items:
                _amount(x.amount,f"{label} amount")
                if x.party_id and x.party_id not in party_ids: raise ValueError(f"unknown party: {x.party_id}")
                if x.document_id and x.document_id not in document_ids: raise ValueError(f"unknown document: {x.document_id}")
        return self

    def add_party(self,party):
        if any(x.id==party.id for x in self.parties): raise ValueError("duplicate party id")
        _text(party.name,"party name",True); self.parties.append(party); return party

    def add_document(self,document):
        old=list(self.documents)
        self.documents.append(document)
        try: self.validate()
        except Exception:
            self.documents=old
            raise
        return document

    def _add(self,target,entry,label):
        if any(x.id==entry.id for x in target): raise ValueError(f"duplicate {label} id")
        target.append(entry)
        try: self.validate()
        except Exception:
            target.pop()
            raise
        return entry
    def add_obligation(self,entry): return self._add(self.obligations,entry,"obligation")
    def add_cost(self,entry): return self._add(self.costs,entry,"cost")
    def add_receipt(self,entry): return self._add(self.receipts,entry,"receipt")
    def add_payment(self,entry): return self._add(self.payments,entry,"payment")

    def reconciliation(self):
        rows=[]
        for d in self.documents:
            paid=sum(x.amount for x in self.payments if x.document_id==d.id)
            outstanding=max(d.amount-paid,0.0)
            derived="paid" if d.amount>0 and outstanding==0 else ("partial" if paid>0 else "unpaid")
            rows.append({**asdict(d),"paid_amount":paid,"outstanding":outstanding,
                         "derived_status":derived,"status_match":d.status==derived})
        return {"rows":rows,"document_count":len(rows),"mismatch_count":sum(not x["status_match"] for x in rows),
                "outstanding":sum(x["outstanding"] for x in rows)}

    def due_control(self,as_of):
        as_of=_text(as_of,"as_of",True); rec={x["id"]:x for x in self.reconciliation()["rows"]}; rows=[]
        for d in self.documents:
            x=rec[d.id]
            if x["outstanding"]<=0: continue
            due=_text(d.due_date,"due_date")
            status="بدون سررسید" if not due else ("معوق" if due<as_of else ("سررسید امروز" if due==as_of else "آتی"))
            rows.append({**x,"due_status":status})
        order={"معوق":0,"سررسید امروز":1,"آتی":2,"بدون سررسید":3}
        rows.sort(key=lambda x:(order[x["due_status"]],x["due_date"],x["id"]))
        return {"as_of":as_of,"rows":rows,"overdue_count":sum(x["due_status"]=="معوق" for x in rows),
                "overdue_amount":sum(x["outstanding"] for x in rows if x["due_status"]=="معوق")}

    def dashboard(self,as_of=""):
        rec=self.reconciliation()
        result={"party_count":len(self.parties),"document_count":len(self.documents),
                "cost":sum(x.amount for x in self.costs),"receipts":sum(x.amount for x in self.receipts),
                "obligations":sum(x.amount for x in self.obligations),"payments":sum(x.amount for x in self.payments),
                "outstanding_documents":rec["outstanding"],"reconciliation_mismatches":rec["mismatch_count"],
                "net_cash":sum(x.amount for x in self.receipts)-sum(x.amount for x in self.payments)}
        if as_of: result["due"]=self.due_control(as_of)
        return result

    def export_dict(self):
        return {k:[asdict(x) for x in getattr(self,k)] for k in
                ("parties","documents","obligations","costs","receipts","payments")}
