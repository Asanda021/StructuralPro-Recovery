"""Project financial ledger with traceable commitments and receivables."""
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class LedgerEntry:
    kind:str; amount:float; reference:str; description:str=""

def summarize(entries:Iterable[LedgerEntry])->dict:
    totals={"receivable":0.0,"commitment":0.0,"payment":0.0,"other":0.0}
    rows=[]
    for e in entries:
        amount=max(0.0,float(e.amount)); kind=e.kind if e.kind in totals else "other"
        totals[kind]+=amount; rows.append({"kind":kind,"amount":amount,"reference":e.reference,"description":e.description})
    totals["net_position"]=totals["receivable"]-totals["commitment"]-totals["payment"]
    return {"entries":rows,"totals":totals}
