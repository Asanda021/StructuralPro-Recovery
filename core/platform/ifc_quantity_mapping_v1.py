"""Fail-closed IFC quantity/property mapping assurance."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json


@dataclass(frozen=True)
class IFCQuantityMapping:
    source_property: str
    target_quantity: str
    unit: str


def evaluate_ifc_mapping(
    mappings: list[IFCQuantityMapping],
    required_targets: set[str],
) -> dict[str, object]:
    seen: dict[str, IFCQuantityMapping] = {}
    reasons: list[str] = []
    for item in mappings:
        if not item.source_property or not item.target_quantity or not item.unit:
            reasons.append("invalid_mapping")
            continue
        if item.target_quantity in seen:
            reasons.append(f"duplicate_target:{item.target_quantity}")
        seen[item.target_quantity] = item

    missing = sorted(required_targets - set(seen))
    reasons.extend(f"missing_target:{name}" for name in missing)
    ready = not reasons
    payload = {
        "ready": ready,
        "required_targets": sorted(required_targets),
        "mapped_targets": sorted(seen),
        "missing_targets": missing,
        "reasons": reasons,
    }
    payload["fingerprint"] = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload
