"""Deterministic real-user workflow for the StructuralPro desktop product.

The workflow is intentionally derived from persisted project data. It does not
perform engineering calculations and it does not let AI decide project state.
Its job is to make the user's next meaningful action explicit and traceable.
"""
from __future__ import annotations

from typing import Any

STAGES: tuple[dict[str, str], ...] = (
    {"key": "project", "title": "پروژه", "action": "اطلاعات پایه پروژه را تکمیل کنید."},
    {"key": "takeoff", "title": "متره", "action": "حداقل یک آیتم متره ثبت و تأیید کنید."},
    {"key": "boq", "title": "BOQ", "action": "ردیف‌های BOQ را بازبینی کنید."},
    {"key": "estimate", "title": "برآورد", "action": "برآورد را بازسازی و کنترل کنید."},
    {"key": "progress", "title": "پیشرفت", "action": "مقدار جاری/تجمعی پیشرفت را ثبت کنید."},
    {"key": "payment", "title": "صورت‌وضعیت", "action": "دوره صورت‌وضعیت را ثبت یا بازبینی کنید."},
    {"key": "finance", "title": "مالی", "action": "هزینه، تعهد، دریافتی و اسناد مالی را کنترل کنید."},
    {"key": "report", "title": "گزارش", "action": "گزارش نهایی پروژه را تولید و بازبینی کنید."},
)


def _count(project: dict[str, Any], key: str) -> int:
    value = project.get(key, [])
    return len(value) if isinstance(value, list) else 0


def _has_estimate(project: dict[str, Any]) -> bool:
    estimate = project.get("estimate")
    return isinstance(estimate, dict) and bool(estimate.get("summary") or estimate.get("boq"))


def evaluate_workflow(project: dict[str, Any]) -> dict[str, Any]:
    """Return a stable workflow snapshot for a persisted project.

    Statuses:
    - ready: the user can perform the stage's action now
    - in_progress: useful data exists but the stage is not complete
    - complete: the stage has a meaningful persisted result
    - blocked: a prerequisite is missing
    """
    if not isinstance(project, dict):
        raise TypeError("project must be a dictionary")

    project_id = str(project.get("id") or "").strip()
    name = str(project.get("name") or "").strip()
    takeoffs = _count(project, "takeoffs")
    boq = _count(project, "boq")
    periods = _count(project, "statement_periods")
    financial = sum(
        _count(project, key)
        for key in ("cost_entries", "commitment_entries", "receipts", "financial_documents")
    )

    checks = {
        "project": bool(project_id and name),
        "takeoff": takeoffs > 0,
        "boq": boq > 0,
        "estimate": _has_estimate(project),
        "progress": any(
            float(row.get("current_quantity", 0) or 0) > 0
            for row in (project.get("boq", []) or [])
            if isinstance(row, dict)
        ),
        "payment": periods > 0,
        "finance": financial > 0,
        "report": _has_estimate(project) and (boq > 0 or periods > 0),
    }

    stages: list[dict[str, Any]] = []
    prerequisite_ok = True
    for stage in STAGES:
        key = stage["key"]
        complete = checks[key] and (
            key == "project" or prerequisite_ok
        )
        blocked = not prerequisite_ok
        if blocked:
            status = "blocked"
        elif complete:
            status = "complete"
        elif key == "project":
            status = "ready" if not checks[key] else "complete"
        else:
            status = "ready"
        stages.append({
            "key": key,
            "title": stage["title"],
            "status": status,
            "complete": bool(complete),
            "action": stage["action"],
        })
        # A stage becomes a prerequisite only when it is expected to produce
        # data before the next stage. Users can still navigate directly in UI.
        prerequisite_ok = prerequisite_ok and bool(checks[key])

    first_incomplete = next((x for x in stages if x["status"] != "complete"), None)
    completed_count = sum(1 for x in stages if x["status"] == "complete")
    blockers = [
        {
            "stage": x["title"],
            "reason": "پیش‌نیاز مرحله قبل هنوز تکمیل نشده است.",
        }
        for x in stages
        if x["status"] == "blocked"
    ]

    return {
        "project_id": project_id,
        "project_name": name,
        "current_stage": first_incomplete["key"] if first_incomplete else "report",
        "current_title": first_incomplete["title"] if first_incomplete else "گزارش",
        "next_action": first_incomplete["action"] if first_incomplete else "چرخه پروژه آماده بازبینی نهایی است.",
        "completed": completed_count,
        "total": len(stages),
        "completion_percent": round(completed_count / len(stages) * 100, 1),
        "stages": stages,
        "blockers": blockers,
        "counts": {
            "takeoffs": takeoffs,
            "boq": boq,
            "statement_periods": periods,
            "financial_records": financial,
        },
    }


def stage_status(project: dict[str, Any], stage: str) -> str:
    """Return one stage status, raising for unknown stages."""
    snapshot = evaluate_workflow(project)
    for item in snapshot["stages"]:
        if item["key"] == stage:
            return item["status"]
    raise KeyError(stage)
