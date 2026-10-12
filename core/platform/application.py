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

class StructuralProApp:
    def __init__(self,data_dir: str|Path):
        self.data_dir=Path(data_dir); self.data_dir.mkdir(parents=True,exist_ok=True)
        self.store=ProjectStore(self.data_dir/"projects.db")
        self.takeoff=TakeoffEngine()
        self.qa=ProjectQA()
        self.ai_assistant = EngineeringAssistant()
        self.engineering = EngineeringLibrary()

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
        boq_inputs=[]
        for takeoff in p["takeoffs"]:
            for q in takeoff.get("quantities",[]):
                boq_inputs.append({
                    "source": takeoff.get("source_id","") or "manual",
                    "source_id": takeoff.get("source_id",""),
                    "source_type": "takeoff",
                    "description": q.get("title",""),
                    "quantity": q.get("amount",0),
                    "unit": q.get("unit",""),
                    "item_code": q.get("code", item),
                    "price_code": q.get("price_code"),
                    "unit_price": q.get("unit_price"),
                    "category": domain,
                    "group": domain,
                })
        p["boq"]=build_boq(boq_inputs)
        self.store.save(project_id,p); return row


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
        boq_inputs = []
        for takeoff in project.get("takeoffs", []):
            for quantity in takeoff.get("quantities", []):
                boq_inputs.append({
                    "source": takeoff.get("source_id", "") or "manual",
                    "source_id": takeoff.get("source_id", ""), "source_type": "takeoff",
                    "description": quantity.get("title", ""), "quantity": quantity.get("amount", 0),
                    "unit": quantity.get("unit", ""), "item_code": quantity.get("code", ""),
                    "price_code": quantity.get("price_code"), "unit_price": quantity.get("unit_price"),
                    "category": takeoff.get("domain", "manual"), "group": takeoff.get("domain", "manual"),
                })
        project["boq"] = build_boq(boq_inputs)
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
        boq_inputs = []
        for takeoff in project.get("takeoffs", []):
            for quantity in takeoff.get("quantities", []):
                boq_inputs.append({
                    "source": takeoff.get("source_id", "") or "manual",
                    "source_id": takeoff.get("source_id", ""), "source_type": "takeoff",
                    "description": quantity.get("title", ""), "quantity": quantity.get("amount", 0),
                    "unit": quantity.get("unit", ""), "item_code": quantity.get("code", ""),
                    "price_code": quantity.get("price_code"), "unit_price": quantity.get("unit_price"),
                    "category": takeoff.get("domain", "manual"), "group": takeoff.get("domain", "manual"),
                })
        project["boq"] = build_boq(boq_inputs)
        record["ai_committed_item_ids"] = sorted(set(record.get("ai_committed_item_ids", [])) | seen_session_items)
        record["revision"] = expected_session_revision + 1
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(pid, project, expected_digest=digest)
        return {"approved": True, "takeoffs_added": deepcopy(new_rows), "boq_count": len(project["boq"]),
                "drawing_session_id": sid, "drawing_session_revision": record["revision"]}

    def add_assembly_takeoff(self, project_id: str, assembly_code: str, inputs: dict[str, Any], *,
                             floor_id: str, description: str = "") -> dict[str, Any]:
        """Calculate and persist every verified component of an explicit-input assembly to the BOQ."""
        pid = str(project_id).strip()
        floor = str(floor_id or "").strip()
        if not pid:
            raise ValueError("شناسه پروژه الزامی است")
        if not floor:
            raise ValueError("طبقه یا تراز باید صریح مشخص شود")
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
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
            "inputs": deepcopy(dict(inputs)), "inputs_used": list(result.inputs_used),
            "revision": 1, "created_at": created_at, "component_source_ids": [],
        }
        rows = []
        for component in result.components:
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
                "description": title, "system": floor,
                "quantities": [{
                    "code": component.code, "title": title, "system": floor,
                    "unit": component.unit, "amount": float(component.quantity),
                    "formula": component.formula, "warning": component.warning,
                    "price_code": None, "unit_price": None,
                }],
            }
            project.setdefault("takeoffs", []).append(row)
            rows.append(row)
            parent["component_source_ids"].append(source_id)

        project.setdefault("takeoff_assemblies", []).append(parent)
        boq_inputs = []
        for takeoff in project.get("takeoffs", []):
            for quantity in takeoff.get("quantities", []):
                boq_inputs.append({
                    "source": takeoff.get("source_id", "") or "manual",
                    "source_id": takeoff.get("source_id", ""),
                    "source_type": "takeoff", "description": quantity.get("title", ""),
                    "quantity": quantity.get("amount", 0), "unit": quantity.get("unit", ""),
                    "item_code": quantity.get("code", ""), "price_code": quantity.get("price_code"),
                    "unit_price": quantity.get("unit_price"), "category": takeoff.get("domain", "assembly"),
                    "group": takeoff.get("domain", "assembly"),
                })
        project["boq"] = build_boq(boq_inputs)
        self.store.save(pid, project)
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

        boq_inputs = []
        for takeoff in project.get("takeoffs", []):
            for quantity in takeoff.get("quantities", []):
                boq_inputs.append({
                    "source": takeoff.get("source_id", "") or "manual",
                    "source_id": takeoff.get("source_id", ""),
                    "source_type": "takeoff", "description": quantity.get("title", ""),
                    "quantity": quantity.get("amount", 0), "unit": quantity.get("unit", ""),
                    "item_code": quantity.get("code", item), "price_code": quantity.get("price_code"),
                    "unit_price": quantity.get("unit_price"), "category": takeoff.get("domain", "manual"),
                    "group": takeoff.get("domain", "manual"),
                })
        project["boq"] = build_boq(boq_inputs)
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

    def project_statement_period(self, project_id: str, period_no: int) -> dict[str, Any]:
        """Return one persisted statement period by number."""
        period_no = int(period_no)
        return next((x for x in self.statement_periods(project_id) if int(x.get("number", 0)) == period_no), None) or (_ for _ in ()).throw(KeyError(period_no))

    def project_management_snapshot(self, project_id: str, *, as_of: str | None = None) -> dict[str, Any]:
        """Return a read-only operational management dashboard for a project."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        def _load(cls, key):
            return [cls(**row) for row in p.get(key, [])]
        manager = ProjectManagement(
            tasks=_load(ScheduleTask, "project_schedule_tasks"),
            daily_reports=_load(DailyReport, "project_daily_reports"),
            resources=_load(ResourceRecord, "project_resources"),
            materials=_load(MaterialRecord, "project_materials"),
            meetings=_load(MeetingRecord, "project_meetings"),
        )
        return {"project_id": project_id, "dashboard": manager.dashboard(as_of=as_of),
                "actual_vs_plan": manager.actual_vs_plan(), "export": manager.export_dict()}

    def save_project_management(self, project_id: str, management: ProjectManagement) -> dict[str, Any]:
        """Persist a validated management snapshot without changing legacy project fields."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        management.validate()
        exported = management.export_dict()
        p.update({
            "project_schedule_tasks": exported["tasks"],
            "project_daily_reports": exported["daily_reports"],
            "project_resources": exported["resources"],
            "project_materials": exported["materials"],
            "project_meetings": exported["meetings"],
        })
        self.store.save(project_id, p)
        return self.project_management_snapshot(project_id)

    def project_activity_summary(self, project_id: str) -> dict[str, Any]:
        """Provide a compact project activity inventory for dashboards."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return {
            "project_id": project_id,
            "takeoffs": len(p.get("takeoffs", [])),
            "boq_items": len(p.get("boq", [])),
            "statement_periods": len(p.get("statement_periods", [])),
            "documents": len(p.get("financial_documents", [])),
            "commitments": len(p.get("commitment_entries", [])),
            "costs": len(p.get("cost_entries", [])),
            "receipts": len(p.get("receipt_entries", [])),
            "counterparties": len(p.get("counterparties", [])),
        }

    def project_financial_control_snapshot(self, project_id: str, as_of: str = "") -> dict[str, Any]:
        """One read-only snapshot for financial control screens."""
        kpi = self.project_financial_kpi_summary(project_id, as_of)
        return {
            "project_id": project_id,
            "kpi": kpi,
            "documents": self.project_financial_document_status_matrix(project_id),
            "integrity": self.project_financial_integrity_audit(project_id),
            "counterparties": self.project_counterparty_financial_rollup(project_id),
        }

    def project_statement_report(self, project_id: str, fmt: str, path):
        """Export persisted statement-period summary."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        summary = self.project_statement_summary(project_id)
        rows = [{
            "دوره": x.get("number", ""), "کارکرد ناخالص": x.get("gross_current", 0),
            "کسورات نگهداری": x.get("retention", 0), "علی‌الحساب": x.get("advance_recovery", 0),
            "مالیات": x.get("tax", 0), "بیمه": x.get("insurance", 0),
            "قابل پرداخت": x.get("payable_current", 0), "پیشرفت": x.get("progress_percent", 0),
        } for x in self.statement_periods(project_id)]
        return build_report(f'{p.get("name", "")} — خلاصه صورت‌وضعیت‌ها', rows, summary).export(path, fmt)

    def project_financial_control_report(self, project_id: str, as_of: str, fmt: str, path):
        """Export one consolidated financial-control snapshot."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        snap = self.project_financial_control_snapshot(project_id, as_of)
        rows = []
        for x in snap["counterparties"]:
            rows.append({
                "طرف حساب": x["name"], "شناسه": x["counterparty_id"],
                "اسناد": x["documents"], "تعهدات": x["commitments"],
                "مبلغ تعهدات": x["commitment_amount"], "پرداخت تعهدات": x["paid_commitments"],
                "هزینه": x["cost_amount"], "دریافتی": x["receipt_amount"],
            })
        return build_report(f'{p.get("name", "")} — کنترل مالی یکپارچه', rows, snap).export(path, fmt)

    def project_financial_document_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_financial_documents(project_id)
        by_status = {"unpaid": 0.0, "partial": 0.0, "paid": 0.0}
        by_type: dict[str, float] = {}
        for entry in entries:
            amount = float(entry.get("amount", 0) or 0)
            status = str(entry.get("payment_status", "unpaid"))
            by_status[status] = by_status.get(status, 0.0) + amount
            dtype = str(entry.get("document_type", "سایر"))
            by_type[dtype] = by_type.get(dtype, 0.0) + amount
        return {
            "project_id": project_id,
            "document_count": len(entries),
            "document_total": sum(float(x.get("amount", 0) or 0) for x in entries),
            "by_payment_status": by_status,
            "by_type": by_type,
        }

    def project_financial_reconciliation(self, project_id: str) -> dict[str, Any]:
        """Audit financial-document links against linked settlement records without mutating data."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        commitments = {int(x.get("id", 0)): x for x in p.get("commitment_entries", [])}
        costs = {int(x.get("id", 0)): x for x in p.get("cost_entries", [])}
        receipts = {int(x.get("id", 0)): x for x in p.get("receipt_entries", [])}
        rows = []
        for doc in p.get("financial_documents", []):
            amount = float(doc.get("amount", 0) or 0)
            commitment = commitments.get(int(doc["commitment_id"])) if doc.get("commitment_id") is not None else None
            cost = costs.get(int(doc["cost_entry_id"])) if doc.get("cost_entry_id") is not None else None
            receipt = receipts.get(int(doc["receipt_id"])) if doc.get("receipt_id") is not None else None
            commitment_paid = float(commitment.get("paid_amount", 0) or 0) if commitment else 0.0
            receipt_amount = float(receipt.get("amount", 0) or 0) if receipt else 0.0
            settlement_amount = max(commitment_paid, receipt_amount)
            if settlement_amount <= 0:
                derived_status = "unpaid"
            elif settlement_amount >= amount:
                derived_status = "paid"
            else:
                derived_status = "partial"
            manual_status = str(doc.get("payment_status", "unpaid")).strip().lower()
            rows.append({
                "document_id": doc.get("id", ""),
                "document_number": doc.get("document_number", ""),
                "amount": amount,
                "manual_status": manual_status,
                "derived_status": derived_status,
                "status_match": manual_status == derived_status,
                "commitment_id": doc.get("commitment_id"),
                "commitment_paid": commitment_paid,
                "cost_entry_id": doc.get("cost_entry_id"),
                "cost_amount": float(cost.get("amount", 0) or 0) if cost else 0.0,
                "receipt_id": doc.get("receipt_id"),
                "receipt_amount": receipt_amount,
                "settlement_amount": settlement_amount,
                "multiple_settlement_links": bool(commitment and receipt),
                "linkage_state": "متصل" if any((commitment, cost, receipt)) else "بدون اتصال",
            })
        mismatches = [x for x in rows if not x["status_match"]]
        return {
            "project_id": project_id,
            "rows": rows,
            "document_count": len(rows),
            "matched_count": len(rows) - len(mismatches),
            "mismatch_count": len(mismatches),
            "unlinked_count": sum(1 for x in rows if x["linkage_state"] == "بدون اتصال"),
            "multiple_settlement_count": sum(1 for x in rows if x["multiple_settlement_links"]),
        }

    def project_financial_reconciliation_rows(self, project_id: str) -> list[dict[str, Any]]:
        """Return normalized reconciliation rows for UI grids and integrations."""
        return list(self.project_financial_reconciliation(project_id)["rows"])

    def project_counterparty_financial_rollup_report(self, project_id: str, fmt: str, path):
        """Export stable-ID counterparty financial rollup."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        rollup = self.project_counterparty_financial_rollup(project_id)
        rows = [{
            "شناسه": x["counterparty_id"], "طرف حساب": x["name"], "نقش": x["role"],
            "وضعیت": "فعال" if x["active"] else "غیرفعال",
            "اسناد": x["documents"], "مبلغ اسناد": x["document_amount"],
            "تعهدات": x["commitments"], "مبلغ تعهدات": x["commitment_amount"],
            "پرداخت تعهدات": x["paid_commitments"], "هزینه‌ها": x["costs"],
            "مبلغ هزینه": x["cost_amount"], "دریافتی": x["receipts"],
            "مبلغ دریافتی": x["receipt_amount"],
        } for x in rollup]
        summary = {"project_id": project_id, "counterparty_count": len(rollup), "rows": rollup}
        return build_report(f'{p.get("name", "")} — رول‌آپ مالی طرف حساب‌ها', rows, summary).export(path, fmt)

    def project_financial_audit_summary(self, project_id: str) -> dict[str, Any]:
        """Combine document reconciliation controls into one audit snapshot."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        documents = self.project_financial_document_status_summary(project_id)
        reconciliation = self.project_financial_reconciliation(project_id)
        return {
            "project_id": project_id,
            "document_count": documents["document_count"],
            "status_mismatch_count": documents["mismatch_count"],
            "matched_count": reconciliation["matched_count"],
            "unlinked_count": reconciliation["unlinked_count"],
            "multiple_settlement_count": reconciliation["multiple_settlement_count"],
            "paid_documents": documents["counts"]["paid"],
            "partial_documents": documents["counts"]["partial"],
            "unpaid_documents": documents["counts"]["unpaid"],
        }

    def project_financial_reconciliation_report(self, project_id: str, fmt: str, path):
        """Export the financial-document reconciliation audit."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        reconciliation = self.project_financial_reconciliation(project_id)
        rows = [{
            "شناسه سند": x["document_id"], "شماره سند": x["document_number"], "مبلغ سند": x["amount"],
            "وضعیت ثبت‌شده": x["manual_status"], "وضعیت محاسباتی": x["derived_status"],
            "تطبیق": "تطبیق دارد" if x["status_match"] else "نیازمند بررسی",
            "تعهد": x["commitment_id"] or "", "پرداخت تعهد": x["commitment_paid"],
            "هزینه": x["cost_entry_id"] or "", "مبلغ هزینه": x["cost_amount"],
            "دریافتی": x["receipt_id"] or "", "مبلغ دریافتی": x["receipt_amount"],
            "مبلغ تسویه محاسباتی": x["settlement_amount"], "وضعیت اتصال": x["linkage_state"],
        } for x in reconciliation["rows"]]
        return build_report(f'{p.get("name", "")} — کنترل تطبیق اسناد مالی', rows, reconciliation).export(path, fmt)

    def add_project_cost(self, project_id: str, category: str, amount: float, *, description: str = "", date: str = "", document_id: int | None = None, counterparty: str = "") -> dict[str, Any]:
        """Persist an actual project cost entry for financial control."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        amount = float(amount)
        if amount < 0:
            raise ValueError("cost amount cannot be negative")
        categories = {"مصالح", "دستمزد", "پیمانکار", "تجهیزات", "سایر"}
        category = str(category).strip()
        if category not in categories:
            raise ValueError(f"unsupported cost category: {category}")
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        entries = list(p.get("cost_entries", []))
        entry = {
            "id": len(entries) + 1,
            "category": category,
            "amount": amount,
            "description": str(description).strip(),
            "date": str(date).strip(),
            "counterparty": str(counterparty).strip(),
            "counterparty_id": self._counterparty_id_for_name(p, counterparty),
            "document_id": int(document_id) if document_id is not None else None,
        }
        entries.append(entry)
        p["cost_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def project_costs(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("cost_entries", []))

    def project_cost_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_costs(project_id)
        by_category = {}
        for entry in entries:
            category = str(entry.get("category", "سایر"))
            by_category[category] = by_category.get(category, 0.0) + float(entry.get("amount", 0) or 0)
        return {
            "project_id": project_id,
            "entry_count": len(entries),
            "actual_cost": sum(by_category.values()),
            "by_category": by_category,
        }

    def project_financial_control(self, project_id: str, *, planned_cost: float | None = None,
                                  actual_cost: float = 0.0) -> dict[str, Any]:
        """Calculate cost variance indicators from explicit project cost inputs."""
        if actual_cost < 0 or (planned_cost is not None and planned_cost < 0):
            raise ValueError("cost values cannot be negative")
        dashboard = self.financial_dashboard(project_id)
        contract = float(dashboard["contract_amount"])
        work = float(dashboard["cumulative_work"])
        planned = contract if planned_cost is None else float(planned_cost)
        ledger_actual = float(self.project_cost_summary(project_id)["actual_cost"])
        actual = ledger_actual if actual_cost == 0 else float(actual_cost)
        earned = work
        cost_variance = earned - actual
        schedule_variance = earned - (planned * dashboard["progress_percent"] / 100.0 if planned else 0.0)
        cost_ratio = (earned / actual) if actual > 0 else None
        budget_ratio = (earned / planned) if planned > 0 else None
        return {
            "project_id": project_id,
            "contract_amount": contract,
            "planned_cost": planned,
            "actual_cost": actual,
            "earned_value": earned,
            "cost_variance": cost_variance,
            "schedule_variance": schedule_variance,
            "cost_performance_index": cost_ratio,
            "budget_progress_ratio": budget_ratio,
            "progress_percent": dashboard["progress_percent"],
        }

    def financial_dashboard(self, project_id: str) -> dict[str, Any]:
        """Return a compact financial/progress snapshot for the project dashboard."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        estimate = p.get("estimate") or self.recalculate_estimate(project_id)
        cost = estimate.get("cost", {}) or {}
        boq = p.get("boq", []) or []
        contract = float(cost.get("grand_total", 0) or 0)
        base = float(cost.get("base", 0) or 0)
        snapshot = self.build_commercial_snapshot(project_id)
        progress = snapshot.get("progress", {}) or {}
        periods = list(p.get("statement_periods", []))
        latest = periods[-1] if periods else None
        cumulative = float(progress.get("completed_total", 0) or 0)
        if latest is not None:
            cumulative = float(latest.get("completed_total", cumulative) or cumulative)
        remaining = max(contract - cumulative, 0.0)
        percent = (cumulative / contract * 100.0) if contract else 0.0
        total_payable = sum(float(x.get("payable_current", 0) or 0) for x in periods)
        cost_summary = self.project_cost_summary(project_id)
        actual_cost = float(cost_summary["actual_cost"])
        gross_margin = cumulative - actual_cost
        return {
            "project_id": project_id,
            "project_name": p.get("name", ""),
            "line_count": len(boq),
            "contract_amount": contract,
            "base_amount": base,
            "cumulative_work": cumulative,
            "remaining_contract": remaining,
            "progress_percent": percent,
            "statement_count": len(periods),
            "latest_statement_no": latest.get("number") if latest else None,
            "latest_payable": float(latest.get("payable_current", 0) or 0) if latest else 0.0,
            "total_payable": total_payable,
            "actual_cost": actual_cost,
            "gross_margin": gross_margin,
            "cost_entry_count": cost_summary["entry_count"],
            "cost_by_category": cost_summary["by_category"],
            "warnings": list((estimate.get("warnings") or [])),
        }

    def _finance_depth_control(self, project_id: str) -> FinancePaymentControl:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        payments = [
            PaymentRecord(
                id=str(x.get("id")),
                amount=float(x.get("amount", 0) or 0),
                date=str(x.get("date", "")),
                reference=str(x.get("reference", "")),
                document_id=int(x["document_id"]) if x.get("document_id") is not None else None,
                commitment_id=int(x["commitment_id"]) if x.get("commitment_id") is not None else None,
                counterparty_id=x.get("counterparty_id"),
                notes=str(x.get("notes", "")),
                status=str(x.get("status", "unallocated")),
            )
            for x in p.get("payment_entries", [])
        ]
        allocations = [
            PaymentAllocation(
                id=str(x.get("id")),
                payment_id=str(x.get("payment_id")),
                target_type=str(x.get("target_type")),
                target_id=x.get("target_id"),
                amount=float(x.get("amount", 0) or 0),
            )
            for x in p.get("payment_allocations", [])
        ]
        budget = [
            BudgetLine(
                code=str(x.get("code")),
                category=str(x.get("category", "")),
                description=str(x.get("description", "")),
                planned=float(x.get("planned", 0) or 0),
            )
            for x in p.get("financial_budget", [])
        ]
        return FinancePaymentControl(payments=payments, allocations=allocations, budget=budget)

    def add_project_payment(self, project_id: str, amount: float, *, date: str = "",
                            reference: str = "", document_id: int | None = None,
                            commitment_id: int | None = None, counterparty_id: str | None = None,
                            notes: str = "") -> dict[str, Any]:
        """Register an actual payment without mutating legacy commitment balances."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        if commitment_id is not None and not any(int(x.get("id", 0)) == int(commitment_id) for x in p.get("commitment_entries", [])):
            raise KeyError(f"commitment {commitment_id}")
        if counterparty_id is not None and self.find_project_counterparty_by_id(project_id, counterparty_id) is None:
            raise KeyError(counterparty_id)
        entries = list(p.get("payment_entries", []))
        payment_id = f"PAY{len(entries) + 1:05d}"
        entry = {
            "id": payment_id, "amount": float(amount), "date": str(date).strip(),
            "reference": str(reference).strip(), "document_id": int(document_id) if document_id is not None else None,
            "commitment_id": int(commitment_id) if commitment_id is not None else None,
            "counterparty_id": str(counterparty_id) if counterparty_id is not None else None,
            "notes": str(notes).strip(), "status": "unallocated",
        }
        control = self._finance_depth_control(project_id)
        control.add_payment(PaymentRecord(**entry))
        entries.append(entry)
        p["payment_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def allocate_project_payment(self, project_id: str, payment_id: str, target_type: str,
                                 target_id: int | str, amount: float) -> dict[str, Any]:
        """Allocate part/all of a payment to a document or commitment, atomically."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        control = self._finance_depth_control(project_id)
        allocation_id = f"ALC{len(p.get('payment_allocations', [])) + 1:05d}"
        allocation = PaymentAllocation(
            id=allocation_id, payment_id=str(payment_id), target_type=str(target_type),
            target_id=target_id, amount=float(amount),
        )
        control.allocate(allocation)
        records = list(p.get("payment_allocations", []))
        row = {
            "id": allocation_id, "payment_id": str(payment_id), "target_type": str(target_type),
            "target_id": target_id, "amount": float(amount),
        }
        records.append(row)
        p["payment_allocations"] = records
        self.store.save(project_id, p)
        return row

    def project_payments(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("payment_entries", []))

    def project_payment_summary(self, project_id: str) -> dict[str, Any]:
        return self._finance_depth_control(project_id).payment_summary()

    def add_financial_budget_line(self, project_id: str, code: str, category: str,
                                  planned: float, *, description: str = "") -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        records = list(p.get("financial_budget", []))
        row = {"code": str(code).strip(), "category": str(category).strip(),
               "description": str(description).strip(), "planned": float(planned)}
        candidate = FinancePaymentControl(budget=[
            BudgetLine(str(x.get("code")), str(x.get("category", "")), str(x.get("description", "")),
                       float(x.get("planned", 0) or 0)) for x in records + [row]
        ])
        _ = candidate
        if any(str(x.get("code", "")).strip() == row["code"] for x in records):
            raise ValueError("budget code must be unique")
        records.append(row)
        p["financial_budget"] = records
        self.store.save(project_id, p)
        return row

    def project_budget_control(self, project_id: str) -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return self._finance_depth_control(project_id).budget_control(
            actual_costs=p.get("cost_entries", []),
            commitments=p.get("commitment_entries", []),
        )

    def project_cash_flow_control(self, project_id: str) -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return self._finance_depth_control(project_id).cash_flow(
            receipts=p.get("receipt_entries", []),
            costs=p.get("cost_entries", []),
            payments=p.get("payment_entries", []),
            commitments=p.get("commitment_entries", []),
        )

    def project_finance_payment_depth_snapshot(self, project_id: str) -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        control = self._finance_depth_control(project_id)
        return control.control_snapshot(
            actual_costs=p.get("cost_entries", []),
            commitments=p.get("commitment_entries", []),
            receipts=p.get("receipt_entries", []),
            costs=p.get("cost_entries", []),
        )

    def project_finance_payment_depth_report(self, project_id: str, fmt: str, path):
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        snapshot = self.project_finance_payment_depth_snapshot(project_id)
        rows = []
        for row in snapshot["budget"]["rows"]:
            rows.append({
                "دسته": row["category"], "بودجه": row["planned"], "تعهد": row["committed"],
                "هزینه واقعی": row["actual"], "انحراف تعهد": row["committed_variance"],
                "انحراف هزینه": row["actual_variance"],
            })
        for row in snapshot["payments"]["rows"]:
            rows.append({
                "دسته": "پرداخت", "بودجه": "", "تعهد": row["amount"],
                "هزینه واقعی": row["allocated_amount"], "انحراف تعهد": "",
                "انحراف هزینه": row["unallocated_amount"],
            })
        return build_report(f'{p.get("name", "")} — عمق مالی و پرداخت', rows, snapshot).export(path, fmt)

    def validate(self,project_id:str): 
        p=self.store.get(project_id); return self.qa.run(p or {})

    def add_project_commitment(self, project_id: str, amount: float, *, category: str = "سایر", description: str = "", date: str = "", due_date: str = "", reference: str = "", paid_amount: float = 0.0, document_id: int | None = None, counterparty: str = "") -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        amount = float(amount)
        paid_amount = float(paid_amount)
        if amount < 0 or paid_amount < 0 or paid_amount > amount:
            raise ValueError("invalid commitment amount")
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        entries = list(p.get("commitment_entries", []))
        entry = {"id": len(entries) + 1, "amount": amount, "paid_amount": paid_amount, "category": str(category).strip() or "سایر", "description": str(description).strip(), "date": str(date).strip(), "due_date": str(due_date).strip(), "reference": str(reference).strip(), "document_id": int(document_id) if document_id is not None else None, "counterparty": str(counterparty).strip(), "counterparty_id": self._counterparty_id_for_name(p, counterparty)}
        entries.append(entry)
        p["commitment_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def project_commitments(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("commitment_entries", []))

    def project_commitment_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_commitments(project_id)
        total = sum(float(x.get("amount", 0) or 0) for x in entries)
        paid = sum(float(x.get("paid_amount", 0) or 0) for x in entries)
        return {"project_id": project_id, "entry_count": len(entries), "committed_total": total, "paid_total": paid, "unpaid_total": max(total - paid, 0.0)}

    def add_project_receipt(self, project_id: str, amount: float, *, description: str = "", date: str = "", reference: str = "", document_id: int | None = None, counterparty: str = "") -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        amount = float(amount)
        if amount < 0:
            raise ValueError("receipt amount cannot be negative")
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        entries = list(p.get("receipt_entries", []))
        entry = {"id": len(entries) + 1, "amount": amount, "description": str(description).strip(), "date": str(date).strip(), "reference": str(reference).strip(), "document_id": int(document_id) if document_id is not None else None, "counterparty": str(counterparty).strip(), "counterparty_id": self._counterparty_id_for_name(p, counterparty)}
        entries.append(entry)
        p["receipt_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def project_receipts(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        return list(p.get("receipt_entries", []))

    def project_receipt_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_receipts(project_id)
        return {"project_id": project_id, "entry_count": len(entries), "total_received": sum(float(x.get("amount", 0) or 0) for x in entries)}

    def project_financial_position(self, project_id: str) -> dict[str, Any]:
        dashboard = self.financial_dashboard(project_id)
        receipts = self.project_receipt_summary(project_id)
        commitments = self.project_commitment_summary(project_id)
        contract = float(dashboard["contract_amount"])
        received = float(receipts["total_received"])
        receivable = max(contract - received, 0.0)
        committed = float(commitments["committed_total"])
        return {
            "project_id": project_id, "contract_amount": contract,
            "earned_value": float(dashboard["cumulative_work"]), "actual_cost": float(dashboard["actual_cost"]),
            "received": received, "receivable": receivable,
            "committed_cost": committed, "unpaid_commitments": float(commitments["unpaid_total"]),
            "cash_exposure": max(committed - received, 0.0),
            "cost_margin": float(dashboard["gross_margin"]), "receipt_count": receipts["entry_count"],
            "commitment_count": commitments["entry_count"],
        }

    def project_cost_report(self, project_id: str, fmt: str, path):
        """Export the project's persisted cost ledger with category totals."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        entries = self.project_costs(project_id)
        summary = self.project_cost_summary(project_id)
        rows = [{
            "ردیف": entry.get("id", ""),
            "دسته": entry.get("category", ""),
            "شرح": entry.get("description", ""),
            "تاریخ": entry.get("date", ""),
            "مبلغ": float(entry.get("amount", 0) or 0),
        } for entry in entries]
        by_category = summary["by_category"]
        summary_payload = {
            "receipts": self.project_receipt_summary(project_id),
            "financial_position": self.project_financial_position(project_id),
            "cost": {
                "line_count": summary["entry_count"],
                "grand_total": summary["actual_cost"],
                "base": summary["actual_cost"],
                "factors": by_category,
            }
        }
        return build_report(f'{p.get("name", "")} — گزارش هزینه پروژه', rows, summary_payload).export(path, fmt)

    def _counterparty_id_for_name(self, project: dict[str, Any], name: str) -> str | None:
        key = " ".join(str(name).strip().split()).casefold()
        if not key:
            return None
        for item in project.get("counterparties", []):
            if " ".join(str(item.get("name", "")).strip().split()).casefold() == key:
                return str(item.get("id"))
        return None

    def _next_counterparty_id(self, records: list[dict[str, Any]]) -> str:
        numbers = []
        for item in records:
            raw = str(item.get("id", ""))
            if raw.upper().startswith("CP") and raw[2:].isdigit():
                numbers.append(int(raw[2:]))
        return f"CP{max(numbers, default=0) + 1:04d}"

    def add_project_counterparty(self, project_id: str, name: str, *, role: str = "", notes: str = "") -> dict[str, Any]:
        """Create a normalized active project counterparty master record."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        name = " ".join(str(name).strip().split())
        role = " ".join(str(role).strip().split())
        notes = " ".join(str(notes).strip().split())
        if not name:
            raise ValueError("counterparty name cannot be empty")
        records = list(p.get("counterparties", []))
        key = name.casefold()
        if any(str(x.get("name", "")).strip().casefold() == key for x in records):
            raise ValueError("counterparty already exists")
        record = {
            "id": self._next_counterparty_id(records),
            "name": name,
            "role": role,
            "notes": notes,
            "active": True,
        }
        records.append(record)
        p["counterparties"] = records
        self.store.save(project_id, p)
        return record

    def project_counterparties(self, project_id: str, *, active_only: bool = False) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        records = list(p.get("counterparties", []))
        if active_only:
            return [x for x in records if x.get("active", True)]
        return records

    def find_project_counterparty(self, project_id: str, name: str) -> dict[str, Any] | None:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        key = " ".join(str(name).strip().split()).casefold()
        if not key:
            return None
        return next((x for x in p.get("counterparties", []) if str(x.get("name", "")).strip().casefold() == key), None)

    def find_project_counterparty_by_id(self, project_id: str, counterparty_id: str) -> dict[str, Any] | None:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        key = str(counterparty_id).strip()
        if not key:
            return None
        return next((x for x in p.get("counterparties", []) if str(x.get("id", "")).strip() == key), None)

    def update_project_counterparty(self, project_id: str, counterparty_id: str, *, name: str | None = None,
                                    role: str | None = None, notes: str | None = None) -> dict[str, Any]:
        """Update master data without changing linked financial records."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        records = list(p.get("counterparties", []))
        target = next((x for x in records if str(x.get("id", "")) == str(counterparty_id).strip()), None)
        if target is None:
            raise KeyError(counterparty_id)
        new_name = " ".join(str(target.get("name", "") if name is None else name).strip().split())
        new_role = " ".join(str(target.get("role", "") if role is None else role).strip().split())
        new_notes = " ".join(str(target.get("notes", "") if notes is None else notes).strip().split())
        if not new_name:
            raise ValueError("counterparty name cannot be empty")
        key = new_name.casefold()
        if any(x is not target and str(x.get("name", "")).strip().casefold() == key for x in records):
            raise ValueError("counterparty already exists")
        target.update({"name": new_name, "role": new_role, "notes": new_notes})
        p["counterparties"] = records
        self.store.save(project_id, p)
        return target

    def set_project_counterparty_active(self, project_id: str, counterparty_id: str, active: bool) -> dict[str, Any]:
        """Activate/deactivate a counterparty while preserving historical links."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        records = list(p.get("counterparties", []))
        target = next((x for x in records if str(x.get("id", "")) == str(counterparty_id).strip()), None)
        if target is None:
            raise KeyError(counterparty_id)
        target["active"] = bool(active)
        p["counterparties"] = records
        self.store.save(project_id, p)
        return target


    def project_counterparty_financial_rollup(self, project_id: str) -> list[dict[str, Any]]:
        """Aggregate financial activity by stable counterparty ID, including legacy name-only records."""
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        parties=self.project_counterparties(project_id)
        rows={x["id"]: {"counterparty_id":x["id"],"name":x.get("name",""),"role":x.get("role",""),
                        "active":x.get("active",True),"documents":0,"document_amount":0.0,
                        "commitments":0,"commitment_amount":0.0,"paid_commitments":0.0,
                        "costs":0,"cost_amount":0.0,"receipts":0,"receipt_amount":0.0} for x in parties}
        for coll,key,count,amount in [
            ("financial_documents","documents","document_amount","amount"),
            ("commitment_entries","commitments","commitment_amount","amount"),
            ("cost_entries","costs","cost_amount","amount"),
            ("receipt_entries","receipts","receipt_amount","amount")]:
            for item in p.get(coll,[]):
                cid=item.get("counterparty_id") or self._counterparty_id_for_name(p,item.get("counterparty",""))
                if cid not in rows: continue
                rows[cid][key]+=1
                target_key = {"amount":"document_amount"}.get(amount, amount)
                if coll == "commitment_entries": target_key = "commitment_amount"
                elif coll == "cost_entries": target_key = "cost_amount"
                elif coll == "receipt_entries": target_key = "receipt_amount"
                rows[cid][target_key]+=float(item.get("amount",0) or 0)
                if coll=="commitment_entries":
                    rows[cid]["paid_commitments"]+=float(item.get("paid_amount",0) or 0)
        return sorted(rows.values(),key=lambda x:(not bool(x["active"]),str(x["name"]).casefold()))

    def project_counterparty_summary(self, project_id: str) -> dict[str, Any]:
        """Aggregate project financial exposure by counterparty."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        result: dict[str, dict[str, Any]] = {}
        def bucket(name: str) -> dict[str, Any]:
            key = str(name or "").strip() or "نامشخص"
            return result.setdefault(key, {"counterparty": key, "documents": 0, "document_amount": 0.0,
                                           "commitments": 0, "committed_amount": 0.0, "paid_commitments": 0.0,
                                           "cost_entries": 0, "actual_cost": 0.0, "receipts": 0, "received": 0.0})
        for d in p.get("financial_documents", []):
            b = bucket(d.get("counterparty", ""))
            b["documents"] += 1
            b["document_amount"] += float(d.get("amount", 0) or 0)
        for c in p.get("commitment_entries", []):
            # Commitment records predate counterparty support; use their optional field when available.
            b = bucket(c.get("counterparty", ""))
            b["commitments"] += 1
            b["committed_amount"] += float(c.get("amount", 0) or 0)
            b["paid_commitments"] += float(c.get("paid_amount", 0) or 0)
        for c in p.get("cost_entries", []):
            b = bucket(c.get("counterparty", ""))
            b["cost_entries"] += 1
            b["actual_cost"] += float(c.get("amount", 0) or 0)
        for r in p.get("receipt_entries", []):
            b = bucket(r.get("counterparty", ""))
            b["receipts"] += 1
            b["received"] += float(r.get("amount", 0) or 0)
        for b in result.values():
            b["unpaid_commitments"] = max(b["committed_amount"] - b["paid_commitments"], 0.0)
            b["net_cash"] = b["received"] - b["paid_commitments"]
        return {"project_id": project_id, "counterparties": list(result.values()),
                "counterparty_count": len(result)}

    def project_counterparty_ledger_by_id(self, project_id: str, counterparty_id: str) -> dict[str, Any]:
        """Return a detailed ledger using the stable counterparty ID."""
        party = self.find_project_counterparty_by_id(project_id, counterparty_id)
        if party is None:
            raise KeyError(counterparty_id)
        return self.project_counterparty_ledger(project_id, party["name"])

    def project_counterparty_ledger(self, project_id: str, counterparty: str) -> dict[str, Any]:
        """Return chronological financial activity for one project counterparty."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        name = str(counterparty).strip()
        if not name:
            raise ValueError("counterparty cannot be empty")
        rows = []
        def add(source: str, entry: dict[str, Any], amount: float, direction: str):
            rows.append({
                "source": source, "id": entry.get("id", ""), "date": entry.get("date", ""),
                "reference": entry.get("reference", ""), "description": entry.get("description", ""),
                "amount": float(amount), "direction": direction,
                "cash_in": float(amount) if direction == "in" else 0.0,
                "cash_out": float(amount) if direction == "out" else 0.0,
                "document_id": entry.get("document_id"),
            })
        for entry in p.get("financial_documents", []):
            if str(entry.get("counterparty", "")).strip() == name:
                add("سند مالی", entry, entry.get("amount", 0), "info")
        for entry in p.get("commitment_entries", []):
            if str(entry.get("counterparty", "")).strip() == name:
                add("تعهد", entry, entry.get("amount", 0), "out")
        for entry in p.get("cost_entries", []):
            if str(entry.get("counterparty", "")).strip() == name:
                add("هزینه", entry, entry.get("amount", 0), "out")
        for entry in p.get("receipt_entries", []):
            if str(entry.get("counterparty", "")).strip() == name:
                add("دریافتی", entry, entry.get("amount", 0), "in")
        rows.sort(key=lambda x: (str(x.get("date", "")), str(x.get("source", "")), int(x.get("id", 0) or 0)))
        cash_in = sum(x["cash_in"] for x in rows)
        cash_out = sum(x["cash_out"] for x in rows)
        return {
            "project_id": project_id, "counterparty": name, "rows": rows,
            "row_count": len(rows), "cash_in": cash_in, "cash_out": cash_out,
            "net_cash": cash_in - cash_out,
        }

    def project_counterparty_ledger_report(self, project_id: str, counterparty: str, fmt: str, path):
        """Export a detailed counterparty transaction ledger."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        ledger = self.project_counterparty_ledger(project_id, counterparty)
        rows = [{
            "نوع": x["source"], "شناسه": x["id"], "تاریخ": x["date"], "مرجع": x["reference"],
            "شرح": x["description"], "مبلغ": x["amount"], "جهت": x["direction"],
            "دریافت": x["cash_in"], "پرداخت": x["cash_out"], "سند مالی": x["document_id"] or "",
        } for x in ledger["rows"]]
        return build_report(f'{p.get("name", "")} — گردش حساب {counterparty}', rows, ledger).export(path, fmt)

    def project_counterparty_report(self, project_id: str, fmt: str, path):
        """Export the counterparty financial ledger."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        summary = self.project_counterparty_summary(project_id)
        rows = []
        for b in summary["counterparties"]:
            rows.append({
                "طرف حساب": b["counterparty"], "اسناد": b["documents"], "مبلغ اسناد": b["document_amount"],
                "تعهدات": b["commitments"], "مبلغ تعهدات": b["committed_amount"],
                "پرداخت تعهدات": b["paid_commitments"], "پرداخت‌نشده": b["unpaid_commitments"],
                "هزینه واقعی": b["actual_cost"], "دریافتی": b["received"], "خالص نقدی": b["net_cash"],
            })
        return build_report(f'{p.get("name", "")} — گردش مالی طرف حساب‌ها', rows, summary).export(path, fmt)

    def project_financial_kpi_summary(self, project_id: str, as_of: str = "") -> dict[str, Any]:
        """Return dashboard-ready financial KPIs without mutating persisted data."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        position = self.project_financial_position(project_id)
        status = self.project_financial_document_status_summary(project_id)
        result = {
            "project_id": project_id,
            "contract_amount": position["contract_amount"],
            "earned_value": position["earned_value"],
            "actual_cost": position["actual_cost"],
            "received": position["received"],
            "receivable": position["receivable"],
            "committed_cost": position["committed_cost"],
            "unpaid_commitments": position["unpaid_commitments"],
            "cash_exposure": position["cash_exposure"],
            "cost_margin": position["cost_margin"],
            "document_count": status["document_count"],
            "document_mismatches": status["mismatch_count"],
        }
        if str(as_of).strip():
            due_data = self.project_financial_due_summary(project_id, as_of)
            result.update({
                "overdue_amount": due_data["overdue_amount"],
                "overdue_count": due_data["overdue_count"],
                "due_today_count": due_data["due_today_count"],
                "upcoming_count": due_data["upcoming_count"],
                "no_due_date_count": due_data["no_due_date_count"],
                "open_due_amount": due_data["total_open_amount"],
            })
        else:
            result.update({
                "overdue_amount": 0.0, "overdue_count": 0, "due_today_count": 0,
                "upcoming_count": 0, "no_due_date_count": 0, "open_due_amount": 0.0,
            })
        return result

    def project_financial_due_summary(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Compact due-date control summary suitable for dashboard cards."""
        aging=self.project_financial_aging(project_id,as_of)
        return {
            "project_id":project_id, "as_of":aging["as_of"],
            "overdue_count":aging["overdue_count"], "overdue_amount":aging["overdue_amount"],
            "due_today_count":aging["due_today_count"], "upcoming_count":aging["upcoming_count"],
            "no_due_date_count":aging["no_due_date_count"],
            "total_open_amount":sum(float(x.get("outstanding",0) or 0) for x in aging["rows"]),
            "highest_risk":aging["rows"][0] if aging["rows"] else None,
        }

    def project_financial_aging(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Return deterministic due-date aging for unpaid project financial items.

        The caller supplies the reporting date explicitly. This avoids mixing the
        project's Jalali date strings with the machine's Gregorian clock.
        """
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        as_of_key = _normalize_date_key(as_of)
        if as_of_key is None:
            raise ValueError("invalid aging date; expected YYYY/MM/DD")
        rows = []

        def classify(due_date: str) -> str:
            due_key = _normalize_date_key(due_date)
            if due_key is None:
                return "بدون سررسید"
            if due_key < as_of_key:
                return "معوق"
            if due_key == as_of_key:
                return "سررسید امروز"
            return "آتی"

        for entry in p.get("commitment_entries", []):
            amount = float(entry.get("amount", 0) or 0)
            paid = float(entry.get("paid_amount", 0) or 0)
            outstanding = max(amount - paid, 0.0)
            if outstanding <= 0:
                continue
            due_date = str(entry.get("due_date", "")).strip()
            status = classify(due_date)
            rows.append({
                "source": "تعهد", "id": entry.get("id", ""), "counterparty": entry.get("counterparty", ""),
                "reference": entry.get("reference", ""), "due_date": due_date, "status": status,
                "amount": amount, "paid_amount": paid, "outstanding": outstanding,
            })

        for entry in p.get("financial_documents", []):
            payment_status = str(entry.get("payment_status", "unpaid")).strip().lower()
            if payment_status == "paid":
                continue
            amount = float(entry.get("amount", 0) or 0)
            due_date = str(entry.get("due_date", "")).strip()
            status = classify(due_date)
            rows.append({
                "source": "سند مالی", "id": entry.get("id", ""), "counterparty": entry.get("counterparty", ""),
                "reference": entry.get("document_number", ""), "due_date": due_date, "status": status,
                "amount": amount, "paid_amount": None, "outstanding": amount if payment_status == "unpaid" else None,
            })

        order = {"معوق": 0, "سررسید امروز": 1, "آتی": 2, "بدون سررسید": 3}
        rows.sort(key=lambda x: (order.get(x["status"], 9), _normalize_date_key(x["due_date"]) or "9999/99/99",
                                str(x["source"]), int(x.get("id", 0) or 0)))
        overdue_commitments = sum(x["outstanding"] for x in rows if x["source"] == "تعهد" and x["status"] == "معوق")
        overdue_unpaid_documents = sum(x["outstanding"] or 0 for x in rows if x["source"] == "سند مالی" and x["status"] == "معوق")
        return {
            "project_id": project_id,
            "as_of": as_of_key,
            "rows": rows,
            "row_count": len(rows),
            "overdue_count": sum(1 for x in rows if x["status"] == "معوق"),
            "due_today_count": sum(1 for x in rows if x["status"] == "سررسید امروز"),
            "upcoming_count": sum(1 for x in rows if x["status"] == "آتی"),
            "no_due_date_count": sum(1 for x in rows if x["status"] == "بدون سررسید"),
            "overdue_commitments": overdue_commitments,
            "overdue_unpaid_documents": overdue_unpaid_documents,
            "overdue_amount": overdue_commitments + overdue_unpaid_documents,
        }

    def project_financial_alerts(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Summarize actionable financial warnings for the dashboard."""
        aging = self.project_financial_aging(project_id, as_of)
        return {
            "project_id": project_id,
            "as_of": aging["as_of"],
            "overdue_amount": aging["overdue_amount"],
            "overdue_count": aging["overdue_count"],
            "due_today_count": aging["due_today_count"],
            "no_due_date_count": aging["no_due_date_count"],
            "upcoming_count": aging["upcoming_count"],
            "has_overdue": aging["overdue_count"] > 0,
            "has_due_today": aging["due_today_count"] > 0,
            "has_missing_due_date": aging["no_due_date_count"] > 0,
        }


    def project_financial_aging_report(self, project_id: str, as_of: str, fmt: str, path):
        """Export the project's due-date aging center."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        aging = self.project_financial_aging(project_id, as_of)
        rows = [{
            "نوع": x["source"], "شناسه": x["id"], "طرف حساب": x["counterparty"],
            "مرجع": x["reference"], "سررسید": x["due_date"], "وضعیت": x["status"],
            "مبلغ": x["amount"], "پرداخت": x["paid_amount"] if x["paid_amount"] is not None else "",
            "مانده": x["outstanding"] if x["outstanding"] is not None else "",
        } for x in aging["rows"]]
        return build_report(f'{p.get("name", "")} — کنترل سررسید مالی', rows, aging).export(path, fmt)


    def project_financial_report(self, project_id: str, fmt: str, path):
        """Export a consolidated project financial report from all financial ledgers."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        position = self.project_financial_position(project_id)
        documents = self.project_financial_documents(project_id)
        costs = self.project_costs(project_id)
        commitments = self.project_commitments(project_id)
        receipts = self.project_receipts(project_id)
        rows = []
        for entry in documents:
            rows.append({
                "نوع": "سند مالی",
                "شناسه": entry.get("id", ""),
                "شماره سند": entry.get("document_number", ""),
                "نوع سند": entry.get("document_type", ""),
                "طرف حساب": entry.get("counterparty", ""),
                "مبلغ": float(entry.get("amount", 0) or 0),
                "تاریخ": entry.get("date", ""),
                "سررسید": entry.get("due_date", ""),
                "وضعیت پرداخت": entry.get("payment_status", ""),
                "تعهد": entry.get("commitment_id", ""),
                "هزینه": entry.get("cost_entry_id", ""),
                "دریافتی": entry.get("receipt_id", ""),
                "مرجع": entry.get("reference", ""),
            })
        for entry in commitments:
            rows.append({
                "نوع": "تعهد",
                "شناسه": entry.get("id", ""),
                "شماره سند": "",
                "نوع سند": entry.get("category", ""),
                "طرف حساب": "",
                "مبلغ": float(entry.get("amount", 0) or 0),
                "تاریخ": entry.get("date", ""),
                "سررسید": entry.get("due_date", ""),
                "وضعیت پرداخت": "paid" if float(entry.get("paid_amount", 0) or 0) >= float(entry.get("amount", 0) or 0) else "unpaid",
                "تعهد": entry.get("id", ""),
                "هزینه": "",
                "دریافتی": "",
                "مرجع": entry.get("reference", ""),
            })
        for entry in costs:
            rows.append({
                "نوع": "هزینه",
                "شناسه": entry.get("id", ""),
                "شماره سند": "",
                "نوع سند": entry.get("category", ""),
                "طرف حساب": "",
                "مبلغ": float(entry.get("amount", 0) or 0),
                "تاریخ": entry.get("date", ""),
                "سررسید": "",
                "وضعیت پرداخت": "",
                "تعهد": "",
                "هزینه": entry.get("id", ""),
                "دریافتی": "",
                "مرجع": "",
            })
        for entry in receipts:
            rows.append({
                "نوع": "دریافتی",
                "شناسه": entry.get("id", ""),
                "شماره سند": "",
                "نوع سند": "دریافتی",
                "طرف حساب": "",
                "مبلغ": float(entry.get("amount", 0) or 0),
                "تاریخ": entry.get("date", ""),
                "سررسید": "",
                "وضعیت پرداخت": "received",
                "تعهد": "",
                "هزینه": "",
                "دریافتی": entry.get("id", ""),
                "مرجع": entry.get("reference", ""),
            })
        doc_summary = self.project_financial_document_summary(project_id)
        summary = {
            "financial_position": position,
            "documents": doc_summary,
            "cost": self.project_cost_summary(project_id),
            "commitments": self.project_commitment_summary(project_id),
            "receipts": self.project_receipt_summary(project_id),
        }
        return build_report(f'{p.get("name", "")} — گزارش مالی تجمیعی پروژه', rows, summary).export(path, fmt)

    def report(self,project_id:str,fmt:str,path,*,period_no:int|None=None):
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        estimate=p.get("estimate") or build_estimate(p.get("boq",[]), aggregate=False)
        selected=None
        periods=p.get("statement_periods",[])
        if period_no is not None:
            selected=next((x for x in periods if int(x.get("number",0))==int(period_no)),None)
            if selected is None: raise KeyError(f"statement period {period_no}")
        if selected is None:
            statement=self.build_statement(project_id)
            title=p.get("name","")
        else:
            statement=selected
            title=f'{p.get("name","")} — صورت‌وضعیت دوره {selected.get("number")}'
        rows=[]
        for row in statement.get("lines",[]):
            rows.append({"کد":row.get("code",""),"شرح":row.get("description",""),
                "واحد":row.get("unit",""),"مقدار قرارداد":row.get("contract_quantity",0),
                "قبلی":row.get("previous_quantity",0),"این دوره":row.get("current_quantity",0),
                "تجمعی":row.get("cumulative_quantity",0),"قیمت واحد":row.get("unit_price",0),
                "مبلغ این دوره":row.get("current_amount",0),"مبلغ تجمعی":row.get("completed_amount",0)})
        summary={**estimate.get("cost",{}), "period_no": selected.get("number") if selected else None,
                 "statement": {
            "gross_current":statement.get("gross_current",0),
            "retention":statement.get("retention",0),
            "advance_recovery":statement.get("advance_recovery",0),
            "taxable_current":statement.get("taxable_current",0),
            "tax":statement.get("tax",0),
            "insurance":statement.get("insurance",0),
            "payable_current":statement.get("payable_current",0),
            "previous_paid":statement.get("previous_paid",0),
            "balance_after_current":statement.get("balance_after_current",0),
        }}
        return build_report(title,rows,summary).export(path,fmt)
