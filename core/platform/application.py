"""Application service shared by desktop and future mobile/chat clients."""
from __future__ import annotations
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import math
from datetime import datetime, timezone
from typing import Any
from core.projects.store import ProjectStore
from core.takeoff.engine import TakeoffEngine
from core.takeoff.boq import build_boq, boq_summary
from core.takeoff.estimate import build_estimate
from core.takeoff.assembly_templates import AssemblyTemplateLibrary
from core.commercial.progress import build_progress
from core.reports.project_report import build_report
from core.ai.qa_engine import ProjectQA
from core.ai.engineering_assistant import EngineeringAssistant
from core.projects.user_workflow import evaluate_workflow
from core.validation.real_data import validate_project
from core.engineering import EngineeringLibrary
from core.projects.management import ProjectManagement, ScheduleTask, DailyReport, ResourceRecord, MaterialRecord, MeetingRecord
from core.commercial.finance_depth import FinancePaymentControl, PaymentRecord, PaymentAllocation, BudgetLine
from core.drawings.model_registry import ModelRegistry, ModelSource, ModelObject
from core.performance.project_performance import paginate, project_performance_snapshot
from core.recovery.recovery import export_project, import_project
from core.aec.disciplines import takeoff_domain
from core.drawings.takeoff_bridge import session_to_boq_rows, validate_session_payload
from core.takeoff.ai_output_guard import validate_ai_takeoff_proposal


def _normalize_date_key(value: str) -> str | None:
    """Normalize simple Persian/Gregorian project dates for deterministic aging checks."""
    raw = str(value or "").strip()
    if not raw:
        return None
    trans = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    raw = raw.translate(trans).replace("-", "/").replace(".", "/")
    parts = raw.split("/")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    y, m, d = (int(part) for part in parts)
    if y < 1 or not 1 <= m <= 12:
        return None
    max_day = 31 if m <= 6 else 30
    if m == 12:
        # Civil Jalali 33-year-cycle validation for Esfand's 29/30-day boundary.
        # This is used only for input validation; it does not convert dates.
        cycle_day = y % 33
        leap = cycle_day in {1, 5, 9, 13, 17, 22, 26, 30}
        max_day = 30 if leap else 29
    if not 1 <= d <= max_day:
        return None
    return f"{y:04d}/{m:02d}/{d:02d}"

# The original PR #481 branch is unavailable. These rules restore the documented
# payable/consumption split without changing the payment treatment of legacy
# concrete, steel, or masonry assembly components.
_FINISH_ASSEMBLY_CODES = frozenset({
    "gypsum_scratch", "gypsum_finish", "cement_render", "wall_tile",
    "wall_paint", "waterproofing_wall", "facade_finish", "floor_tile",
    "floor_screed", "ceiling_paint", "false_ceiling",
    "waterproofing_floor", "skirting",
})


def _finish_component_role(assembly_code: str, component_code: str) -> str:
    if assembly_code not in _FINISH_ASSEMBLY_CODES:
        return "work"
    if component_code == assembly_code + "_procurement":
        return "procurement"
    if component_code == assembly_code + "_material":
        return "material"
    return "work"


def _is_payable_quantity(takeoff: dict[str, Any], quantity: dict[str, Any]) -> bool:
    explicit_role = str(quantity.get("role") or takeoff.get("component_role") or "").strip()
    if explicit_role:
        # Fail closed: unknown role is not silently treated as payable work.
        if explicit_role not in {"work", "procurement", "material"}:
            raise ValueError("نقش جزء متره ناشناخته است")
        return explicit_role == "work"
    params = takeoff.get("params") or {}
    assembly_code = str(params.get("assembly_code", ""))
    component_code = str(quantity.get("code", ""))
    # Backward-compatible: old saved finish rows had no role marker.
    return _finish_component_role(assembly_code, component_code) == "work"


