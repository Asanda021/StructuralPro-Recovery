"""External provisioning evidence and release-readiness gate.

This module records evidence for dependencies that cannot be fabricated by the
repository: official price data, DWG converters, GGUF models and code signing.
It deliberately fails closed when required evidence is missing or malformed.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib
import re
from typing import Iterable

_SHA256 = re.compile(r"^[0-9a-f]{64}$", re.I)
_ALLOWED = {"verified", "pending", "blocked"}

@dataclass(frozen=True)
class ProvisioningEvidence:
    component: str
    status: str = "pending"
    version: str = ""
    sha256: str = ""
    source_ref: str = ""
    license_ref: str = ""
    notes: str = ""
    required: bool = True

    def validate(self) -> list[str]:
        errors = []
        name = self.component.strip()
        if not name:
            errors.append("component is required")
        if self.status not in _ALLOWED:
            errors.append("invalid status")
        if self.required and self.status != "verified":
            errors.append("required component is not verified")
        if self.status == "verified":
            if not _SHA256.fullmatch(self.sha256.strip()):
                errors.append("verified component requires a valid sha256")
            if not self.source_ref.strip():
                errors.append("verified component requires source_ref")
            if not self.license_ref.strip():
                errors.append("verified component requires license_ref")
        return errors

def build_provisioning_manifest(items: Iterable[ProvisioningEvidence]) -> dict:
    items = list(items)
    entries = [asdict(x) for x in items]
    errors = []
    seen = set()
    for item in items:
        key = item.component.strip().casefold()
        if key in seen:
            errors.append(f"duplicate component: {item.component}")
        seen.add(key)
        errors.extend(f"{item.component}: {e}" for e in item.validate())
    canonical = repr(entries).encode("utf-8")
    return {
        "components": entries,
        "valid": not errors,
        "errors": errors,
        "sha256": hashlib.sha256(canonical).hexdigest(),
    }

def release_provisioning_ready(items: Iterable[ProvisioningEvidence]) -> bool:
    return build_provisioning_manifest(items)["valid"]
