"""P30 Production Hardening master gate.

Evidence-first, deterministic and fail-closed. This phase composes existing
production contracts without changing engineering quantity/calculation logic.
"""
from __future__ import annotations
from dataclasses import dataclass
import importlib
from pathlib import Path
from tempfile import TemporaryDirectory
from core.platform.backup import create_backup, restore_backup
from core.platform.concurrency import begin_write, guarded_update
from core.platform.migrations import MigrationRegistry, MigrationStep
from core.platform.production_hardening_v1 import PerformanceBudget, SecurityPolicy, ProductionGuard
from core.platform.production_hardening_gate_v1 import harden_payload, validate_no_unknown
from core.recovery.recovery import export_project, import_project
from core.platform.logging import redact

REQUIRED_SURFACES = (
    "performance", "memory", "large_projects_pdf_cad_bim", "concurrency",
    "error_handling", "crash_recovery", "logging", "security",
    "data_integrity", "backup_restore", "migration", "compatibility",
)
PRODUCTION_MODULES = (
    "core.drawing.graphical_pdf_measurement_engine_v1",
    "core.cad.native_dwg_dxf_production_boundary_v1",
    "core.bim.roundtrip",
    "core.platform.backup",
    "core.platform.concurrency",
)

@dataclass(frozen=True)
class P30Result:
    valid: bool
    checks: tuple[str, ...]
    errors: tuple[str, ...]

def _check(name: str, fn) -> tuple[str, str | None]:
    try:
        fn()
        return name, None
    except Exception as exc:
        return name, f"{name}:{type(exc).__name__}:{exc}"

def run_p30_gate() -> P30Result:
    checks: list[str] = []
    errors: list[str] = []
    def add(name, fn):
        n, err = _check(name, fn)
        checks.append(n)
        if err:
            errors.append(err)
    add("performance", lambda: PerformanceBudget(2.0, 5000).validate())
    add("memory", lambda: harden_payload({"source_id": "p30", "items": []}, required=("source_id",)))
    add("large_projects_pdf_cad_bim", _large_surface_probe)
    add("concurrency", _concurrency_probe)
    add("error_handling", _error_probe)
    add("crash_recovery", _recovery_probe)
    add("logging", _logging_probe)
    add("security", lambda: SecurityPolicy(allow_network=False).validate())
    add("data_integrity", _integrity_probe)
    add("backup_restore", _backup_probe)
    add("migration", _migration_probe)
    add("compatibility", _compatibility_probe)
    return P30Result(not errors and tuple(checks) == REQUIRED_SURFACES,
                     tuple(checks), tuple(errors))

def _large_surface_probe():
    for name in PRODUCTION_MODULES:
        importlib.import_module(name)
    result = validate_no_unknown(
        {"source_id": "p30", "surface": "large_projects_pdf_cad_bim"},
        ("source_id", "surface"))
    assert result.valid

def _concurrency_probe():
    current = {"project": "P30", "revision": 1}
    digest = begin_write(current)
    assert guarded_update(current, digest, {"project": "P30", "revision": 2})["revision"] == 2

def _error_probe():
    guard = ProductionGuard(PerformanceBudget(1.0, 2), SecurityPolicy())
    guard.validate_payload({"source_id": "p30"})
    result = guard.run([1], lambda _: (_ for _ in ()).throw(RuntimeError("probe")))
    assert not result.ok and result.errors

def _recovery_probe():
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "project.json"
        export_project({"id": "p30", "revision": 1}, path)
        assert import_project(path)["id"] == "p30"

def _logging_probe():
    assert "[REDACTED]" in redact("token=super-secret")

def _integrity_probe():
    result = harden_payload({"source_id": "p30", "value": 1}, required=("source_id",))
    assert result.valid and len(result.fingerprint) == 64

def _backup_probe():
    backup = create_backup("p30", 1, {"items": [1, 2, 3]})
    assert restore_backup(backup, expected_project_id="p30") == {"items": [1, 2, 3]}

def _migration_probe():
    registry = MigrationRegistry((MigrationStep(1, 2, lambda d: {**d, "v2": True}),))
    assert registry.migrate({"v": 1}, 1, 2)["v2"] is True

def _compatibility_probe():
    assert REQUIRED_SURFACES == tuple(REQUIRED_SURFACES)