class StructuralProApp:
    def __init__(self,data_dir: str|Path):
        self.data_dir=Path(data_dir); self.data_dir.mkdir(parents=True,exist_ok=True)
        self.store=ProjectStore(self.data_dir/"projects.db")
        self.takeoff=TakeoffEngine()
        self.qa=ProjectQA()
        self.ai_assistant = EngineeringAssistant()
        self.engineering = EngineeringLibrary()

    @staticmethod
    def _build_project_boq(project: dict[str, Any]) -> list[dict[str, Any]]:
        """Single payable-BOQ rebuild route for manual, drawing, AI and revisions.

        Procurement and material-consumption figures remain as auditable takeoffs
        but are never billed twice in the payment BOQ.
        """
        boq_inputs: list[dict[str, Any]] = []
        for takeoff in project.get("takeoffs", []):
            for quantity in takeoff.get("quantities", []):
                if not _is_payable_quantity(takeoff, quantity):
                    continue
                group = takeoff.get("domain") or "manual"
                boq_inputs.append({
                    "source": takeoff.get("source_id", "") or "manual",
                    "source_id": takeoff.get("source_id", ""),
                    "source_type": "takeoff",
                    "description": quantity.get("title", ""),
                    "quantity": quantity.get("amount", 0),
                    "unit": quantity.get("unit", ""),
                    "item_code": quantity.get("code", ""),
                    "price_code": quantity.get("price_code"),
                    "unit_price": quantity.get("unit_price"),
                    "category": group, "group": group,
                })
        return build_boq(boq_inputs)

    def create_project(self,name:str,project_id:str)->dict[str,Any]:
        project={"id":project_id,"name":name,"takeoffs":[],"boq":[],"metadata":{"offline":True}}
        self.store.save(project_id,project); return self.store.get(project_id)

    def open_project(self,project_id:str)->dict[str,Any]|None: return self.store.get(project_id)

    def ai_assistant_context(self, project_id: str) -> dict[str, Any]:
        """Return the bounded project context used by the AI assistant."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return self.ai_assistant.context(project)

    def ai_assistant_respond(self, project_id: str, prompt: str) -> dict[str, Any]:
        """Return an explainable, read-only AI response for a persisted project."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        response = self.ai_assistant.respond(
            prompt,
            project=project,
            validator=validate_project,
        )
        return {
            "intent": response.intent,
            "text": response.text,
            "confidence": response.confidence,
            "evidence": list(response.evidence),
            "proposals": list(response.proposals),
            "requires_confirmation": response.requires_confirmation,
            "deterministic": response.deterministic,
            "offline": True,
        }

    def project_reliability_status(self, project_id: str) -> dict[str, Any]:
        """Return persistence integrity and project revision health."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        revisions = self.store.revisions(project_id)
        integrity = self.store.integrity_check()
        return {
            "project_id": project_id,
            "integrity": integrity,
            "revision_count": len(revisions),
            "current_version": revisions[-1]["version"] if revisions else 0,
            "recoverable": bool(integrity.get("ok")) and bool(revisions),
        }

    def backup_project_database(self, backup_path: str | Path) -> dict[str, Any]:
        """Create a consistent SQLite backup of all projects."""
        return self.store.backup(backup_path)

    def export_project_backup(self, project_id: str, path: str | Path) -> dict[str, Any]:
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return export_project(project, path)

    def import_project_backup(self, path: str | Path) -> dict[str, Any]:
        """Read and validate a project backup; does not persist it."""
        return import_project(path)

    def project_performance_snapshot(self, project_id: str) -> dict[str, Any]:
        """Return deterministic size/collection metrics without mutating project data."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return project_performance_snapshot(project)

    def project_collection_page(self, project_id: str, collection: str, *, page: int = 1,
                                page_size: int = 100) -> dict[str, Any]:
        """Read a bounded page from a large project collection."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        allowed = {
            "takeoffs", "boq", "estimates", "reports", "drawings", "floors",
            "model_sources", "model_objects", "project_schedule_tasks",
            "project_daily_reports", "project_resources", "project_materials",
            "project_meetings", "financial_documents",
        }
        if collection not in allowed:
            raise ValueError(f"unsupported project collection: {collection}")
        return paginate(project.get(collection, []) or [], page=page, page_size=page_size)

    def engineering_library_snapshot(self) -> dict[str, list[dict[str, Any]]]:
        """Return the immutable reference-library snapshot for clients and reports."""
        return self.engineering.snapshot()

    def search_engineering_library(self, query: str = "", *, category: str | None = None) -> list[dict[str, Any]]:
        """Search engineering references without touching project data."""
        return self.engineering.search(query, category=category)

    def engineering_library_status(self) -> dict[str, Any]:
        """Return deterministic health and item counts for engineering references."""
        return self.engineering.validate()

    def validate_project_data(self, project_id: str) -> dict[str, Any]:
        """Run the Priority 14 real-data validation gates for a persisted project."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return validate_project(project)

    def workflow_summary(self, project_id: str) -> dict[str, Any]:
        """Return the deterministic next-action workflow for the selected project."""
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return evaluate_workflow(project)

    def _model_registry(self, project_id: str) -> ModelRegistry:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return ModelRegistry(
            sources=[ModelSource(**x) for x in p.get("model_sources", [])],
            objects=[ModelObject(**x) for x in p.get("model_objects", [])],
        )

    def register_model_source(self, project_id: str, source: ModelSource) -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        registry = self._model_registry(project_id)
        registry.register_source(source)
        p["model_sources"] = [x.__dict__ for x in registry.sources]
        self.store.save(project_id, p)
        return dict(source.__dict__)

    def add_model_object(self, project_id: str, obj: ModelObject) -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        registry = self._model_registry(project_id)
        registry.add_object(obj)
        p["model_objects"] = [x.__dict__ for x in registry.objects]
        self.store.save(project_id, p)
        return dict(obj.__dict__)

    def project_model_inventory(self, project_id: str) -> dict[str, Any]:
        return self._model_registry(project_id).source_inventory()

    def project_model_revision_diff(self, project_id: str, old_revision: str, new_revision: str) -> dict[str, Any]:
        return self._model_registry(project_id).revision_diff(old_revision, new_revision)

    def project_model_takeoff_preview(self, project_id: str, *, mapping: dict[str, str] | None = None,
                                      source_id: str | None = None, require_mapping: bool = False) -> dict[str, Any]:
        """Convert BIM/CAD normalized objects to reviewable canonical takeoff rows."""
        return self._model_registry(project_id).to_takeoff_rows(
            mapping=mapping, source_id=source_id, require_mapping=require_mapping
        )

    def project_model_snapshot(self, project_id: str) -> dict[str, Any]:
        return self._model_registry(project_id).export_dict()

    def add_takeoff(self,project_id:str,domain:str,item:str,**params)->dict[str,Any]:
        # Multiple desktop windows may hold cached snapshots. Always reload the
        # latest committed project before checking identities and calculating BOQ.
        digest = self.store.current_digest(project_id)
        self.store._cache.pop(str(project_id), None)
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        source_id=str(params.pop("source_id","")).strip()
        description=str(params.pop("description","")).strip()
        system=str(params.pop("system","")).strip() or None
        if source_id and any(str(t.get("source_id","")).strip()==source_id for t in p.get("takeoffs",[])):
            raise ValueError(f"منبع متره تکراری و مستعد دوباره‌شماری: {source_id}")
        calculation_params = deepcopy(params)
        normalized_domain = takeoff_domain(domain)
        result=self.takeoff.calculate(normalized_domain,item,description=description or item,**calculation_params)
        row={"id":f"{len(p['takeoffs'])+1}","member_code":str(params.get("member_code",item)),
             "source_id":source_id,"domain":normalized_domain,"item":str(item),
             "params":calculation_params,"revision":1,
             "description":description or item,"system":system,
             "quantities":[{"code":item,"title":description or item,"system":system,"unit":result.unit,"amount":result.quantity,
             "formula":result.formula,"warning":result.warning,"price_code":params.get("price_code"),"unit_price":params.get("unit_price")}]}
        p["takeoffs"].append(row)
        p["boq"] = self._build_project_boq(p)
        self.store.save(project_id,p,expected_digest=digest); return row


    def save_drawing_takeoff_session(self, project_id: str, session_payload: dict[str, Any] | Any, *,
                                     session_id: str | None = None,
                                     expected_revision: int | None = None) -> dict[str, Any]:
        """Persist a validated graphical drawing session with optimistic revision checks."""
        pid = str(project_id or "").strip()
        if not pid:
            raise ValueError("شناسه پروژه الزامی است")
        payload = session_payload.to_dict() if hasattr(session_payload, "to_dict") else deepcopy(session_payload)
        report = validate_session_payload(payload)
        if not report["valid"]:
            raise ValueError("نشست متره ذخیره نشد: " + "؛ ".join(report["issues"]))
        sid = str(session_id or uuid4().hex).strip()
        if not sid:
            raise ValueError("شناسه نشست نقشه معتبر نیست")
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        sessions = project.setdefault("drawing_sessions", {})
        if not isinstance(sessions, dict):
            raise ValueError("ساختار نشست‌های نقشه در پروژه ناسازگار است")
        previous = sessions.get(sid)
        if previous is None:
            if expected_revision not in (None, 0):
                raise RuntimeError("نشست نقشه تغییر کرده یا وجود ندارد؛ نسخه را دوباره بخوانید")
            revision = 1
            committed = []
            ai_committed = []
        else:
            current_revision = int(previous.get("revision", 1))
            if expected_revision is None or int(expected_revision) != current_revision:
                raise RuntimeError(f"تعارض نسخه نشست نقشه؛ نسخه فعلی {current_revision} است")
            revision = current_revision + 1
            committed = list(previous.get("committed_item_ids", []))
            ai_committed = list(previous.get("ai_committed_item_ids", []))
        sessions[sid] = {
            "id": sid, "revision": revision, "drawing_source": str(payload.get("drawing_source", "")),
            "session": deepcopy(payload), "committed_item_ids": committed,
            "ai_committed_item_ids": ai_committed,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.store.save(pid, project, expected_digest=digest)
        return {"session_id": sid, "revision": revision, "item_count": len(payload.get("items", [])),
                "committed_item_ids": committed, "validation": report}

    def load_drawing_takeoff_session(self, project_id: str, session_id: str) -> dict[str, Any]:
        """Return a copy of a persisted drawing session; no caller can mutate stored state."""
        project = self.store.get(str(project_id or "").strip())
        if project is None:
            raise KeyError(project_id)
        record = (project.get("drawing_sessions", {}) or {}).get(str(session_id or "").strip())
        if not isinstance(record, dict):
            raise KeyError(f"نشست نقشه پیدا نشد: {session_id}")
        report = validate_session_payload(record.get("session", {}))
        if not report["valid"]:
            raise ValueError("نشست ذخیره‌شده نامعتبر است: " + "؛ ".join(report["issues"]))
        return deepcopy(record)

    def commit_drawing_takeoff_to_boq(self, project_id: str, session_id: str,
                                      selected_item_ids: list[str], *,
                                      expected_session_revision: int) -> dict[str, Any]:
        """Atomically persist explicitly selected drawing measurements into takeoffs and BOQ."""
        pid, sid = str(project_id or "").strip(), str(session_id or "").strip()
        if not pid or not sid:
            raise ValueError("شناسه پروژه و نشست نقشه الزامی هستند")
        if not selected_item_ids:
            raise ValueError("برای انتقال به BOQ باید متره‌ها را صریحاً انتخاب کنید")
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        sessions = project.get("drawing_sessions", {})
        record = sessions.get(sid) if isinstance(sessions, dict) else None
        if not isinstance(record, dict):
            raise KeyError(f"نشست نقشه پیدا نشد: {sid}")
        current_revision = int(record.get("revision", 1))
        if int(expected_session_revision) != current_revision:
            raise RuntimeError(f"تعارض نسخه نشست نقشه؛ نسخه فعلی {current_revision} است")
        selected = list(dict.fromkeys(str(x) for x in selected_item_ids))
        already = set(record.get("committed_item_ids", []))
        ai_already = set(record.get("ai_committed_item_ids", []))
        if already.intersection(selected) or ai_already.intersection(selected):
            raise ValueError("برخی متره‌های انتخاب‌شده قبلاً از مسیر دستی یا هوشمند وارد BOQ شده‌اند؛ انتقال تکراری رد شد")
        rows = session_to_boq_rows(record.get("session", {}), session_id=sid, selected_item_ids=selected)
        existing_sources = {str(row.get("source_id", "")).strip() for row in project.get("takeoffs", [])}
        duplicate_sources = [row["source_id"] for row in rows if row["source_id"] in existing_sources]
        if duplicate_sources:
            raise ValueError("منبع متره قبلاً ثبت شده است: " + "، ".join(duplicate_sources))
        new_takeoffs = []
        for row in rows:
            source_id = row["source_id"]
            new_takeoffs.append({
                "id": f"{len(project.get('takeoffs', [])) + len(new_takeoffs) + 1}",
                "member_code": row["item_code"], "source_id": source_id,
                "domain": "drawing", "item": row["kind"],
                "params": {"drawing_session_id": sid, "drawing_source": row["drawing_source"],
                           "page": row["page"], "geometry": row["geometry"],
                           "confidence": row["confidence"], "formula": row["formula"]},
                "revision": 1, "drawing_session_id": sid, "drawing_takeoff_id": row["takeoff_id"],
                "description": row["description"], "system": f"صفحه {row['page']}",
                "quantities": [{
                    "code": row["item_code"], "title": row["description"], "system": f"صفحه {row['page']}",
                    "unit": row["unit"], "amount": row["quantity"], "formula": row["formula"],
                    "warning": "", "price_code": row["price_code"], "unit_price": None,
                    "source_ref": row["source"], "page": row["page"],
                }],
            })
        project.setdefault("takeoffs", []).extend(new_takeoffs)
        project["boq"] = self._build_project_boq(project)
        record["committed_item_ids"] = sorted(already.union(selected))
        record["ai_committed_item_ids"] = sorted(ai_already)
        record["revision"] = current_revision + 1
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(pid, project, expected_digest=digest)
        return {"session_id": sid, "revision": record["revision"],
                "committed_item_ids": record["committed_item_ids"],
                "takeoffs_added": deepcopy(new_takeoffs), "boq_count": len(project["boq"])}

    def commit_ai_takeoff_proposal(self, project_id: str, proposal: dict[str, Any], *,
                                   user_confirmed: bool = False,
                                   minimum_confidence: float = 0.85) -> dict[str, Any]:
        """Persist AI-suggested quantities only after evidence, session revision and user confirmation pass."""
        pid = str(project_id or "").strip()
        if not pid:
            raise ValueError("شناسه پروژه الزامی است")
        report = validate_ai_takeoff_proposal(
            proposal, user_confirmed=user_confirmed, minimum_confidence=minimum_confidence
        )
        if not report["valid"]:
            raise ValueError("پیشنهاد هوش مصنوعی رد شد: " + "؛ ".join(report["issues"]))
        if not report["approved"]:
            raise PermissionError("پیشنهاد هوش مصنوعی هنوز تأیید صریح کاربر را ندارد")
        sid = str(proposal.get("drawing_id", "")).strip()
        try:
            expected_session_revision = int(proposal.get("revision_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("نسخه نشست نقشه در پیشنهاد معتبر نیست") from exc
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        record = (project.get("drawing_sessions", {}) or {}).get(sid)
        if not isinstance(record, dict):
            raise ValueError("نشست نقشه مرجع پیشنهاد در پروژه ذخیره نشده است")
        candidate_item_ids = {str(row.get("session_item_id", "")).strip() for row in report["rows"]}
        candidate_item_ids.discard("")
        committed_item_ids = set(record.get("committed_item_ids", [])) | set(record.get("ai_committed_item_ids", []))
        existing_item_ids = {
            str(row.get("drawing_takeoff_id") or (row.get("params") or {}).get("session_item_id") or "").strip()
            for row in project.get("takeoffs", [])
            if str(row.get("drawing_session_id", "")).strip() == sid
        }
        existing_item_ids.discard("")
        if candidate_item_ids.intersection(committed_item_ids | existing_item_ids):
            raise ValueError("یک یا چند متره هندسی قبلاً از مسیر دستی یا هوشمند ثبت شده است؛ دوباره‌شماری رد شد")
        if int(record.get("revision", 1)) != expected_session_revision:
            raise RuntimeError("نسخه نقشه/نشست با پیشنهاد هوش مصنوعی مطابقت ندارد؛ پیشنهاد را دوباره تولید کنید")
        from core.drawings.takeoff_session import DrawingTakeoffSession
        session = DrawingTakeoffSession.from_dict(record.get("session", {}))
        known_pages = {session.current_page, *session.calibrations.keys(), *[item.page for item in session.items]}
        existing_sources = {str(row.get("source_id", "")).strip() for row in project.get("takeoffs", [])}
        new_rows = []
        seen_session_items: set[str] = set()
        for candidate in report["rows"]:
            item_id = candidate["session_item_id"]
            if item_id in seen_session_items:
                raise ValueError("یک متره هندسی در همین پیشنهاد بیش از یک بار استفاده شده است")
            seen_session_items.add(item_id)
            page = candidate["page"]
            if page not in known_pages:
                raise ValueError(f"صفحه {page} در نشست نقشه مرجع وجود ندارد یا بازبینی نشده است")
            try:
                measured_item = session.find(candidate["session_item_id"])
            except KeyError as exc:
                raise ValueError("شناسه متره هندسی پیشنهاد در نشست ذخیره‌شده وجود ندارد") from exc
            if measured_item.page != page or measured_item.kind != candidate["kind"] or measured_item.unit != candidate["unit"]:
                raise ValueError("نوع، واحد یا صفحه پیشنهاد با متره هندسی ذخیره‌شده مطابقت ندارد")
            if not math.isclose(measured_item.quantity, candidate["quantity"], rel_tol=1e-9, abs_tol=1e-9):
                raise ValueError("مقدار پیشنهاد با مقدار هندسی محاسبه‌شده در نشست مطابقت ندارد")
            evidence = candidate["evidence"]
            source_ref = str(evidence.get("source_ref", "")).strip()
            if source_ref != measured_item.source_ref:
                raise ValueError("مرجع شواهد با مرجع متره هندسی ذخیره‌شده مطابقت ندارد")
            if candidate["kind"] in {"length", "area"}:
                calibration = session.calibrations.get(page)
                if calibration is None:
                    raise ValueError(f"صفحه {page} کالیبراسیون معتبر ندارد")
                try:
                    evidence_factor = float(evidence.get("meters_per_pixel"))
                except (TypeError, ValueError) as exc:
                    raise ValueError("شواهد کالیبراسیون فاقد ضریب مقیاس معتبر است") from exc
                if not math.isfinite(evidence_factor) or not math.isclose(
                    evidence_factor, calibration.meters_per_pixel, rel_tol=1e-9, abs_tol=1e-12
                ):
                    raise ValueError("ضریب مقیاس پیشنهاد با کالیبراسیون ذخیره‌شده مطابقت ندارد")
            source_id = f"ai-takeoff:{sid}:{expected_session_revision}:{candidate['source_id']}"
            if source_id in existing_sources:
                raise ValueError("پیشنهاد تکراری است و می‌تواند باعث دوباره‌شماری شود")
            existing_sources.add(source_id)
            title = candidate["label"]
            new_rows.append({
                "id": f"{len(project.get('takeoffs', [])) + len(new_rows) + 1}",
                "member_code": candidate["source_id"], "source_id": source_id,
                "domain": "drawing_ai", "item": candidate["kind"],
                "params": {"drawing_session_id": sid, "drawing_revision": expected_session_revision,
                           "session_item_id": candidate["session_item_id"],
                           "geometry": [list(point) for point in measured_item.geometry],
                           "evidence": deepcopy(candidate["evidence"]), "confidence": candidate["confidence"],
                           "formula": candidate["formula"]},
                "revision": 1, "drawing_session_id": sid, "ai_generated": True,
                "description": title, "system": f"صفحه {page}",
                "quantities": [{
                    "code": candidate["source_id"], "title": title, "system": f"صفحه {page}",
                    "unit": candidate["unit"], "amount": candidate["quantity"],
                    "formula": candidate["formula"], "warning": "پیشنهاد هوش مصنوعی با تأیید انسانی ثبت شده است",
                    "price_code": None, "unit_price": None, "source_ref": source_ref, "page": page,
                }],
            })
        if not new_rows:
            raise ValueError("پیشنهاد تأییدشده هیچ ردیف قابل ثبت ندارد")
        project.setdefault("takeoffs", []).extend(new_rows)
        project["boq"] = self._build_project_boq(project)
        record["ai_committed_item_ids"] = sorted(set(record.get("ai_committed_item_ids", [])) | seen_session_items)
        record["revision"] = expected_session_revision + 1
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(pid, project, expected_digest=digest)
        return {"approved": True, "takeoffs_added": deepcopy(new_rows), "boq_count": len(project["boq"]),
                "drawing_session_id": sid, "drawing_session_revision": record["revision"]}

    def add_assembly_takeoff(self, project_id: str, assembly_code: str, inputs: dict[str, Any], *,
                             floor_id: str, description: str = "", location_id: str = "") -> dict[str, Any]:
        """Persist a reviewed assembly with stable source/location identity."""
        pid = str(project_id).strip()
        floor = str(floor_id or "").strip()
        if not pid:
            raise ValueError("شناسه پروژه الزامی است")
        if not floor:
            raise ValueError("طبقه یا تراز باید صریح مشخص شود")
        # Read through SQLite rather than a cached in-memory snapshot. The
        # checksum will be enforced again by the transactional save below.
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        fixed_location = str(location_id or "").strip()
        assembly_key = str(assembly_code).strip()
        if assembly_key in _FINISH_ASSEMBLY_CODES:
            if not fixed_location:
                raise ValueError("شناسه ثابت محل برای متره نازک‌کاری الزامی است")
            if any(
                str(previous.get("assembly_code", "")) == assembly_key
                and str(previous.get("floor_id", "")).strip() == floor
                and str(previous.get("location_id", "")).strip() == fixed_location
                for previous in project.get("takeoff_assemblies", [])
            ):
                raise ValueError("متره تکراری برای همین نوع عملیات، طبقه و شناسه محل ثبت شده است")
        result = AssemblyTemplateLibrary().expand(assembly_code, inputs)
        if not result.complete:
            raise ValueError("ورودی‌های قالب کامل نیستند: " + "، ".join(result.missing_inputs))
        if not result.components:
            raise ValueError("قالب هیچ جزء قابل ثبتی تولید نکرد")
        for component in result.components:
            if not math.isfinite(float(component.quantity)) or float(component.quantity) < 0:
                raise ValueError(f"مقدار جزء {component.code} نامعتبر است")

        bundle_id = uuid4().hex
        created_at = datetime.now(timezone.utc).isoformat()
        parent = {
            "id": bundle_id, "assembly_code": result.code, "title": result.title,
            "description": str(description or result.title).strip(), "floor_id": floor,
            "location_id": fixed_location,
            "inputs": deepcopy(dict(inputs)), "inputs_used": list(result.inputs_used),
            "revision": 1, "created_at": created_at, "component_source_ids": [],
        }
        rows = []
        for component in result.components:
            component_role = _finish_component_role(result.code, component.code)
            source_id = f"assembly:{bundle_id}:{component.code}"
            if any(str(existing.get("source_id", "")).strip() == source_id
                   for existing in project.get("takeoffs", [])):
                raise ValueError(f"منبع جزء متره تکراری است: {source_id}")
            title = f"{parent['description']} — {component.title}"
            row = {
                "id": f"{len(project['takeoffs']) + 1}",
                "member_code": component.code, "source_id": source_id,
                "domain": "assembly", "item": component.code,
                "params": {"assembly_id": bundle_id, "assembly_code": result.code,
                           "component_code": component.code, "inputs": deepcopy(dict(inputs))},
                "revision": 1, "assembly_id": bundle_id,
                "component_role": component_role, "location_id": fixed_location,
                "description": title, "system": floor,
                "quantities": [{
                    "code": component.code, "title": title, "system": floor,
                    "role": component_role,
                    "unit": component.unit, "amount": float(component.quantity),
                    "formula": component.formula, "warning": component.warning,
                    "price_code": None, "unit_price": None,
                }],
            }
            project.setdefault("takeoffs", []).append(row)
            rows.append(row)
            parent["component_source_ids"].append(source_id)

        project.setdefault("takeoff_assemblies", []).append(parent)
        project["boq"] = self._build_project_boq(project)
        self.store.save(pid, project, expected_digest=digest)
        return {"assembly": parent, "rows": deepcopy(rows)}

    def revise_takeoff(self, project_id: str, source_id: str, *, expected_revision: int,
                       domain: str, item: str, description: str = "", system: str | None = None,
                       **params) -> dict[str, Any]:
        """Optimistically revise one persisted takeoff row and preserve its prior revision.

        The caller must supply the revision it edited. A stale revision is rejected;
        the project payload digest is also checked at save time to detect concurrent writes.
        """
        pid = str(project_id).strip()
        source = str(source_id or "").strip()
        if not pid or not source:
            raise ValueError("شناسه پروژه و منبع متره برای ویرایش الزامی هستند")
        try:
            expected = int(expected_revision)
        except (TypeError, ValueError) as exc:
            raise ValueError("شماره نسخه مورد انتظار معتبر نیست") from exc
        if expected < 1:
            raise ValueError("شماره نسخه مورد انتظار باید مثبت باشد")

        digest = self.store.current_digest(pid)
        # Force a fresh database read; never revise a stale in-memory project snapshot.
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        matches = [row for row in project.get("takeoffs", [])
                   if str(row.get("source_id", "")).strip() == source]
        if len(matches) != 1:
            raise KeyError(f"منبع متره باید دقیقاً یک ردیف داشته باشد: {source}")
        row = matches[0]
        current = int(row.get("revision", 1))
        if current != expected:
            raise RuntimeError(f"تعارض نسخه متره؛ نسخه فعلی {current} است و نسخه ارسالی {expected} بود.")

        normalized_domain = takeoff_domain(domain)
        calculation_params = deepcopy(params)
        clean_description = str(description or row.get("description") or item).strip()
        result = self.takeoff.calculate(normalized_domain, item, description=clean_description,
                                        **calculation_params)
        previous = deepcopy(row)
        changed_at = datetime.now(timezone.utc).isoformat()
        history = project.setdefault("takeoff_revision_history", [])
        history.append({
            "source_id": source, "from_revision": current, "to_revision": current + 1,
            "changed_at": changed_at, "previous_row": previous,
        })
        project["takeoff_revision_history"] = history[-500:]

        row.update({
            "domain": normalized_domain, "item": str(item), "params": calculation_params,
            "revision": current + 1, "revised_at": changed_at,
            "description": clean_description,
            "system": str(system).strip() if system is not None else row.get("system"),
            "quantities": [{
                "code": item, "title": clean_description, "system": system or row.get("system"),
                "unit": result.unit, "amount": result.quantity, "formula": result.formula,
                "warning": result.warning, "price_code": calculation_params.get("price_code"),
                "unit_price": calculation_params.get("unit_price"),
            }],
        })

        project["boq"] = self._build_project_boq(project)
        self.store.save(pid, project, expected_digest=digest)
        return deepcopy(row)

    def recalculate_estimate(self, project_id: str, *, factors: dict[str,float] | None = None) -> dict[str,Any]:
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        normalized_factors={str(k):float(v) for k,v in (factors or {}).items()}
        estimate=build_estimate(p.get("boq",[]), factors=normalized_factors, aggregate=False)
        # Keep the application service deterministic even if a downstream costing adapter is replaced.
        if normalized_factors:
            base=float(estimate["cost"].get("base",0) or 0)
            subtotal=base
            applied={}
            for name,rate in normalized_factors.items():
                delta=subtotal*rate
                applied[name]=delta
                subtotal+=delta
            estimate["cost"]["factors"]=applied
            estimate["cost"]["grand_total"]=subtotal
        p["estimate"]=estimate
        self.store.save(project_id,p)
        return estimate

    def build_commercial_snapshot(self, project_id: str, *, factors: dict[str,float] | None = None) -> dict[str,Any]:
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        estimate=self.recalculate_estimate(project_id,factors=factors)
        p=self.store.get(project_id) or p
        lines=[]
        for row in p.get("boq",[]):
            lines.append({
                "code":row.get("price_code",""),
                "contract_quantity":row.get("quantity",0),
                "previous_quantity":row.get("previous_quantity",0),
                "current_quantity":row.get("current_quantity",0),
                "unit_price":row.get("unit_price",0),
            })
        progress=build_progress(lines) if lines else {"lines":[],"contract_total":0,"current_total":0,"payable_current":0,"balance_current":0}
        return {"project_id":project_id,"estimate":estimate,"progress":progress,
                "boq_summary":boq_summary(p.get("boq",[]))}

    def build_statement(self, project_id: str, *, previous_paid: float = 0.0,
                        retention_rate: float = 0.0, advance_recovery_rate: float = 0.0,
                        tax_rate: float = 0.0, insurance_rate: float = 0.0) -> dict[str, Any]:
        """Build a period payment statement directly from the project's BOQ."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        if min(previous_paid, retention_rate, advance_recovery_rate, tax_rate, insurance_rate) < 0:
            raise ValueError("statement rates and previous payment cannot be negative")
        lines = []
        for row in p.get("boq", []):
            lines.append({
                "code": row.get("price_code", ""),
                "description": row.get("description", ""),
                "unit": row.get("unit", ""),
                "contract_quantity": row.get("quantity", 0),
                "unit_price": row.get("unit_price", 0),
                "previous_quantity": row.get("previous_quantity", 0),
                "current_quantity": row.get("current_quantity", 0),
            })
        progress = build_progress(lines) if lines else {
            "lines": [], "contract_total": 0, "completed_total": 0, "current_total": 0,
            "gross_current": 0, "deductions": 0, "payable_current": 0,
            "payments": 0, "balance_current": 0, "remaining_contract": 0, "progress_percent": 0,
        }
        gross = float(progress.get("gross_current", 0) or 0)
        retention = gross * float(retention_rate)
        advance = gross * float(advance_recovery_rate)
        taxable = max(gross - retention - advance, 0.0)
        tax = taxable * float(tax_rate)
        insurance = taxable * float(insurance_rate)
        payable = max(taxable + tax - insurance, 0.0)
        return {
            **progress,
            "retention": retention,
            "advance_recovery": advance,
            "taxable_current": taxable,
            "tax": tax,
            "insurance": insurance,
            "payable_current": payable,
            "previous_paid": float(previous_paid),
            "balance_after_current": payable - float(previous_paid),
            "rates": {
                "retention_rate": float(retention_rate),
                "advance_recovery_rate": float(advance_recovery_rate),
                "tax_rate": float(tax_rate),
                "insurance_rate": float(insurance_rate),
            },
        }

    def save_statement_period(self, project_id: str, *, period_no: int | None = None,
                              current_quantities: dict[str, float] | None = None,
                              retention_rate: float = 0.0, advance_recovery_rate: float = 0.0,
                              tax_rate: float = 0.0, insurance_rate: float = 0.0) -> dict[str, Any]:
        """Persist a numbered statement period and roll its quantities into the next period."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        periods = list(p.get("statement_periods", []))
        if period_no is None:
            period_no = (max((int(x.get("number", 0)) for x in periods), default=0) + 1)
        period_no = int(period_no)
        if period_no <= 0 or any(int(x.get("number", 0)) == period_no for x in periods):
            raise ValueError("statement period number must be positive and unique")
        previous = {}
        if periods:
            previous = {
                str(x.get("code", "")): float(x.get("cumulative_quantity", 0) or 0)
                for x in periods[-1].get("lines", [])
            }
        overrides = {str(k): float(v) for k, v in (current_quantities or {}).items()}
        lines = []
        for row in p.get("boq", []):
            code = str(row.get("price_code", "") or "")
            cur = float(overrides.get(code, row.get("current_quantity", 0)) or 0)
            prev = float(previous.get(code, row.get("previous_quantity", 0)) or 0)
            if cur < 0 or prev < 0:
                raise ValueError("statement quantities cannot be negative")
            lines.append({
                "code": code, "description": row.get("description", ""), "unit": row.get("unit", ""),
                "contract_quantity": float(row.get("quantity", 0) or 0),
                "unit_price": float(row.get("unit_price", 0) or 0),
                "previous_quantity": prev, "current_quantity": cur,
            })
        progress = build_progress(lines)
        period = {
            "number": period_no,
            "lines": progress["lines"],
            "gross_current": progress["gross_current"],
            "completed_total": progress["completed_total"],
            "remaining_contract": progress["remaining_contract"],
            "progress_percent": progress["progress_percent"],
            "rates": {
                "retention_rate": float(retention_rate), "advance_recovery_rate": float(advance_recovery_rate),
                "tax_rate": float(tax_rate), "insurance_rate": float(insurance_rate),
            },
        }
        gross = float(period["gross_current"])
        retention = gross * float(retention_rate)
        advance = gross * float(advance_recovery_rate)
        taxable = max(gross - retention - advance, 0.0)
        tax = taxable * float(tax_rate)
        insurance = taxable * float(insurance_rate)
        period.update({
            "retention": retention, "advance_recovery": advance, "taxable_current": taxable,
            "tax": tax, "insurance": insurance, "payable_current": max(taxable + tax - insurance, 0.0),
        })
        periods.append(period)
        p["statement_periods"] = periods
        self.store.save(project_id, p)
        return period

    def statement_periods(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("statement_periods", []))

    def project_financial_document_status_summary(self, project_id: str) -> dict[str, Any]:
        """Summarize registered and calculated payment statuses without mutating documents."""
        audit = self.project_financial_reconciliation(project_id)
        counts = {"unpaid": 0, "partial": 0, "paid": 0}
        amounts = {"unpaid": 0.0, "partial": 0.0, "paid": 0.0}
        for row in audit["rows"]:
            status = row["derived_status"]
            if row["linkage_state"] == "بدون اتصال":
                status = row["manual_status"] if row["manual_status"] in counts else "unpaid"
            counts[status] += 1
            amounts[status] += float(row["amount"])
        return {"project_id": project_id, "counts": counts, "amounts": amounts,
                "document_count": audit["document_count"], "mismatch_count": audit["mismatch_count"]}

    def add_project_financial_document(self, project_id: str, document_number: str, document_type: str, amount: float, *, counterparty: str = "", date: str = "", due_date: str = "", reference: str = "", notes: str = "", payment_status: str = "unpaid", commitment_id: int | None = None, cost_entry_id: int | None = None, receipt_id: int | None = None) -> dict[str, Any]:
        """Persist a project financial invoice/document and optionally link it to a ledger entry."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        document_number = str(document_number).strip()
        document_type = str(document_type).strip()
        payment_status = str(payment_status).strip().lower()
        amount = float(amount)
        if not document_number:
            raise ValueError("document number cannot be empty")
        if not document_type:
            raise ValueError("document type cannot be empty")
        if amount < 0:
            raise ValueError("document amount cannot be negative")
        if payment_status not in {"unpaid", "partial", "paid"}:
            raise ValueError("invalid payment status")
        documents = list(p.get("financial_documents", []))
        if any(str(x.get("document_number", "")) == document_number for x in documents):
            raise ValueError("document number must be unique within the project")
        def _exists(collection: str, entry_id: int | None) -> bool:
            return entry_id is None or any(int(x.get("id", 0)) == int(entry_id) for x in p.get(collection, []))
        if not _exists("commitment_entries", commitment_id):
            raise KeyError(f"commitment {commitment_id}")
        if not _exists("cost_entries", cost_entry_id):
            raise KeyError(f"cost entry {cost_entry_id}")
        if not _exists("receipt_entries", receipt_id):
            raise KeyError(f"receipt {receipt_id}")
        entry = {
            "id": len(documents) + 1,
            "document_number": document_number,
            "document_type": document_type,
            "counterparty": str(counterparty).strip(),
            "counterparty_id": self._counterparty_id_for_name(p, counterparty),
            "amount": amount,
            "date": str(date).strip(),
            "due_date": str(due_date).strip(),
            "reference": str(reference).strip(),
            "notes": str(notes).strip(),
            "payment_status": payment_status,
            "commitment_id": int(commitment_id) if commitment_id is not None else None,
            "cost_entry_id": int(cost_entry_id) if cost_entry_id is not None else None,
            "receipt_id": int(receipt_id) if receipt_id is not None else None,
        }
        documents.append(entry)
        p["financial_documents"] = documents
        self.store.save(project_id, p)
        return entry

    def project_financial_documents(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("financial_documents", []))


    def project_financial_documents_by_status(self, project_id: str, status: str) -> list[dict[str, Any]]:
        """Filter financial documents by normalized payment status."""
        status = str(status).strip().lower()
        if status not in {"unpaid", "partial", "paid"}:
            raise ValueError("invalid payment status")
        return [x for x in self.project_financial_documents(project_id)
                if str(x.get("payment_status", "unpaid")).strip().lower() == status]

    def project_financial_documents_by_counterparty(self, project_id: str, counterparty_id: str) -> list[dict[str, Any]]:
        """Filter financial documents by stable counterparty ID."""
        party = self.find_project_counterparty_by_id(project_id, counterparty_id)
        if party is None:
            raise KeyError(counterparty_id)
        return [x for x in self.project_financial_documents(project_id)
                if x.get("counterparty_id") == counterparty_id
                or self._counterparty_id_for_name(self.store.get(project_id), x.get("counterparty", "")) == counterparty_id]

    def project_counterparty_exposure(self, project_id: str, counterparty_id: str) -> dict[str, Any]:
        """Calculate a focused exposure snapshot for one counterparty."""
        party = self.find_project_counterparty_by_id(project_id, counterparty_id)
        if party is None:
            raise KeyError(counterparty_id)
        row = next((x for x in self.project_counterparty_financial_rollup(project_id)
                    if x["counterparty_id"] == counterparty_id), None)
        row = row or {"counterparty_id": counterparty_id, "name": party["name"],
                      "commitment_amount": 0.0, "paid_commitments": 0.0,
                      "cost_amount": 0.0, "receipt_amount": 0.0, "document_amount": 0.0}
        return {
            **row,
            "unpaid_commitments": max(float(row["commitment_amount"]) - float(row["paid_commitments"]), 0.0),
            "net_cash": float(row["receipt_amount"]) - float(row["paid_commitments"]),
        }

    def project_financial_document_status_matrix(self, project_id: str) -> dict[str, Any]:
        """Return count and amount matrix for registered and calculated document status."""
        audit = self.project_financial_reconciliation(project_id)
        matrix = {s: {"count": 0, "amount": 0.0} for s in ("unpaid", "partial", "paid")}
        mismatches = 0
        for row in audit["rows"]:
            status = row["derived_status"]
            matrix[status]["count"] += 1
            matrix[status]["amount"] += float(row["amount"])
            mismatches += not row["status_match"]
        return {"project_id": project_id, "matrix": matrix, "mismatch_count": mismatches}

    def project_financial_integrity_audit(self, project_id: str) -> dict[str, Any]:
        """Detect broken references, invalid amounts and malformed financial rows."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        issues = []
        for collection, label in (("commitment_entries", "تعهد"), ("cost_entries", "هزینه"), ("receipt_entries", "دریافتی")):
            for item in p.get(collection, []):
                try:
                    amount = float(item.get("amount", 0) or 0)
                    if amount < 0: issues.append({"type": "negative_amount", "source": label, "id": item.get("id", "")})
                except (TypeError, ValueError):
                    issues.append({"type": "invalid_amount", "source": label, "id": item.get("id", "")})
        valid_ids = {
            "commitment_id": {int(x.get("id", 0)) for x in p.get("commitment_entries", [])},
            "cost_entry_id": {int(x.get("id", 0)) for x in p.get("cost_entries", [])},
            "receipt_id": {int(x.get("id", 0)) for x in p.get("receipt_entries", [])},
        }
        for doc in p.get("financial_documents", []):
            for key, ids in valid_ids.items():
                value = doc.get(key)
                if value is not None:
                    try:
                        if int(value) not in ids:
                            issues.append({"type": "broken_reference", "source": "سند مالی", "id": doc.get("id", ""), "field": key})
                    except (TypeError, ValueError):
                        issues.append({"type": "invalid_reference", "source": "سند مالی", "id": doc.get("id", ""), "field": key})
            if float(doc.get("amount", 0) or 0) < 0:
                issues.append({"type": "negative_amount", "source": "سند مالی", "id": doc.get("id", "")})
        return {"project_id": project_id, "issue_count": len(issues), "issues": issues, "healthy": not issues}

    def project_statement_summary(self, project_id: str) -> dict[str, Any]:
        """Summarize persisted statement periods."""
        periods = self.statement_periods(project_id)
        return {
            "project_id": project_id,
            "period_count": len(periods),
            "latest_period": periods[-1] if periods else None,
            "gross_total": sum(float(x.get("gross_current", 0) or 0) for x in periods),
            "payable_total": sum(float(x.get("payable_current", 0) or 0) for x in periods),
            "retention_total": sum(float(x.get("retention", 0) or 0) for x in periods),
            "tax_total": sum(float(x.get("tax", 0) or 0) for x in periods),
        }
