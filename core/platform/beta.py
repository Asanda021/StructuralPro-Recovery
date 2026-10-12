"""Deterministic beta-release readiness contract."""
from __future__ import annotations
from dataclasses import dataclass
@dataclass(frozen=True)
class BetaGate:
    version_valid: bool
    golden_ready: bool
    docs_ready: bool
    packaging_ready: bool
    blocking_issues: tuple[str, ...] = ()
    @property
    def ready(self)->bool:
        return all((self.version_valid,self.golden_ready,self.docs_ready,self.packaging_ready)) and not self.blocking_issues
def beta_gate(*,version_valid:bool,golden_ready:bool,docs_ready:bool,packaging_ready:bool,blocking_issues=()):
    return BetaGate(version_valid,golden_ready,docs_ready,packaging_ready,tuple(str(x) for x in blocking_issues))
def beta_label(version:str)->str:
    version=version.strip()
    if not version or version.startswith("v"): raise ValueError("beta version must be a canonical MAJOR.MINOR.PATCH value")
    parts=version.split(".")
    if len(parts)!=3 or any(not p.isdigit() for p in parts): raise ValueError("beta version must use MAJOR.MINOR.PATCH")
    return f"StructuralPro {version} Beta"
