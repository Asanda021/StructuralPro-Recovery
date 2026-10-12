"""Deterministic project-management domain services.

This layer adds operational depth without performing engineering design:
schedule baselines, dependencies, daily reports, resources, materials,
meetings, KPIs, and schedule/progress variance.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import date
import math
from typing import Any, Iterable

TASK_STATUSES = ("todo", "in_progress", "blocked", "done", "cancelled")


def _nonneg(v, label):
    v = float(v)
    if not math.isfinite(v) or v < 0:
        raise ValueError(f"{label} must be finite and non-negative")
    return v


def _pct(v, label):
    v = float(v)
    if not math.isfinite(v) or not 0 <= v <= 100:
        raise ValueError(f"{label} must be between 0 and 100")
    return v


def _date(value: str) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw.replace("/", "-"))
    except ValueError:
        return None


@dataclass(frozen=True)
class ScheduleTask:
    id: str
    title: str
    planned_start: str
    planned_end: str
    actual_start: str = ""
    actual_end: str = ""
    progress: float = 0.0
    status: str = "todo"
    predecessor_ids: tuple[str, ...] = ()
    responsible: str = ""
    weight: float = 1.0


@dataclass(frozen=True)
class DailyReport:
    id: str
    date: str
    summary: str
    progress: float = 0.0
    weather: str = ""
    notes: str = ""
    workforce: float = 0.0


@dataclass(frozen=True)
class ResourceRecord:
    id: str
    name: str
    kind: str
    quantity: float
    unit: str = ""
    date: str = ""
    status: str = "active"


@dataclass(frozen=True)
class MaterialRecord:
    id: str
    name: str
    quantity: float
    unit: str
    date: str = ""
    supplier: str = ""
    status: str = "received"


@dataclass(frozen=True)
class MeetingRecord:
    id: str
    date: str
    title: str
    participants: str = ""
    decisions: str = ""
    actions: str = ""
    follow_up_date: str = ""


class ProjectManagement:
    def __init__(self, *, tasks: Iterable[ScheduleTask] = (),
                 daily_reports: Iterable[DailyReport] = (),
                 resources: Iterable[ResourceRecord] = (),
                 materials: Iterable[MaterialRecord] = (),
                 meetings: Iterable[MeetingRecord] = ()):
        self.tasks = list(tasks)
        self.daily_reports = list(daily_reports)
        self.resources = list(resources)
        self.materials = list(materials)
        self.meetings = list(meetings)
        self.validate()

    def _ids(self, items, label):
        seen = set()
        for x in items:
            if not str(x.id).strip():
                raise ValueError(f"{label} id is required")
            if x.id in seen:
                raise ValueError(f"duplicate {label} id: {x.id}")
            seen.add(x.id)

    def validate(self):
        for items, label in (
            (self.tasks, "task"), (self.daily_reports, "daily report"),
            (self.resources, "resource"), (self.materials, "material"),
            (self.meetings, "meeting"),
        ):
            self._ids(items, label)

        task_ids = {x.id for x in self.tasks}
        for x in self.tasks:
            if not x.title.strip():
                raise ValueError("task title is required")
            _pct(x.progress, "task progress")
            if x.status not in TASK_STATUSES:
                raise ValueError("invalid task status")
            if _nonneg(x.weight, "task weight") == 0:
                raise ValueError("task weight must be greater than zero")
            start, end = _date(x.planned_start), _date(x.planned_end)
            if start and end and start > end:
                raise ValueError("planned task start cannot be after planned end")
            for predecessor in x.predecessor_ids:
                if predecessor == x.id:
                    raise ValueError("task cannot depend on itself")
                if predecessor not in task_ids:
                    raise ValueError(f"unknown predecessor task: {predecessor}")

        successors = {key: [] for key in task_ids}
        degree = {task.id: len(set(task.predecessor_ids)) for task in self.tasks}
        for task in self.tasks:
            for predecessor in set(task.predecessor_ids):
                successors[predecessor].append(task.id)
        ready = [key for key, value in degree.items() if value == 0]
        visited = 0
        while ready:
            key = ready.pop()
            visited += 1
            for successor in successors[key]:
                degree[successor] -= 1
                if degree[successor] == 0: ready.append(successor)
        if visited != len(task_ids):
            raise ValueError("وابستگی دوری در برنامه پروژه مجاز نیست")

        for x in self.daily_reports:
            _pct(x.progress, "daily report progress")
            _nonneg(x.workforce, "daily report workforce")
            if x.date and _date(x.date) is None:
                raise ValueError("invalid daily report date")
        for x in self.resources:
            _nonneg(x.quantity, "resource quantity")
        for x in self.materials:
            _nonneg(x.quantity, "material quantity")
        for x in self.meetings:
            if x.follow_up_date and _date(x.follow_up_date) is None:
                raise ValueError("invalid meeting follow-up date")
        return self

    def _add(self, target, item, label):
        if any(x.id == item.id for x in target):
            raise ValueError(f"duplicate {label} id")
        target.append(item)
        try:
            self.validate()
        except Exception:
            target.pop()
            raise
        return item

    def add_task(self, x): return self._add(self.tasks, x, "task")
    def add_daily_report(self, x): return self._add(self.daily_reports, x, "daily report")
    def add_resource(self, x): return self._add(self.resources, x, "resource")
    def add_material(self, x): return self._add(self.materials, x, "material")
    def add_meeting(self, x): return self._add(self.meetings, x, "meeting")

    def schedule_summary(self, *, as_of: str | None = None):
        total = len(self.tasks)
        avg = sum(x.progress for x in self.tasks) / total if total else 0
        completed = sum(x.progress >= 100 or x.status == "done" for x in self.tasks)
        result = {
            "task_count": total,
            "completed_tasks": completed,
            "average_progress": avg,
        }
        if as_of is not None:
            weight_total = sum(x.weight for x in self.tasks)
            weighted = sum(x.progress * x.weight for x in self.tasks) / weight_total if weight_total else 0
            today = _date(as_of)
            if today is None:
                raise ValueError("invalid schedule summary date")
            overdue = sum(
                bool(_date(x.planned_end) and _date(x.planned_end) < today
                     and x.progress < 100 and x.status != "cancelled")
                for x in self.tasks
            )
            result.update({"weighted_progress": weighted, "overdue_tasks": overdue})
        return result

    def actual_vs_plan(self):
        rows = []
        for x in self.tasks:
            planned_end, actual_end = _date(x.planned_end), _date(x.actual_end)
            delay_days = (actual_end - planned_end).days if planned_end and actual_end else 0
            rows.append({
                **asdict(x),
                "started": bool(x.actual_start),
                "finished": bool(x.actual_end),
                "delay": delay_days > 0,
                "delay_days": max(delay_days, 0),
            })
        return rows

    def dependency_ready(self, task_id: str) -> bool:
        task = next((x for x in self.tasks if x.id == task_id), None)
        if task is None:
            raise KeyError(task_id)
        done = {x.id for x in self.tasks if x.progress >= 100 or x.status == "done"}
        return all(x in done for x in task.predecessor_ids)

    def blocked_tasks(self):
        return [x.id for x in self.tasks
                if x.status not in {"done", "cancelled"} and not self.dependency_ready(x.id)]

    def resource_summary(self):
        active = [x for x in self.resources if x.status == "active"]
        by_kind = {}
        for x in active:
            by_kind[x.kind] = by_kind.get(x.kind, 0.0) + x.quantity
        return {"active_count": len(active), "quantity_by_kind": by_kind}

    def material_summary(self):
        received = [x for x in self.materials if x.status == "received"]
        by_unit = {}
        for x in received:
            key = f"{x.name}|{x.unit}"
            by_unit[key] = by_unit.get(key, 0.0) + x.quantity
        return {"received_count": len(received), "quantity_by_material": by_unit}

    def daily_progress_summary(self):
        if not self.daily_reports:
            return {"report_count": 0, "latest_progress": 0.0, "average_progress": 0.0, "workforce_total": 0.0}
        ordered = sorted(self.daily_reports, key=lambda x: x.date)
        return {
            "report_count": len(ordered),
            "latest_progress": ordered[-1].progress,
            "average_progress": sum(x.progress for x in ordered) / len(ordered),
            "workforce_total": sum(x.workforce for x in ordered),
        }

    def meeting_followups(self, *, as_of: str | None = None):
        today = _date(as_of) if as_of else date.today()
        return [
            asdict(x) for x in self.meetings
            if x.follow_up_date and _date(x.follow_up_date) and _date(x.follow_up_date) <= today
            and x.actions.strip()
        ]

    def dashboard(self, *, as_of: str | None = None):
        schedule = self.schedule_summary(as_of=as_of)
        return {
            **schedule,
            "daily_report_count": len(self.daily_reports),
            "resource_count": len(self.resources),
            "material_record_count": len(self.materials),
            "meeting_count": len(self.meetings),
            "latest_report_date": max((x.date for x in self.daily_reports), default=""),
            "latest_material_date": max((x.date for x in self.materials), default=""),
            "blocked_tasks": self.blocked_tasks(),
            "daily_progress": self.daily_progress_summary(),
            "resources": self.resource_summary(),
            "materials": self.material_summary(),
            "meeting_followup_count": len(self.meeting_followups(as_of=as_of)),
        }

    def export_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {
            k: [asdict(x) for x in getattr(self, k)]
            for k in ("tasks", "daily_reports", "resources", "materials", "meetings")
        }
