"""Project financial ledger with deterministic cumulative balance."""
from __future__ import annotations
from dataclasses import dataclass,asdict
@dataclass(frozen=True)
class LedgerEntry:
    date:str; kind:str; description:str; amount:float
class ProjectLedger:
    def __init__(self,entries=()): self.entries=list(entries)
    def add(self,entry): 
        if float(entry.amount)<0: raise ValueError("amount must be non-negative")
        self.entries.append(entry)
    def summary(self):
        by_kind={}
        for e in self.entries: by_kind[e.kind]=by_kind.get(e.kind,0.0)+float(e.amount)
        return {"entry_count":len(self.entries),"by_kind":by_kind,"total":sum(by_kind.values())}
    def to_dict(self): return [asdict(e) for e in self.entries]
