"""P31 Commercial Readiness master gate.

Deterministic, offline-first and fail-closed. Validates the client-side
commercial lifecycle without inventing payment, cloud activation or private
key infrastructure.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
from core.licensing.license import LicenseManager
from core.platform.activation_integrity_v1 import (
    ActivationEvidence, EntitlementEvidence, RevocationPolicy, activation_allowed,
)
from core.platform.update_release_trust_v1 import build_release_manifest, release_trust_ready
from core.platform.updates import validate_update
from core.help.content import topics, topic

REQUIRED_SURFACES = (
    "licensing", "activation", "entitlements", "trial_demo", "versioning",
    "updates", "migration", "backup_restore", "documentation_help",
)

@dataclass(frozen=True)
class P31Result:
    valid: bool
    checks: tuple[str, ...]
    errors: tuple[str, ...]

def _check(name, fn):
    try:
        fn()
        return name, None
    except Exception as exc:
        return name, f"{name}:{type(exc).__name__}:{exc}"

def run_p31_gate() -> P31Result:
    checks=[]; errors=[]
    probes={
        "licensing": _licensing,
        "activation": _activation,
        "entitlements": _entitlements,
        "trial_demo": _trial_demo,
        "versioning": _versioning,
        "updates": _updates,
        "migration": _migration,
        "backup_restore": _backup_restore,
        "documentation_help": _documentation_help,
    }
    for name in REQUIRED_SURFACES:
        n,e=_check(name,probes[name])
        checks.append(n)
        if e: errors.append(e)
    return P31Result(not errors and tuple(checks)==REQUIRED_SURFACES,tuple(checks),tuple(errors))

def _licensing():
    secret="p31-test-secret"
    lm=LicenseManager(secret)
    token=lm.issue("demo",9999999999,"device-1")
    assert lm.validate(token,"device-1")["valid"]
    assert not lm.validate(token,"device-2")["valid"]

def _activation():
    fp=hashlib.sha256(b"license-p31").hexdigest()
    ev=ActivationEvidence("LIC-P31",fp,"StructuralPro","P31","0.1.0","accepted","offline",date.today().isoformat())
    ent=EntitlementEvidence("LIC-P31",("takeoff","reports"))
    assert activation_allowed(ev,ent,RevocationPolicy(frozenset(),False))
    assert not activation_allowed(ev,ent,RevocationPolicy(frozenset({"LIC-P31"}),False))

def _entitlements():
    ent=EntitlementEvidence("LIC-P31",("takeoff","reports"))
    ent.validate()
    try:
        EntitlementEvidence("LIC-P31",("takeoff","takeoff")).validate()
    except ValueError:
        return
    raise AssertionError("duplicate entitlement must fail closed")

def _trial_demo():
    # Trial/demo remains an entitlement policy, not an implicit bypass.
    assert "takeoff" in EntitlementEvidence("DEMO",("takeoff",)).features

def _versioning():
    version=Path("VERSION").read_text(encoding="utf-8").strip()
    parts=version.split(".")
    assert len(parts)==3 and all(p.isdigit() for p in parts)

def _updates():
    artifact=b"p31-release"
    manifest=build_release_manifest("0.1.1","stable",artifact,{"phase":"P31"})
    assert release_trust_ready("0.1.0",manifest,channel="stable",artifact=artifact)
    assert validate_update("0.1.1",manifest,channel="stable")

def _migration():
    from core.platform.migrations import MigrationRegistry, MigrationStep
    registry=MigrationRegistry((MigrationStep(1,2,lambda d:{**d,"schema":2}),))
    assert registry.migrate({"schema":1},1,2)["schema"]==2

def _backup_restore():
    from core.platform.backup import create_backup, restore_backup
    source={"project":"P31","items":[1,2]}
    b=create_backup("P31",1,source)
    assert restore_backup(b,expected_project_id="P31")==source

def _documentation_help():
    keys={x.key for x in topics()}
    assert {"start","takeoff","reports","recovery","ai"} <= keys
    assert topic("start").steps
