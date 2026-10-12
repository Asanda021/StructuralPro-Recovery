"""P136-P140 AI-assisted quantity/estimate quality gates."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable

@dataclass(frozen=True)
class Evidence:
    source_id: str
    kind: str
    text: str = ""
    page: str | None = None

@dataclass(frozen=True)
class QuantityFact:
    item: str
    quantity: float
    unit: str
    source_id: str

@dataclass(frozen=True)
class EstimateFact:
    item: str
    quantity: float
    unit: str
    unit_price: float | None
    source_id: str

@dataclass(frozen=True)
class AIContext:
    project_id: str
    scope: str
    evidence: tuple[Evidence, ...] = ()
    quantities: tuple[QuantityFact, ...] = ()
    estimates: tuple[EstimateFact, ...] = ()

@dataclass(frozen=True)
class Finding:
    code: str
    severity: str
    message: str
    sources: tuple[str, ...] = ()

def build_context(project_id: str, scope: str, evidence: Iterable[Evidence],
                  quantities: Iterable[QuantityFact] = (),
                  estimates: Iterable[EstimateFact] = ()) -> AIContext:
    if not project_id.strip() or not scope.strip():
        raise ValueError("project_id and scope are required")
    return AIContext(project_id.strip(), scope.strip(), tuple(evidence), tuple(quantities), tuple(estimates))

def run_quality_gate(ctx: AIContext, required_items: Iterable[str] = ()) -> dict:
    source_ids = {e.source_id for e in ctx.evidence}
    findings: list[Finding] = []
    if not source_ids:
        findings.append(Finding("P136-NO-EVIDENCE", "error", "AI review requires at least one source."))
    for q in ctx.quantities:
        if q.source_id not in source_ids:
            findings.append(Finding("P136-UNTRACED-QUANTITY", "error", f"Quantity '{q.item}' has no registered evidence.", (q.source_id,)))
        if q.quantity < 0:
            findings.append(Finding("P136-NEGATIVE-QUANTITY", "error", f"Quantity '{q.item}' cannot be negative.", (q.source_id,)))
    present = {q.item.strip().casefold() for q in ctx.quantities}
    for item in required_items:
        if item.strip().casefold() not in present:
            findings.append(Finding("P137-MISSING-ITEM", "warning", f"Required item '{item}' is missing."))
    grouped: dict[str, list[QuantityFact]] = {}
    for q in ctx.quantities:
        grouped.setdefault(q.item.strip().casefold(), []).append(q)
    for item, facts in grouped.items():
        if len({round(f.quantity, 9) for f in facts}) > 1:
            findings.append(Finding("P138-CROSS-SOURCE-CONFLICT", "warning", f"Conflicting quantities found for '{item}'.",
                                    tuple(sorted({f.source_id for f in facts}))))
    scope = ctx.scope.casefold()
    spec_review = "spec" in scope or "مشخصات" in scope
    spec_text = " ".join(e.text.casefold() for e in ctx.evidence)
    if spec_review and not spec_text.strip():
        findings.append(Finding("P139-NO-SPECIFICATION-TEXT", "warning",
                                "No specification text was supplied for specification review."))
    for e in ctx.estimates:
        if e.quantity < 0:
            findings.append(Finding("P140-NEGATIVE-ESTIMATE", "error", f"Estimate '{e.item}' has a negative quantity.", (e.source_id,)))
        if e.unit_price is None:
            findings.append(Finding("P140-UNPRICED-ESTIMATE", "error", f"Estimate '{e.item}' has no unit price.", (e.source_id,)))
        elif e.unit_price < 0:
            findings.append(Finding("P140-NEGATIVE-PRICE", "error", f"Estimate '{e.item}' has a negative unit price.", (e.source_id,)))
    errors = sum(f.severity == "error" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    return {
        "project_id": ctx.project_id,
        "scope": ctx.scope,
        "status": "fail" if errors else ("review" if warnings else "pass"),
        "errors": errors,
        "warnings": warnings,
        "findings": [
            {"code": f.code, "severity": f.severity, "message": f.message, "sources": list(f.sources)}
            for f in findings
        ],
    }

def deterministic_digest(ctx: AIContext) -> str:
    payload = {"project_id": ctx.project_id, "scope": ctx.scope,
               "evidence": [e.__dict__ for e in ctx.evidence],
               "quantities": [q.__dict__ for q in ctx.quantities],
               "estimates": [e.__dict__ for e in ctx.estimates]}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()
