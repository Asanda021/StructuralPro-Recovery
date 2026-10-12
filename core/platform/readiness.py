"""Deterministic application readiness aggregation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
@dataclass(frozen=True)
class CheckResult:
    name:str; ok:bool; detail:str=""
@dataclass(frozen=True)
class Readiness:
    ready:bool; checks:tuple[CheckResult,...]
    @property
    def failures(self): return tuple(c for c in self.checks if not c.ok)
def run_readiness(checks:Iterable[tuple[str,Callable[[],bool]]])->Readiness:
    results=[]
    for name,fn in checks:
        try: results.append(CheckResult(name,bool(fn())))
        except Exception as exc: results.append(CheckResult(name,False,f"{type(exc).__name__}: {exc}"))
    return Readiness(all(c.ok for c in results),tuple(results))
