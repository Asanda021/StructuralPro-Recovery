"""Fail-closed commercial activation evidence boundary for P271-P280.

This module extends the existing offline license primitives with deterministic
activation evidence. It does not provision payment, issuer, key-management,
or network activation services.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
from typing import Iterable


VALID_RESULTS = frozenset({"accepted", "rejected"})
VALID_CHANNELS = frozenset({"offline", "provisioned"})


@dataclass(frozen=True)
class ActivationEvidence:
    license_id: str
    license_fingerprint: str
    product: str
    issuer: str
    application_version: str
    result: str
    channel: str
    checked_on: str

    def validate(self) -> "ActivationEvidence":
        if not self.license_id.strip() or not self.license_fingerprint.strip():
            raise ValueError("activation identity is incomplete")
        if not self.product.strip() or not self.issuer.strip():
            raise ValueError("activation issuer/product is incomplete")
        if len(self.license_fingerprint) != 64:
            raise ValueError("invalid license fingerprint")
        if not self.application_version.strip():
            raise ValueError("application version is incomplete")
        if self.result not in VALID_RESULTS:
            raise ValueError("invalid activation result")
        if self.channel not in VALID_CHANNELS:
            raise ValueError("invalid activation channel")
        try:
            date.fromisoformat(self.checked_on)
        except ValueError:
            raise ValueError("invalid activation date")
        return self


@dataclass(frozen=True)
class EntitlementEvidence:
    license_id: str
    features: tuple[str, ...]
    unique: bool = True

    def validate(self) -> "EntitlementEvidence":
        if not self.license_id.strip():
            raise ValueError("license id is incomplete")
        if not self.unique or len(set(self.features)) != len(self.features):
            raise ValueError("duplicate entitlements are not accepted")
        if any(not feature.strip() for feature in self.features):
            raise ValueError("empty entitlement is not accepted")
        return self


@dataclass(frozen=True)
class RevocationPolicy:
    license_ids: frozenset[str]
    provisioned: bool

    def validate(self) -> "RevocationPolicy":
        if any(not item.strip() for item in self.license_ids):
            raise ValueError("revocation policy contains an empty license id")
        if not isinstance(self.provisioned, bool):
            raise ValueError("invalid revocation policy state")
        return self

    def is_revoked(self, license_id: str) -> bool:
        self.validate()
        return license_id in self.license_ids


def activation_allowed(
    evidence: ActivationEvidence,
    entitlements: EntitlementEvidence,
    policy: RevocationPolicy,
) -> bool:
    evidence.validate()
    entitlements.validate()
    policy.validate()
    if evidence.license_id != entitlements.license_id:
        return False
    if policy.is_revoked(evidence.license_id):
        return False
    return evidence.result == "accepted"


def activation_fingerprint(*records: object) -> str:
    payload = []
    for record in records:
        if hasattr(record, "validate"):
            record.validate()
        if hasattr(record, "__dict__"):
            payload.append(record.__dict__)
        else:
            payload.append(record)
    return hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
