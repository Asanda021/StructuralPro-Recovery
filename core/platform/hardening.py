"""Production hardening acceptance checks for local release surfaces."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from core.platform.release import load_version
from core.platform.release_security import find_embedded_secret_candidates
@dataclass(frozen=True)
class HardeningResult:
    version_valid: bool
    packaging_present: bool
    secret_scan_clean: bool
    issues: tuple[str,...]=()
    @property
    def ready(self)->bool: return all((self.version_valid,self.packaging_present,self.secret_scan_clean)) and not self.issues
def run_hardening(root:Path|None=None)->HardeningResult:
    root=Path(root or Path(__file__).resolve().parents[2])
    issues=[]
    try: version_valid=bool(load_version())
    except Exception as exc: version_valid=False; issues.append(f"version: {exc}")
    packaging_present=all((root/"packaging"/name).exists() for name in ("build_windows.ps1","installer.iss","structuralpro.spec"))
    if not packaging_present: issues.append("packaging surface incomplete")
    findings=find_embedded_secret_candidates()
    secret_scan_clean=not findings
    if findings: issues.append("embedded-secret candidates: "+", ".join(findings))
    return HardeningResult(version_valid,packaging_present,secret_scan_clean,tuple(issues))
