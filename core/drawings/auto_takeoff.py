"""Phase 2 Auto Takeoff orchestration.

Deterministic candidate generation for CAD entities. It deliberately stops when
scale is unknown/ambiguous and keeps every candidate traceable to its source.
No quantity is silently corrected or accepted.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from core.drawings.geometry_takeoff import extract_geometry_candidates
from core.drawings.graphical_takeoff import extract_scale_candidates


def detect_scale(text: str) -> dict[str, Any]:
    values = extract_scale_candidates(text or "")
    unique = sorted(set(values))
    if not unique:
        return {"status": "unknown", "scale": None, "candidates": [], "needs_confirmation": True}
    if len(unique) > 1:
        return {"status": "ambiguous", "scale": None, "candidates": unique, "needs_confirmation": True}
    return {"status": "detected", "scale": unique[0], "candidates": unique, "needs_confirmation": False}


def _apply_explicit_openings(rows: list[dict[str, Any]], openings: Iterable[Mapping[str, Any]] | None) -> None:
    """Attach explicit opening/cutout information without changing gross quantity."""
    by_source: dict[str, float] = defaultdict(float)
    for opening in openings or ():
        parent = str(opening.get("parent_source") or "").strip()
        if not parent:
            continue
        try:
            value = float(opening.get("quantity", 0) or 0)
        except (TypeError, ValueError):
            value = -1.0
        for row in rows:
            if row.get("source") != parent:
                continue
            if value < 0:
                row["opening_error"] = True
                row["needs_confirmation"] = True
            else:
                by_source[parent] += value

    for row in rows:
        source = str(row.get("source") or "")
        if source not in by_source:
            continue
        opening = by_source[source]
        gross = float(row.get("quantity", 0) or 0)
        row["opening_quantity"] = opening
        row["net_quantity"] = max(0.0, gross - opening)
        row["opening_exceeds_gross"] = opening > gross
        row["needs_confirmation"] = True
        if opening > gross:
            row["opening_error"] = True


def generate_auto_takeoff(
    entities: Iterable[Any],
    *,
    scale_text: str = "",
    source_unit: str = "m",
    sheet: str = "",
    page: int | None = None,
    openings: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    scale = detect_scale(scale_text)
    rows = extract_geometry_candidates(list(entities), source_unit=source_unit)
    _apply_explicit_openings(rows, openings)
    for row in rows:
        row["sheet"] = sheet
        row["page"] = page
        row["scale_status"] = scale["status"]
        row["scale"] = scale["scale"]
        row["scale_candidates"] = scale["candidates"]
        if scale["needs_confirmation"]:
            row["needs_confirmation"] = True
            row["recognition_reason"] = (
                f"{row.get('recognition_reason', '')}; scale={scale['status']}"
            ).strip("; ")
    return {
        "kind": "cad_auto_takeoff",
        "scale": scale,
        "candidates": rows,
        "summary": {
            "candidate_count": len(rows),
            "review_required": sum(bool(x.get("needs_confirmation")) for x in rows),
            "by_metric": _metric_summary(rows),
            "by_element": _element_summary(rows),
            "opening_review_required": sum(bool(x.get("opening_quantity")) for x in rows),
        },
    }


def generate_multi_sheet_takeoff(sheets: Mapping[str, Mapping[str, Any]], *, source_unit: str = "m") -> dict[str, Any]:
    results: dict[str, Any] = {}
    for sheet_id in sorted(sheets):
        payload = sheets[sheet_id] or {}
        results[sheet_id] = generate_auto_takeoff(
            payload.get("entities", []),
            scale_text=str(payload.get("scale_text", "") or ""),
            source_unit=source_unit,
            sheet=str(sheet_id),
            page=payload.get("page"),
            openings=payload.get("openings"),
        )
    return {
        "kind": "multi_sheet_auto_takeoff",
        "sheets": results,
        "summary": {
            "sheet_count": len(results),
            "candidate_count": sum(x["summary"]["candidate_count"] for x in results.values()),
            "review_required": sum(x["summary"]["review_required"] for x in results.values()),
        },
    }


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for row in rows:
        out[str(row.get("metric", "unknown"))] += 1
    return dict(sorted(out.items()))


def _element_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for row in rows:
        out[str(row.get("element_type", "unknown"))] += 1
    return dict(sorted(out.items()))
