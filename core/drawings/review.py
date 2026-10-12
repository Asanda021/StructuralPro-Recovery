"""Human review and audit primitives for drawing takeoff candidates.

Phase 1 safety boundary:
- review-required candidates need an explicit True decision;
- safe candidates may be accepted by default, but an explicit False rejects them;
- every decision keeps source/provenance and can be serialized as an audit trail;
- no review operation changes or infers quantity.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class ReviewDecision:
    candidate_index: int
    source: str
    decision: str
    reviewer: str
    reviewed_at: str
    quantity: float
    unit: str
    sheet: str = ""
    page: int | None = None
    revision: str = ""
    confidence: float | None = None
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _timestamp(value: str | None) -> str:
    if value:
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def _provenance(row: Mapping[str, Any], index: int) -> dict[str, Any]:
    source = str(row.get("source") or f"drawing:{index}").strip()
    return {
        "source": source,
        "sheet": str(row.get("sheet") or row.get("sheet_id") or "").strip(),
        "page": row.get("page"),
        "revision": str(row.get("revision") or "").strip(),
        "handle": row.get("handle"),
        "entity_type": row.get("entity_type"),
        "layer": row.get("layer"),
        "metric": row.get("metric"),
        "element_type": row.get("element_type"),
    }


def review_candidates(
    candidates: Iterable[Mapping[str, Any]],
    confirmations: Mapping[int, bool] | None = None,
    *,
    reviewer: str = "local-user",
    reviewed_at: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply explicit human decisions and return accepted rows + audit events.

    Review-required candidates are accepted only with an explicit True.
    Safe candidates remain accepted unless explicitly rejected with False.
    """
    confirmations = confirmations or {}
    accepted: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    timestamp = _timestamp(reviewed_at)

    for index, raw in enumerate(candidates, 1):
        row = dict(raw)
        needs_confirmation = bool(row.get("needs_confirmation", False))
        explicit = index in confirmations
        decision = confirmations.get(index)

        if needs_confirmation:
            accepted_flag = decision is True
            decision_name = "approved" if accepted_flag else "rejected_pending_confirmation"
        else:
            accepted_flag = True if not explicit else decision is True
            decision_name = "approved" if accepted_flag else "rejected"

        provenance = _provenance(row, index)
        quantity = float(row.get("quantity", 0) or 0)
        unit = str(row.get("unit") or "")
        event = ReviewDecision(
            candidate_index=index,
            source=provenance["source"],
            decision=decision_name,
            reviewer=str(reviewer or "local-user"),
            reviewed_at=timestamp,
            quantity=quantity,
            unit=unit,
            sheet=provenance["sheet"],
            page=provenance["page"],
            revision=provenance["revision"],
            confidence=row.get("confidence"),
            reason=(
                "explicit confirmation required"
                if needs_confirmation and not accepted_flag
                else "explicit rejection"
                if explicit and decision is False
                else "accepted"
            ),
        ).as_dict()
        audit.append(event)

        if accepted_flag:
            row["confirmation_status"] = "approved"
            row["confirmed_by"] = str(reviewer or "local-user")
            row["confirmed_at"] = timestamp
            row["provenance"] = provenance
            accepted.append(row)

    return accepted, audit
