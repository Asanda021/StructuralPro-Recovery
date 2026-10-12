"""P331-P340 deterministic production-readiness attestation boundary."""
from __future__ import annotations
import hashlib, json
from dataclasses import dataclass
from typing import Mapping, Sequence
from .provisioning import ProvisioningEvidence, build_provisioning_manifest
from .readiness import run_readiness, Readiness
from .update_release_trust_v1 import validate_release_manifest

@dataclass(frozen=True)
class ReadinessAttestation:
    ready: bool
    checks: tuple[tuple[str,bool], ...]
    fingerprint: str
    errors: tuple[str, ...]

def _fingerprint(payload:Mapping)->str:
    raw=json.dumps(dict(payload),ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()

def attest_production_readiness(
    current_version:str,
    release_manifest:Mapping,
    provisioning:Sequence[ProvisioningEvidence],
    checks:Sequence[tuple[str,object]],
    *,
    channel:str="stable",
    artifact:bytes|None=None,
) -> ReadinessAttestation:
    errors=list(validate_release_manifest(current_version,release_manifest,channel=channel,artifact=artifact))
    prov=build_provisioning_manifest(provisioning)
    errors.extend(f"provisioning: {e}" for e in prov["errors"])
    readiness:Readiness=run_readiness(checks)  # type: ignore[arg-type]
    errors.extend(f"readiness: {c.name}: {c.detail or 'failed'}" for c in readiness.failures)
    check_pairs=tuple((c.name,c.ok) for c in readiness.checks)
    payload={"version":release_manifest.get("version"),"channel":release_manifest.get("channel"),
             "release_ok":not validate_release_manifest(current_version,release_manifest,channel=channel,artifact=artifact),
             "provisioning_ok":bool(prov["valid"]),"checks":check_pairs,"errors":tuple(errors)}
    return ReadinessAttestation(not errors,check_pairs,_fingerprint(payload),tuple(errors))
