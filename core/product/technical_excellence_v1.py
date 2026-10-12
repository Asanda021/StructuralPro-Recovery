"""P65 — cross-domain technical excellence gate.

This module scores only supplied evidence. Missing or fabricated evidence never passes.
It is deliberately infrastructure-agnostic: it does not claim a deployed cloud,
signed installer, official price-book corpus, or real-project accuracy without evidence.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json

DOMAINS = (
    "full_building_takeoff", "iran_rules", "pricebook", "mapping",
    "benchmark", "ai_review", "reports", "windows", "cloud", "ux",
)

@dataclass(frozen=True)
class Evidence:
    domain: str
    passed: bool
    evidence_id: str
    verified: bool = True
    blocking: bool = True

def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)

def evidence_fingerprint(items: list[Evidence]) -> str:
    payload = [
        {"domain": x.domain, "passed": x.passed, "evidence_id": x.evidence_id,
         "verified": x.verified, "blocking": x.blocking}
        for x in sorted(items, key=lambda e: (e.domain, e.evidence_id))
    ]
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()

def technical_gate(items: list[Evidence]) -> dict:
    if not items:
        raise ValueError("evidence is required")
    by_domain = {}
    for item in items:
        if item.domain not in DOMAINS:
            raise ValueError("unsupported domain")
        if not item.evidence_id.strip():
            raise ValueError("evidence id is required")
        if item.domain in by_domain:
            raise ValueError("duplicate domain evidence")
        by_domain[item.domain] = item

    missing = [d for d in DOMAINS if d not in by_domain]
    failed = [d for d, e in by_domain.items() if not (e.passed and e.verified)]
    blocking_failures = [
        d for d, e in by_domain.items() if e.blocking and not (e.passed and e.verified)
    ]
    covered = len(by_domain) / len(DOMAINS)
    passed = sum(bool(e.passed and e.verified) for e in by_domain.values())
    raw = 100.0 * passed / len(DOMAINS)
    score = round(raw * covered, 2)
    return {
        "domains": len(DOMAINS),
        "covered": len(by_domain),
        "coverage": round(covered, 4),
        "passed": passed,
        "missing": missing,
        "failed": sorted(failed),
        "blocking_failures": sorted(blocking_failures),
        "score": score,
        "near_100": score >= 98.0 and not missing and not blocking_failures,
        "fingerprint": evidence_fingerprint(items),
    }
