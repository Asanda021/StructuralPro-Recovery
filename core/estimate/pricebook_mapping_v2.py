from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MappingResult:
    takeoff_id: str
    item_code: str | None
    confidence: float
    method: str
    review_required: bool


def _norm(value: str) -> str:
    return re.sub(r"[^\w\u0600-\u06ff]+", " ", value.lower()).strip()


def map_item(takeoff_id: str, description: str, unit: str, candidates: list[dict]) -> MappingResult:
    exact = [c for c in candidates if c.get("description") == description and c.get("unit") == unit]
    if exact:
        return MappingResult(takeoff_id, exact[0]["item_code"], 1.0, "exact-description-unit", False)
    target = set(_norm(description).split())
    best = None
    best_score = 0.0
    for c in candidates:
        if c.get("unit") != unit:
            continue
        tokens = set(_norm(c.get("description", "")).split())
        score = len(target & tokens) / max(1, len(target | tokens))
        if score > best_score:
            best, best_score = c, score
    if best is None or best_score < 0.60:
        return MappingResult(takeoff_id, None, best_score, "unresolved", True)
    return MappingResult(takeoff_id, best["item_code"], round(best_score, 6), "token-similarity", best_score < 0.90)


def mapping_fingerprint(results: list[MappingResult]) -> str:
    canonical = "\n".join(
        f"{r.takeoff_id}|{r.item_code}|{r.confidence:.6f}|{r.method}|{r.review_required}"
        for r in sorted(results, key=lambda x: x.takeoff_id)
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def map_items(items: list[dict], candidates: list[dict], require_exact=False) -> list[MappingResult]:
    results=[]
    for item in items:
        result=map_item(str(item["takeoff_id"]), str(item["description"]), str(item["unit"]), candidates)
        if require_exact and (result.method != "exact-description-unit" or result.review_required):
            result=MappingResult(result.takeoff_id, None, result.confidence, "review-required", True)
        results.append(result)
    return results


def mapping_gate(results: list[MappingResult]) -> dict:
    if not results:
        raise ValueError("no mapping results")
    unresolved=[r.takeoff_id for r in results if r.item_code is None]
    review=[r.takeoff_id for r in results if r.review_required]
    exact=sum(r.method=="exact-description-unit" and not r.review_required for r in results)
    return {
        "total": len(results),
        "resolved": len(results)-len(unresolved),
        "unresolved": unresolved,
        "review_required": review,
        "exact_count": exact,
        "exact_ratio": exact/len(results),
        "green": not unresolved and not review,
        "fingerprint": mapping_fingerprint(results),
    }
