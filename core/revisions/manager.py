"""Project revision manager with version snapshots and deterministic comparisons."""
from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
from core.revisions.compare import compare_rows, summary

@dataclass(frozen=True)
class Revision:
    version:int
    label:str
    rows:list[dict]

class RevisionManager:
    def __init__(self): self._revisions:list[Revision]=[]
    def add(self, rows, label="")->Revision:
        if rows is None: raise ValueError("rows are required")
        snap=deepcopy(list(rows))
        rev=Revision(len(self._revisions)+1,label or f"نسخه {len(self._revisions)+1}",snap)
        self._revisions.append(rev); return rev
    def list(self): return list(self._revisions)
    def compare(self, old_version:int, new_version:int):
        old=self._revisions[old_version-1].rows; new=self._revisions[new_version-1].rows
        changes=compare_rows(old,new)
        return {"changes":changes,"summary":summary(changes)}
    def restore(self, version:int)->Revision:
        try: rev=self._revisions[version-1]
        except (IndexError,TypeError) as exc: raise ValueError(f"unknown revision: {version}") from exc
        return Revision(rev.version,rev.label,deepcopy(rev.rows))
    def latest(self): return self._revisions[-1] if self._revisions else None
