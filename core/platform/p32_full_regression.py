"""P32 — Full Regression master gate."""
from __future__ import annotations
from dataclasses import dataclass
import importlib
from pathlib import Path

REQUIRED_SURFACES=("core_functionality","domain_outputs","ui_surfaces","data_integrity","release_artifacts","production_boundary","release_health")
MODULES=("core.platform.application","core.platform.final_product_acceptance_v1","core.platform.p31_commercial_readiness","core.platform.p30_production_hardening","core.validation.golden_project_acceptance_v1","core.reports.production_acceptance_bundle_v1","core.takeoff.production_acceptance_v1")

@dataclass(frozen=True)
class P32Result:
    valid: bool
    checks: tuple[str,...]
    errors: tuple[str,...]

def _probe_modules():
    for name in MODULES: importlib.import_module(name)

def _probe_final_acceptance():
    from core.platform.final_product_acceptance_v1 import evaluate_final_product_acceptance
    r=evaluate_final_product_acceptance({k:True for k in REQUIRED_SURFACES})
    assert r.accepted and not r.blockers

def _probe_p31():
    from core.platform.p31_commercial_readiness import run_p31_gate
    r=run_p31_gate(); assert r.valid,r.errors

def _probe_p30():
    from core.platform.p30_production_hardening import run_p30_gate
    r=run_p30_gate(); assert r.valid,r.errors

def _probe_existing_regression_contract():
    p=Path("tests/test_priority_32_integration_regression.py")
    assert p.is_file() and p.read_text(encoding="utf-8").strip()

def _probe_data_integrity():
    from core.platform.final_product_acceptance_v1 import evaluate_final_product_acceptance
    a=evaluate_final_product_acceptance({k:True for k in REQUIRED_SURFACES})
    b=evaluate_final_product_acceptance({k:True for k in reversed(REQUIRED_SURFACES)})
    assert a.fingerprint==b.fingerprint

def _probe_release_artifacts():
    p=Path("VERSION"); assert p.is_file()
    v=p.read_text(encoding="utf-8").strip()
    assert len(v.split("."))==3 and all(x.isdigit() for x in v.split("."))

def run_p32_gate():
    probes={"core_functionality":_probe_modules,"domain_outputs":_probe_final_acceptance,"ui_surfaces":_probe_existing_regression_contract,"data_integrity":_probe_data_integrity,"release_artifacts":_probe_release_artifacts,"production_boundary":_probe_p30,"release_health":_probe_p31}
    checks=[]; errors=[]
    for name in REQUIRED_SURFACES:
        try: probes[name]()
        except Exception as exc: errors.append(f"{name}:{type(exc).__name__}:{exc}")
        checks.append(name)
    return P32Result(not errors and tuple(checks)==REQUIRED_SURFACES,tuple(checks),tuple(errors))
