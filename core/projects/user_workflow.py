"""Deterministic real-user workflow for the StructuralPro desktop product.

The workflow is intentionally derived from persisted project data. It does not
perform engineering calculations and it does not let AI decide project state.
Its job is to make the user's next meaningful action explicit and traceable.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping
from core.projects.project_model import ProjectModel, _identity

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


def reconcile_persisted_takeoff_identities(saved: Mapping[str, Any], model: ProjectModel) -> dict[str, Any]:
    """Audit existing SQLite takeoff identities; never guess, calculate, or write.

    A linked record is only an identity link, NOT a verified quantity/review/BOQ
    receipt. Original registry keys and spelling remain unchanged.
    """
    from copy import deepcopy

    if not isinstance(saved, Mapping) or model.validate():
        raise ValueError("مدل یا داده پروژه برای تطبیق معتبر نیست")
    floors = {_identity(row["id"]): row["id"] for row in model.floors}
    members = {_identity(row["id"]): row for row in model.members}
    records: list[dict[str, Any]] = []
    registry_sources: dict[str, list[dict[str, Any]]] = {}

    def add(registry: str, record_key: str, floor: Any, member: Any,
            *, source_id: Any = None, revision: Any = None, persisted_status: Any = None):
        f, m = _identity(floor), _identity(member)
        status, reason = "linked", None
        if not f or not m:
            status, reason = "blocked", "missing_explicit_floor_or_member"
        elif f not in floors:
            status, reason = "blocked", "unknown_floor"
        elif m not in members:
            status, reason = "blocked", "unknown_member"
        elif _identity(members[m]["floor_id"]) != f:
            status, reason = "blocked", "member_floor_mismatch"
        item = {"registry": registry, "record_key": str(record_key),
                "status": status, "reason": reason,
                "floor_id": floors.get(f) if status == "linked" else None,
                "member_id": members[m]["id"] if status == "linked" else None,
                "source_id": str(source_id).strip() if _identity(source_id) else None,
                "revision": revision if type(revision) in (str, int) else None,
                "persisted_status": str(persisted_status) if persisted_status is not None else None}
        records.append(item)
        return item

    for registry, floor_field, member_field in (
        ("reviewed_structural_members", "floor_id", "member_id"),
        ("reviewed_aec_systems", "floor_id", "system_id"),
        ("manual_formula_register", "floor", "member"),
    ):
        register = saved.get(registry, {})
        if register is None:
            register = {}
        if not isinstance(register, dict):
            raise ValueError(f"ساختار دفتر متره {registry} نامعتبر است")
        for key, record in register.items():
            if not isinstance(record, dict) or not isinstance(record.get("data"), dict):
                add(registry, str(key), None, None)
                continue
            data = record["data"]
            sid = (data.get("source") or {}).get("source_id") if isinstance(data.get("source"), dict) else data.get("source_id")
            item = add(registry, str(key), data.get(floor_field),
                       data.get(member_field), source_id=sid,
                       revision=record.get("revision"), persisted_status=record.get("status"))
            if record.get("status") != "committed":
                continue
            if registry == "manual_formula_register":
                committed_ids = [data.get("source_id")]
            else:
                committed_ids = record.get("committed_source_ids", record.get("source_ids", []))
            if not isinstance(committed_ids, list):
                item["status"], item["reason"] = "blocked", "invalid_committed_sources"
                continue
            if not committed_ids:
                item["status"], item["reason"] = "blocked", "missing_committed_sources"
            for source in committed_ids:
                if not _identity(source):
                    item["status"], item["reason"] = "blocked", "invalid_committed_sources"
                    continue
                registry_sources.setdefault(_identity(source), []).append(item)

    takeoffs = saved.get("takeoffs", [])
    if takeoffs is None:
        takeoffs = []
    if not isinstance(takeoffs, list):
        raise ValueError("فهرست متره ذخیره‌شده معتبر نیست")
    seen: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(takeoffs):
        key = str(index)
        if not isinstance(row, dict):
            add("takeoffs", key, None, None)
            continue
        source = row.get("source_id")
        source_key = _identity(source)
        params = row.get("params", {})
        if not isinstance(params, dict):
            params = {}
        parents = registry_sources.get(source_key, []) if source_key else []
        if len(parents) == 1:
            parent = parents[0]
            floor, member = parent["floor_id"], parent["member_id"]
            if parent["status"] != "linked":
                floor = member = None
        elif not parents:
            # Generic manual rows default member_code to the item type: that
            # default is NOT a proven member identity. Only explicitly saved
            # per-row member_code or manual_location_id can establish a link.
            member = params.get("member_code") or params.get("manual_location_id")
            floor = row.get("system")
        else:
            floor = member = None
        item = add("takeoffs", key, floor, member, source_id=source,
                   revision=row.get("revision"), persisted_status="stored")
        if not source_key:
            item["status"], item["reason"] = "blocked", "missing_source_id"
        elif not parents and params.get("member_code") and (
                _identity(row.get("member_code")) != _identity(params["member_code"])):
            item["status"], item["reason"] = "blocked", "explicit_member_conflict"
        elif len(parents) > 1:
            item["status"], item["reason"] = "blocked", "ambiguous_source_registry"
        elif len(parents) == 1:
            parent = parents[0]
            if parent["status"] != "linked":
                item["status"], item["reason"] = "blocked", "invalid_parent_record"
            elif (_identity(row.get("system")) != _identity(parent["floor_id"])
                  or _identity(row.get("member_code")) != _identity(parent["member_id"])):
                item["status"], item["reason"] = "blocked", "registry_takeoff_identity_mismatch"
            elif params.get("member_code") and _identity(params["member_code"]) != _identity(parent["member_id"]):
                item["status"], item["reason"] = "blocked", "explicit_member_conflict"
        if source_key:
            if source_key in seen:
                item["status"], item["reason"] = "blocked", "duplicate_takeoff_source"
                seen[source_key]["status"] = "blocked"
                seen[source_key]["reason"] = "duplicate_takeoff_source"
            else:
                seen[source_key] = item

    for source_key, parents in registry_sources.items():
        if len(parents) > 1:
            for parent in parents:
                parent["status"], parent["reason"] = "blocked", "ambiguous_committed_source"
        for parent in parents:
            if source_key not in seen:
                parent["status"], parent["reason"] = "blocked", "missing_committed_takeoff"
            elif seen[source_key]["status"] == "blocked":
                parent["status"], parent["reason"] = "blocked", "invalid_committed_takeoff"

    # A stale or conflicting registry must never yield a selectable child link.
    for item in records:
        if item["registry"] != "takeoffs" or not item["source_id"]:
            continue
        parents = registry_sources.get(_identity(item["source_id"]), [])
        if parents and (len(parents) != 1 or parents[0]["status"] != "linked"):
            item["status"], item["reason"] = "blocked", "invalid_parent_record"

    linked = sum(x["status"] == "linked" for x in records)
    return deepcopy({"project_id": model.project_id, "records": records,
                     "linked": linked, "blocked": len(records)-linked,
                     "coverage": {"total": len(records), "linked": linked, "blocked": len(records)-linked}})

class LiveTakeoffTracker:
    """Nonfinancial, in-memory event reducer for the existing project model.

    Emit notifications only AFTER the real calculation or review service.
    Never writes SQLite, calculates quantities, or authorizes BOQ.
    A BOQ badge requires a verifier backed by the existing authoritative service.
    """

    _TASK_TRANSITIONS = {
        "takeoff_started": ({"not_started", "needs_input", "error", "calculated"}, "in_progress"),
        "input_required": ({"in_progress"}, "needs_input"),
        "validation_failed": ({"in_progress"}, "error"),
        "quantity_calculated": ({"in_progress"}, "calculated"),
        "review_approved": ({"calculated"}, "reviewed"),
        "review_rejected": ({"calculated"}, "needs_input"),
    }

    def __init__(self, project: ProjectModel, *, boq_receipt_verifier: Callable[[Mapping[str, str]], bool] | None = None):
        if not isinstance(project, ProjectModel) or project.validate():
            raise ValueError("ساختار پروژه و هویت طبقات یا اعضا معتبر نیست")
        self.project = project
        self._verifier = boq_receipt_verifier
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._tasks: dict[tuple[str, str], dict[str, str]] = {}
        self._last_event: dict[str, Any] | None = None
        self._sequence = 0
        self.selected_floor_id: str | None = None
        self.selected_member_id: str | None = None

    @classmethod
    def from_store(cls, store: Any, project_id: str, *,
                   boq_receipt_verifier: Callable[[Mapping[str, str]], bool] | None = None):
        """Read explicit structure from the existing SQLite-backed project store.

        This is a read-only UI adapter: neither missing floors/members nor
        calculation/review/BOQ events are reconstructed or fabricated. The
        returned tracker starts with an empty, in-memory event history.
        """
        if not _identity(project_id):
            raise ValueError("شناسه پروژه برای بارگذاری الزامی است")
        if not callable(getattr(store, "get", None)):
            raise TypeError("منبع پروژه باید سرویس ذخیره‌سازی معتبر باشد")
        saved = store.get(str(project_id))
        if saved is None:
            raise KeyError(project_id)
        if not isinstance(saved, dict):
            raise ValueError("ساختار پروژه ذخیره‌شده معتبر نیست")
        stored_id = saved.get("id")
        if (not _identity(stored_id)
                or _identity(stored_id) != _identity(project_id)
                or (saved.get("project_id") is not None
                    and _identity(saved["project_id"]) != _identity(stored_id))):
            raise ValueError("هویت پروژه در SQLite با درخواست مطابقت ندارد")
        floors, members = saved.get("floors", []), saved.get("members", [])
        if not isinstance(floors, list) or not isinstance(members, list):
            raise ValueError("فهرست طبقات یا اعضای ذخیره‌شده معتبر نیست")
        from copy import deepcopy
        model = ProjectModel(project_id=str(stored_id), name=saved.get("name", ""),
                             floors=deepcopy(floors), members=deepcopy(members))
        tracker = cls(model, boq_receipt_verifier=boq_receipt_verifier)
        tracker._persisted_identity = reconcile_persisted_takeoff_identities(saved, model)
        tracker._origin_store = store
        meta = saved.get("_meta")
        tracker._origin_version = meta.get("version") if isinstance(meta, dict) else None
        return tracker

    def persisted_identity_snapshot(self) -> dict[str, Any]:
        """Read-only identities; linked never means calculated, reviewed or payable."""
        from copy import deepcopy
        return deepcopy(getattr(self, "_persisted_identity", {
            "project_id": self.project.project_id,
            "records": [], "linked": 0, "blocked": 0,
            "coverage": {"total": 0, "linked": 0, "blocked": 0},
        }))

    def select_persisted_record(self, registry: str, record_key: str):
        """Select an explicit stored member only while its SQLite version is current."""
        audit = self.persisted_identity_snapshot()
        matches = [row for row in audit["records"]
                   if row["registry"] == registry and row["record_key"] == str(record_key)]
        if len(matches) != 1 or matches[0]["status"] != "linked":
            raise ValueError("هویت عضو ذخیره‌شده قابل انتخاب نیست؛ ابتدا تطبیق را اصلاح کنید")
        store = getattr(self, "_origin_store", None)
        version = getattr(self, "_origin_version", None)
        if store is None or type(version) is not int:
            raise ValueError("نسخه SQLite برای انتخاب ایمن مشخص نیست")
        current = store.get(self.project.project_id)
        if (not isinstance(current, dict)
                or not isinstance(current.get("_meta"), dict)
                or current["_meta"].get("version") != version):
            raise RuntimeError("پروژه از زمان بارگذاری تغییر کرده است؛ داده‌ها را دوباره باز کنید")
        row = matches[0]
        floor = self._floor(row["floor_id"])
        member = self._member(floor["id"], row["member_id"])
        self.selected_floor_id, self.selected_member_id = floor["id"], member["id"]
        return self._publish({"type": "member_selected", "floor_id": floor["id"],
                              "member_id": member["id"], "registry": registry,
                              "record_key": str(record_key),
                              "source_id": row["source_id"], "revision": row["revision"]})

    def subscribe(self, callback: Callable[[dict[str, Any]], None]):
        if not callable(callback):
            raise TypeError("تابع شنونده معتبر نیست")
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)

    def _floor(self, floor_id: str) -> dict:
        for floor in self.project.floors:
            if _identity(floor["id"]) == _identity(floor_id) and _identity(floor_id):
                return floor
        raise ValueError("طبقه ناشناخته است")

    def _member(self, floor_id: str, member_id: str) -> dict:
        for member in self.project.members:
            if _identity(member["id"]) == _identity(member_id) and _identity(member_id):
                if _identity(member["floor_id"]) != _identity(floor_id):
                    raise ValueError("عضو متعلق به این طبقه نیست")
                return member
        raise ValueError("عضو ناشناخته است")

    def _publish(self, event: dict[str, Any]):
        self._sequence += 1
        message = dict(event, sequence=self._sequence, project_id=self.project.project_id)
        self._last_event = message.copy()
        for callback in tuple(self._subscribers):
            callback(message.copy())
        return message.copy()

    def select_floor(self, floor_id: str):
        floor = self._floor(floor_id)
        self.selected_floor_id = floor["id"]
        self.selected_member_id = None
        return self._publish({"type": "floor_selected", "floor_id": floor["id"]})

    def select_member(self, floor_id: str, member_id: str):
        floor = self._floor(floor_id)
        member = self._member(floor["id"], member_id)
        self.selected_floor_id = floor["id"]
        self.selected_member_id = member["id"]
        return self._publish({"type": "member_selected", "floor_id": floor["id"], "member_id": member["id"]})

    def emit(self, event_type: str, *, floor_id: str, member_id: str, task_id: str,
             source_id: str | None = None, revision: str | None = None):
        if event_type not in self._TASK_TRANSITIONS:
            raise ValueError("نوع رویداد متره پشتیبانی نمی‌شود")
        floor = self._floor(floor_id)
        member = self._member(floor["id"], member_id)
        if not _identity(task_id):
            raise ValueError("شناسه عملیات متره الزامی است")
        key = (_identity(member["id"]), _identity(task_id))
        before = self._tasks.get(key, {"status": "not_started", "source_id": "", "revision": ""})
        allowed, after_status = self._TASK_TRANSITIONS[event_type]
        if before["status"] not in allowed:
            raise ValueError("ترتیب رویدادهای متره معتبر نیست")
        if event_type == "quantity_calculated" and (not _identity(source_id) or not _identity(revision)):
            raise ValueError("نتیجه محاسبه به مدرک و نسخه صریح نیاز دارد")
        if event_type == "review_approved" and (
            not _identity(source_id) or not _identity(revision)
            or _identity(source_id) != _identity(before["source_id"])
            or _identity(revision) != _identity(before["revision"])
        ):
            raise ValueError("تأیید باید متعلق به مدرک و نسخه همان محاسبه باشد")
        row = before.copy()
        row["status"] = after_status
        if event_type == "takeoff_started":
            row["source_id"] = ""
            row["revision"] = ""
        if event_type == "quantity_calculated":
            row["source_id"] = str(source_id).strip()
            row["revision"] = str(revision).strip()
        self._tasks[key] = row
        return self._publish({"type": event_type, "floor_id": floor["id"], "member_id": member["id"],
                              "task_id": str(task_id).strip(), "status": row["status"],
                              "source_id": row["source_id"], "revision": row["revision"]})

    def confirm_boq_transfer(self, *, floor_id: str, member_id: str, task_id: str,
                             receipt: Mapping[str, str]):
        """Show a BOQ badge only after verification by the existing BOQ service."""
        floor = self._floor(floor_id)
        member = self._member(floor["id"], member_id)
        if not _identity(task_id):
            raise ValueError("شناسه عملیات الزامی است")
        key = (_identity(member["id"]), _identity(task_id))
        previous = self._tasks.get(key)
        if not previous or previous["status"] != "reviewed":
            raise ValueError("متره هنوز تأیید نشده است")
        required = {"project_id": self.project.project_id, "floor_id": floor["id"],
                    "member_id": member["id"], "task_id": str(task_id).strip(),
                    "source_id": previous["source_id"], "revision": previous["revision"]}
        if not isinstance(receipt, Mapping) or not all(
            _identity(receipt.get(field)) == _identity(value) for field, value in required.items()
        ) or not _identity(receipt.get("boq_row_id")):
            raise ValueError("رسید BOQ با هویت متره مطابقت ندارد")
        if self._verifier is None or not self._verifier(receipt):
            raise ValueError("ثبت BOQ در سرویس اصلی احراز نشده است")
        self._tasks[key] = dict(previous, status="boq_transferred")
        return self._publish({"type": "boq_transfer_confirmed", "floor_id": floor["id"],
                              "member_id": member["id"], "task_id": str(task_id).strip(),
                              "status": "boq_transferred", "boq_row_id": receipt["boq_row_id"],
                              "source_id": previous["source_id"], "revision": previous["revision"]})

    def snapshot(self) -> dict[str, Any]:
        return {"project_id": self.project.project_id,
                "sequence": self._sequence,
                "selected_floor_id": self.selected_floor_id,
                "selected_member_id": self.selected_member_id,
                "tasks": {f"{member}:{task}": data.copy() for (member, task), data in self._tasks.items()},
                "last_event": self._last_event.copy() if self._last_event else None}

