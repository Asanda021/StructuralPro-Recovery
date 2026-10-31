"""Application service shared by desktop and future mobile/chat clients."""
from __future__ import annotations
from pathlib import Path
from copy import deepcopy
from uuid import uuid4
import json, math
from datetime import datetime, timezone
from typing import Any
from core.projects.store import ProjectStore
from core.takeoff.engine import TakeoffEngine
from core.takeoff.boq import build_boq, boq_summary
from core.takeoff.commit_guards import require_source_unused, validate_commit_rows, rebuild_project_boq, _is_payable_quantity
from core.takeoff.units import normalize_unit
from core.takeoff.explicit_inputs import require_explicit_measurement_params
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
from core.drawings.takeoff_bridge import session_to_boq_rows, validate_session_payload, verified_measurement_identities, assert_new_measurements
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

from core.commercial.exact_values import number, wire, exact, display_percent

def _statement_rate(value: Any, name: str):
    rate=number(value,name)
    if rate>1:raise ValueError(f"{name}: نرخ باید متناهی و بین صفر و یک باشد")
    return rate

class StructuralProApp:
    def __init__(self,data_dir: str|Path, *, identity_provider=None):
        self.data_dir=Path(data_dir); self.data_dir.mkdir(parents=True,exist_ok=True)
        self.store=ProjectStore(self.data_dir/"projects.db", identity_provider=identity_provider)
        self.takeoff=TakeoffEngine()
        self.qa=ProjectQA()
        self.ai_assistant = EngineeringAssistant()
        self.engineering = EngineeringLibrary()
        from core.collaboration.workspace import CollaborationWorkspace, Role
        self.collaboration = CollaborationWorkspace()
        for name, permissions in {
            'owner': {'edit','review','approve'}, 'admin': {'edit','review'},
            'editor': {'edit'}, 'reviewer': {'review'}, 'viewer': set(),
        }.items():
            self.collaboration.add_role(Role(name, frozenset(permissions)))


    def create_project(self,name:str,project_id:str)->dict[str,Any]:
        project={"id":project_id,"name":name,"takeoffs":[],"boq":[],"metadata":{"offline":True}}
        self.store.save(project_id,project); return self.store.get(project_id)

    def audit_legacy_metre_zip(
        self, zip_path: str | Path, *, bindings: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Read a user-supplied DWG+metre ZIP locally with strict ZIP/CAD gates.

        Does not write projects/BOQ, copy source drawings, or infer quantities.
        """
        from core.drawings.legacy_metre_cad_package import inspect_legacy_metre_package
        return inspect_legacy_metre_package(zip_path, bindings=bindings)

    def audit_legacy_metre_against_drawing(
        self, metre_path: str | Path, *,
        summary_path: str | Path | None = None,
        drawing_path: str | Path | None = None,
        bindings: list[dict] | None = None,
    ) -> dict[str, Any]:
        """P8/P2 read-only legacy metre vs CAD audit.

        No inferred line items, source mapping, user approval, or BOQ/price
        writes. A missing or unavailable native DWG reader is BLOCKED, not PASS.
        """
        from core.drawings.legacy_metre_cad_reconciliation import LegacyMetreCADReconciler
        return LegacyMetreCADReconciler().inspect(
            metre_path, summary_path=summary_path,
            drawing_path=drawing_path, bindings=bindings,
        )

    def preview_project_start(self, template_code: str, *, project_id: str, name: str,
                              floor_count: int, floor_names=None, disciplines=None):
        from core.projects.start_templates import preview_project_start
        return preview_project_start(template_code, project_id=project_id, name=name,
                                     floor_count=floor_count, floor_names=floor_names,
                                     disciplines=disciplines)

    def create_project_from_template(self, template_code: str, *, project_id: str, name: str,
                                     floor_count: int, floor_names=None, disciplines=None):
        from core.projects.start_templates import preview_project_start, project_payload
        preview=self.preview_project_start(template_code, project_id=project_id, name=name,
                                           floor_count=floor_count, floor_names=floor_names,
                                           disciplines=disciplines)
        from core.projects.project_model import _identity
        for item in self.store.list():
            if _identity(item.get("id"))==_identity(project_id):
                raise ValueError("شناسه پروژه مشابه قبلاً وجود دارد.")
            if _identity(item.get("name"))==_identity(name):
                raise ValueError("نام پروژه مشابه قبلاً وجود دارد.")
        self.store.save(project_id, project_payload(preview), create_only=True)
        return self.store.get(project_id)

    def open_project(self,project_id:str)->dict[str,Any]|None: return self.store.get(project_id)


    def _session_document_hashes(self, project_id: str) -> dict[str, str]:
        """Allow only registered source files whose bytes still match their hash."""
        documents = self.project_documents(project_id)
        if any(d["integrity"] != "verified" for d in documents):
            raise ValueError("session source evidence changed or is missing")
        return {str(d["id"]): str(d["sha256"]) for d in documents}

    def _view_session_directory(self, project_id: str, subject_id: str) -> Path:
        """Never use raw project IDs/user names as filesystem path components."""
        from hashlib import sha256
        key = sha256(json.dumps([project_id, subject_id], ensure_ascii=False).encode()).hexdigest()
        root = self.data_dir / "view_sessions"
        if root.is_symlink():
            raise ValueError("unsafe session directory")
        root.mkdir(exist_ok=True)
        folder = root / key
        if folder.is_symlink():
            raise ValueError("unsafe session directory")
        folder.mkdir(exist_ok=True)
        return folder

    def save_view_session(self, project_id: str, view: dict[str, Any]) -> dict[str, Any]:
        """Write only independent presentation state; never mutate SQLite/BOQ."""
        from core.platform.autosave import write_view_session
        pid = str(project_id)
        project = self.open_project(pid)  # store ACL checks OS identity
        if project is None:
            raise KeyError(pid)
        principal = self.store.current_principal(pid)
        revision = project["_meta"]["version"]
        hashes = self._session_document_hashes(pid)
        folder = self._view_session_directory(pid, principal.user_id)
        snapshot_id = uuid4().hex
        target = folder / (snapshot_id + ".json")
        write_view_session(
            target, project_id=pid, revision=revision,
            subject_id=principal.user_id, view=view, document_hashes=hashes,
        )
        return {"snapshot_id": snapshot_id, "project_id": pid, "revision": revision}

    def restore_view_session(self, project_id: str, snapshot_id: str) -> dict[str, Any]:
        """Only return validated selection/view; caller can offer Restore/Discard."""
        from core.platform.autosave import read_view_session
        if not isinstance(snapshot_id, str) or len(snapshot_id) != 32 or any(
            c not in "0123456789abcdef" for c in snapshot_id
        ):
            raise ValueError("invalid session ID")
        pid = str(project_id)
        project = self.open_project(pid)  # ACL and latest SQLite revision
        if project is None:
            raise KeyError(pid)
        principal = self.store.current_principal(pid)
        hashes = self._session_document_hashes(pid)
        folder = self._view_session_directory(pid, principal.user_id)
        allowed: dict[str, set[str]] = {
            "document_id": set(hashes),
        }
        for key, values in (
            ("floor_id", project.get("floors")),
            ("member_id", project.get("takeoffs")),
        ):
            if isinstance(values, list):
                allowed[key] = {str(item.get("id")) for item in values
                                if isinstance(item, dict) and item.get("id") is not None}
        return read_view_session(
            folder / (snapshot_id + ".json"), project_id=pid,
            revision=project["_meta"]["version"], subject_id=principal.user_id,
            document_hashes=hashes, existing_ids=allowed,
        )

    def add_project_document(self, project_id: str, path: str | Path) -> dict[str, Any]:
        """Register a regular evidence file with immutable project provenance."""
        from hashlib import sha256

        candidate = Path(path)
        if candidate.is_symlink() or not candidate.is_file():
            raise ValueError("project evidence must be a regular non-symlink file")
        resolved = candidate.resolve(strict=True)
        digest = sha256(resolved.read_bytes()).hexdigest()
        pid = str(project_id)
        project = self.open_project(pid)
        if project is None:
            raise KeyError(pid)
        for row in self.store.db.execute("SELECT id,payload FROM projects"):
            for item in json.loads(row["payload"]).get("documents", []):
                try:
                    same_path = Path(str(item.get("path", ""))).resolve(strict=False) == resolved
                except OSError:
                    same_path = False
                if same_path and str(row["id"]) != pid:
                    raise PermissionError("attachment is already bound to another project")
        documents = list(project.get("documents", []))
        if any(str(item.get("path", "")) == str(resolved) for item in documents):
            raise ValueError("attachment is already registered in this project")
        principal = self.store.current_principal(pid)
        document = {
            "id": uuid4().hex,
            "project_id": pid,
            "name": resolved.name,
            "path": str(resolved),
            "size": resolved.stat().st_size,
            "sha256": digest,
            "registered_by": principal.user_id,
        }
        documents.append(document)
        project["documents"] = documents
        self.store.save(pid, project, expected_digest=self.store.current_digest(pid))
        return deepcopy(document)

    def project_documents(self, project_id: str) -> list[dict[str, Any]]:
        """Read attachment metadata and report current integrity without mutation."""
        from hashlib import sha256

        project = self.open_project(project_id)
        if project is None:
            raise KeyError(project_id)
        result = []
        for source in project.get("documents", []):
            item = deepcopy(source)
            path = Path(str(item.get("path", "")))
            if path.is_symlink() or not path.is_file():
                item["integrity"] = "missing-or-unsafe"
            else:
                actual = sha256(path.read_bytes()).hexdigest()
                item["integrity"] = "verified" if actual == item.get("sha256") else "hash-mismatch"
                item["observed_sha256"] = actual
            result.append(item)
        return result

    def ifc_display_geometry(self, project_id, proposal_id):
        """Rebuild read-only display data from persisted reviewed source identity.

        No geometry cache or new ledger is written. Lineage is inspectable,
        including historical owners, but this method grants no quantity rights.
        """
        from core.drawings.ifc_pipeline import lineage_view_binding
        from core.bim.ifc import DeepIFCAdapter
        self.store._cache.pop(project_id, None)
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        decision, element = lineage_view_binding(project, proposal_id)
        source = decision['document']
        geometry = DeepIFCAdapter().read_display_contract(
            source['source_path'], revision=source['revision'])
        if geometry['source_sha256'] != source['source_sha256']:
            raise ValueError("منبع هندسه با تطبیق پروژه ناسازگار است.")
        selected = [item for item in geometry['elements']
                    if item['global_id'] == element['global_id']]
        if len(selected) != 1:
            raise ValueError("عضو فاقد هندسه سه‌بعدی معتبر است؛ هندسه حدس زده نمی‌شود.")
        geometry['elements'] = selected
        previous = any(proposal_id in event.get('previous_proposal_ids', [])
                       for event in project.get('ifc_identity_lineages', []))
        return {
            'project_id': project_id, 'proposal_id': proposal_id,
            'building_id': element['building_id'], 'floor_id': decision['floor_id'],
            'member_id': decision['member_id'], 'dimension': 3,
            'ownership_view': 'historical' if previous else 'current',
            'financial_permission': False, 'geometry': geometry,
        }

    def save_ifc_identity_proposal(self, project_id, path, *, revision, global_id,
                                   floor_id, member_id, author, reference, expected_digest, source_sha256):
        """Persist an explicit identity proposal, never an approval or BOQ receipt.

        Uses the existing project transaction/CAS and keeps previous proposals.
        Spatial evidence does not establish a reviewed 2D/BIM ownership crosswalk.
        """
        from copy import deepcopy
        from hashlib import sha256
        import json
        from core.drawings.bim_adapter import BIMAdapter
        from core.projects.project_model import _identity
        from core.platform.concurrency import assert_unchanged
        if not isinstance(expected_digest,str) or not expected_digest:
            raise ValueError('Snapshot و CAS برای پیشنهاد IFC الزامی است')
        self.store._cache.pop(str(project_id),None)
        project=deepcopy(self.store.get(project_id))
        if project is None:raise KeyError(project_id)
        assert_unchanged({k:v for k,v in project.items() if k!='_meta'},expected_digest)
        for value in (global_id,floor_id,member_id,author,reference):
            if not isinstance(value,str) or not value.strip():raise ValueError('هویت و مرجع پیشنهاد باید صریح باشد')
        floors=project.get('floors') or []
        members=project.get('members') or []
        floor=next((x for x in floors if _identity(x.get('id'))==_identity(floor_id)),None)
        member=next((x for x in members if _identity(x.get('id'))==_identity(member_id)),None)
        if floor is None or member is None or _identity(member.get('floor_id'))!=_identity(floor['id']):
            raise ValueError('FloorID یا MemberID عضو در پروژه معتبر نیست')
        doc=BIMAdapter().read_document(path,revision=revision)
        if doc['source_sha256']!=source_sha256:
            raise ValueError('منبع IFC پس از مشاهده تغییر کرده است')
        element=next((x for x in doc['elements'] if x['global_id']==global_id),None)
        if element is None or not element['storey_id'] or not element['placement_step_id']:
            raise ValueError('عضو IFC فاقد طبقه یا Placement معتبر است')
        proposals=project.setdefault('ifc_identity_proposals',[])
        for old in proposals:
            if old['document']['source_sha256']==doc['source_sha256'] and old['global_id']==global_id:
                raise ValueError('پیشنهاد همین عضو و منبع قبلاً ثبت شده است')
            if old['document']['source_sha256']==doc['source_sha256'] and old['storey_id']==element['storey_id'] and _identity(old['floor_id'])!=_identity(floor['id']):
                raise ValueError('طبقه IFC در پیشنهاد قبلی به طبقه دیگری متصل است؛ بازبینی مستقل لازم است')
        source={k:doc[k] for k in ('source_path','source_sha256','source_id','schema','parser','revision','unit_factors_si')}
        result={'project_id':str(project_id),'building_id':element['building_id'],
                'floor_id':floor['id'],'member_id':member['id'],'storey_id':element['storey_id'],
                'global_id':global_id,'ifc_type':element['ifc_type'],'document':source,
                'placement_matrix_si':element['placement_matrix_si'],'author':author.strip(),
                'reference':reference.strip(),'status':'proposed','ready':False,
                'commit_allowed':False,'payable_rows':[],
                'blockers':['تطبیق طبقه و هویت فیزیکی نیازمند بازبینی مستقل است',
                            'Crosswalk چندمنبعی و قرارداد انتقال مالی هنوز تأیید نشده‌اند']}
        result['id']=sha256(json.dumps(result,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        proposals.append(result)
        self.store.save(project_id,project,expected_digest=expected_digest)
        return deepcopy(result)

    def save_ifc_column_detail(self, project_id, **kwargs):
        from core.drawings.ifc_pipeline import save_column_detail
        return save_column_detail(self, project_id, **kwargs)

    def save_ifc_crosswalk(self, project_id, **kwargs):
        from core.drawings.ifc_pipeline import save_crosswalk
        return save_crosswalk(self, project_id, **kwargs)

    def review_ifc_identity(self, project_id, **kwargs):
        from core.drawings.ifc_pipeline import review_identity
        return review_identity(self, project_id, **kwargs)

    def migrate_ifc_crosswalk_group(self, project_id, **kwargs):
        from core.drawings.ifc_pipeline import migrate_crosswalk_group
        return migrate_crosswalk_group(self, project_id, **kwargs)

    def apply_ifc_quantity_transfer(self, project_id, **kwargs):
        from core.takeoff.manual_formula_amendments import apply_ifc_transfer
        return apply_ifc_transfer(self, project_id, **kwargs)

    def preview_ifc_quantity_transfer_step(self, project_id, **kwargs):
        from core.takeoff.manual_formula_amendments import preview_ifc_transfer_step
        return preview_ifc_transfer_step(self, project_id, **kwargs)

    def undo_ifc_quantity_transfer(self, project_id, **kwargs):
        from core.takeoff.manual_formula_amendments import step_ifc_transfer
        return step_ifc_transfer(self, project_id, action='undo', **kwargs)

    def redo_ifc_quantity_transfer(self, project_id, **kwargs):
        from core.takeoff.manual_formula_amendments import step_ifc_transfer
        return step_ifc_transfer(self, project_id, action='redo', **kwargs)

    def assess_ifc_lineage_quantities(self, project_id, **kwargs):
        from core.drawings.ifc_lineage import assess_quantities
        return assess_quantities(self, project_id, **kwargs)

    def review_ifc_identity_lineage(self, project_id, **kwargs):
        """Record explicit non-payable split/merge of approved IFC member identities."""
        from core.drawings.ifc_lineage import review_lineage
        return review_lineage(self, project_id, **kwargs)

    def live_takeoff_tracker(self, project_id: str, *, boq_receipt_verifier=None):
        """Load audited live member identities from this application's canonical SQLite.

        This returns a read-only identity/navigation tracker; it never calls
        the quantity engine, reconstructs approvals, or commits a BOQ.
        """
        from core.projects.user_workflow import LiveTakeoffTracker
        return LiveTakeoffTracker.from_store(
            self.store, project_id, boq_receipt_verifier=boq_receipt_verifier)

    def takeoff_identity_snapshot(self, project_id: str) -> dict[str, Any]:
        """Expose persisted takeoff-to-member audit to existing UI clients."""
        return self.live_takeoff_tracker(project_id).persisted_identity_snapshot()

    def _explicit_project_structure(self, project_id: str):
        """Load canonical project, its CAS digest, and only stored floor/member IDs."""
        from core.projects.project_model import ProjectModel, _identity
        pid = str(project_id or "").strip()
        if not _identity(pid):
            raise ValueError("شناسه پروژه معتبر نیست")
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if not isinstance(project, dict) or _identity(project.get("id")) != _identity(pid):
            raise ValueError("شناسه پروژه ذخیره‌شده معتبر نیست")
        floors = project.get("floors", [])
        members = project.get("members", [])
        if not isinstance(floors, list) or not isinstance(members, list):
            raise ValueError("طبقات یا اعضای پروژه ساختار معتبری ندارند")
        model = ProjectModel(project_id=str(project["id"]), name=project.get("name", ""),
                             floors=deepcopy(floors), members=deepcopy(members))
        problems = model.validate()
        if problems:
            raise ValueError("ساختار طبقات و اعضای موجود نامعتبر است: " + "؛ ".join(problems))
        return project, digest, model

    def add_project_floor(self, project_id: str, name: str, *, level=None) -> dict[str, Any]:
        """Append an explicitly named floor through existing SQLite/CAS, not a new ledger."""
        project, digest, model = self._explicit_project_structure(project_id)
        result = model.add_floor(name, level=level)
        project["floors"] = model.floors
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(result)

    def add_project_member(self, project_id: str, member_id: str, floor_id: str,
                           kind: str, *, source_id=None) -> dict[str, Any]:
        """Append a user-declared member with strict parent and Unicode identity."""
        project, digest, model = self._explicit_project_structure(project_id)
        result = model.add_member(member_id, floor_id, kind, source_id=source_id)
        project["members"] = model.members
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(result)

    def import_project_pricebook(self, project_id: str, path: str | Path, *, year: int,
                                 approved_by: str, currency: str | None = None,
                                 source_version: str = "", replace_approved: bool = False,
                                 expected_digest: str | None = None) -> dict[str, Any]:
        """Bind a real user import and explicit reviewer to this project's pricing gate."""
        from core.pricing.catalog import PriceCatalog
        from core.pricing.import_service import PricebookImportService
        import hashlib
        reviewer = str(approved_by or "").strip()
        if not reviewer: raise ValueError("تأییدکننده فهرست‌بهای پروژه الزامی است")
        digest = self.store.current_digest(project_id)
        if expected_digest is not None and expected_digest != digest:
            raise RuntimeError("project changed since write began")
        if currency is not None and currency not in {"IRR", "IRT"}:
            raise ValueError("واحد پولی باید صریحاً ریال یا تومان باشد؛ تبدیل خودکار انجام نمی‌شود")
        self.store._cache.pop(str(project_id), None)
        project = self.store.get(project_id)
        if project is None: raise KeyError(project_id)
        catalog = PriceCatalog()
        receipt = PricebookImportService(catalog).import_file(path, year=year, discipline="building", source_id="project-user-import")
        source = Path(path).resolve()
        if hashlib.sha256(source.read_bytes()).hexdigest() != receipt.sha256:
            raise ValueError("فایل فهرست‌بها هنگام ورود تغییر کرده است؛ تأیید ثبت نشد")
        review = {"status":"approved", "numeric_encoding_version":2, "approved_by":reviewer, "path":str(source),
                  "sha256":receipt.sha256, "receipt":receipt.as_dict(),
                  "rows_by_code":{x.code:{"unit":x.unit,"unit_price":x.unit_price}
                                  for x in catalog.search("",year=year,limit=receipt.rows)}}
        review["currency"] = currency
        review["source_version"] = str(source_version).strip()
        previous = project.get("user_pricebook_review")
        if previous and previous != review:
            if not replace_approved:
                raise ValueError("جایگزینی فهرست‌بهای تأییدشده نیازمند تأیید صریح کاربر است")
            history = list(project.get("pricebook_review_history") or [])
            history.append(deepcopy(previous))
            project["pricebook_review_history"] = history
        project["user_pricebook_review"] = review
        self.store.save(project_id,project,expected_digest=digest)
        return deepcopy(review)

    def export_beam_detail_report(self, project_id, floor_id, beam_id, path, *, format):
        from core.reports.beam_detail_report import export
        return export(self,project_id,floor_id,beam_id,path,format=format)

    def create_beam_legacy_mapping(self,project_id,**kwargs):
        from core.takeoff.manual_formula_amendments import mapping_create
        return mapping_create(self,project_id,**kwargs)

    def inspect_beam_legacy_mapping(self,project_id):
        from core.takeoff.manual_formula_amendments import mapping_inventory,read
        return mapping_inventory(read(self,project_id)[0])

    def export_beam_legacy_mapping_report(self,project_id,path,*,format):
        from core.reports.beam_legacy_mapping_report import export
        return export(self,project_id,path,format=format)

    def inspect_beam_history(self,project_id):
        from core.takeoff.manual_formula_amendments import inspect_beam_history
        return inspect_beam_history(self,project_id)

    def create_beam_migration(self,project_id,floor_id,beam_id,data,*,evidence_path,evidence_sha256,evidence_reference,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_create
        evidence={'evidence_path':evidence_path,'evidence_sha256':evidence_sha256,'evidence_reference':evidence_reference}
        return beam_create(self,project_id,floor_id,beam_id,data,migration=evidence,**kwargs)

    def export_column_detail_report(self,project_id,floor_id,member_id,path,*,format):
        from core.reports.column_detail_report import export
        return export(self,project_id,floor_id,member_id,path,format=format)

    def export_foundation_detail_report(self,project_id,kind,floor_id,member_id,path,*,format):
        from core.takeoff.manual_formula_amendments import FOUNDATION_KINDS
        from core.reports.column_detail_report import export
        if kind not in FOUNDATION_KINDS:raise ValueError('نوع پی و شناژ معتبر نیست')
        return export(self,project_id,floor_id,member_id,path,format=format,kind=kind)

    def copy_structural_member(self,project_id,kind,floor_id,member_id,**kwargs):
        from core.takeoff.reviewed_structural import ReviewedStructuralWorkflow
        return ReviewedStructuralWorkflow(self.store,self.takeoff).copy_draft(project_id,kind,floor_id,member_id,**kwargs)

    def delete_structural_member_draft(self,project_id,kind,floor_id,member_id,**kwargs):
        from core.takeoff.reviewed_structural import ReviewedStructuralWorkflow
        return ReviewedStructuralWorkflow(self.store,self.takeoff).delete_draft(project_id,kind,floor_id,member_id,**kwargs)

    def create_foundation_amendment(self,project_id,kind,floor_id,member_id,data,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_create
        return beam_create(self,project_id,floor_id,member_id,data,foundation_kind=kind,**kwargs)

    def create_column_amendment(self,project_id,floor_id,member_id,data,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_create
        return beam_create(self,project_id,floor_id,member_id,data,column=True,**kwargs)

    def create_beam_amendment(self,project_id,floor_id,beam_id,data,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_create
        return beam_create(self,project_id,floor_id,beam_id,data,**kwargs)

    def review_beam_amendment(self,project_id,amendment_id,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_review
        return beam_review(self,project_id,amendment_id,**kwargs)

    def apply_beam_amendment(self,project_id,amendment_id,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_apply
        return beam_apply(self,project_id,amendment_id,**kwargs)

    def beam_detail_workflow(self):
        """Use the canonical SQLite project store and quantity engine for beam details."""
        from core.takeoff.beam_detail import BeamDetailWorkflow
        return BeamDetailWorkflow(self.store, self.takeoff)

    def new_beam_detail(self, floor_id: str, beam_id: str) -> dict[str, Any]:
        from core.takeoff.beam_detail import empty_beam
        return empty_beam(floor_id, beam_id)

    def save_beam_detail_draft(self, project_id: str, draft: dict[str, Any], *,
                               expected_revision: int = 0, reason: str = "ثبت پیش‌نویس") -> dict[str, Any]:
        return self.beam_detail_workflow().save_draft(
            project_id, draft, expected_revision=expected_revision,reason=reason
        )

    def get_beam_detail(self, project_id: str, floor_id: str,
                        beam_id: str) -> dict[str, Any] | None:
        return self.beam_detail_workflow().get(project_id, floor_id, beam_id)

    def preview_beam_detail(self, project_id: str, floor_id: str,
                            beam_id: str) -> dict[str, Any]:
        return self.beam_detail_workflow().preview(project_id, floor_id, beam_id)

    def commit_beam_detail(self, project_id: str, floor_id: str,
                           beam_id: str, *, expected_revision: int) -> dict[str, Any]:
        return self.beam_detail_workflow().commit(
            project_id, floor_id, beam_id, expected_revision=expected_revision
        )

    def structural_drawing_evidence(self, kind: str, member_id: str, *,
                                   drawing_sha256: str, cad_document=None,
                                   cad_region=None, cad_scene_origin=None,
                                   pdf_engine=None) -> dict[str, Any]:
        """Return text evidence only; no unreviewed value becomes a quantity."""
        from core.drawings.member_evidence import index_member_evidence
        return index_member_evidence(
            kind, member_id, drawing_sha256=drawing_sha256,
            cad_document=cad_document, cad_region=cad_region,
            cad_scene_origin=cad_scene_origin, pdf_engine=pdf_engine)

    def structural_member_workflow(self):
        """Column, grade beam and foundation reviews use the same canonical engine/store."""
        from core.takeoff.reviewed_structural import ReviewedStructuralWorkflow
        return ReviewedStructuralWorkflow(self.store, self.takeoff, application=self)

    def new_structural_member(self, kind: str, floor_id: str, member_id: str) -> dict[str, Any]:
        from core.takeoff.reviewed_structural import empty_member
        return empty_member(kind, floor_id, member_id)

    def save_structural_member_draft(self, project_id: str, draft: dict[str, Any], *,
                                      expected_revision: int = 0, reason: str = "ثبت پیش‌نویس") -> dict[str, Any]:
        return self.structural_member_workflow().save_draft(
            project_id, draft, expected_revision=expected_revision,reason=reason)

    def get_structural_member(self, project_id: str, kind: str, floor_id: str,
                              member_id: str) -> dict[str, Any] | None:
        return self.structural_member_workflow().get(project_id, kind, floor_id, member_id)

    def preview_structural_member(self, project_id: str, kind: str, floor_id: str,
                                  member_id: str) -> dict[str, Any]:
        return self.structural_member_workflow().preview(project_id, kind, floor_id, member_id)

    def commit_structural_member(self, project_id: str, kind: str, floor_id: str,
                                 member_id: str, *, expected_revision: int) -> dict[str, Any]:
        return self.structural_member_workflow().commit(
            project_id, kind, floor_id, member_id, expected_revision=expected_revision)

    def aec_workflow(self):
        """Reviewed roof, stair, wall, finish and MEP quantities on existing SQLite/BOQ."""
        from core.takeoff.reviewed_aec import ReviewedAECWorkflow
        return ReviewedAECWorkflow(self.store, self.takeoff)

    def aec_system_types(self) -> dict[str, Any]:
        from core.takeoff.reviewed_aec import SPECS
        return {key: {"title": spec.title, "components": list(spec.components),
                      "essential": list(spec.essential)}
                for key, spec in SPECS.items()}

    def preview_structural_handoff(self, project_id, request, *, source_path, source_sha256, evidence_files=None):
        """Read-only specialist audit against the current existing SQLite project."""
        from core.takeoff.structural_handoff_work import preview
        return preview(self, project_id, request, source_path=source_path,
                       source_sha256=source_sha256, evidence_files=evidence_files)

    def structural_handoff_basis(self, project_id):
        from core.takeoff.structural_handoff_work import project_basis
        return project_basis(self, project_id)

    def save_structural_handoff_draft(self, project_id, audit_id, request, **kwargs):
        from core.takeoff.structural_handoff_work import save_draft
        return save_draft(self, project_id, audit_id, request, **kwargs)

    def get_structural_handoff_audit(self, project_id, audit_id):
        from core.takeoff.structural_handoff_work import get_audit
        return get_audit(self, project_id, audit_id)

    def run_structural_handoff_audit(self, project_id, audit_id, *, expected_revision):
        from core.takeoff.structural_handoff_work import run_audit
        return run_audit(self, project_id, audit_id, expected_revision=expected_revision)

    def commit_structural_handoff_audit(self, project_id, audit_id, **kwargs):
        from core.takeoff.structural_handoff_work import commit_audit
        return commit_audit(self, project_id, audit_id, **kwargs)

    def new_aec_system(self, kind: str, floor_id: str, system_id: str) -> dict[str, Any]:
        from core.takeoff.reviewed_aec import empty_system
        return empty_system(kind, floor_id, system_id)

    def save_aec_system_draft(self, project_id: str, draft: dict[str, Any], *,
                              expected_revision: int = 0) -> dict[str, Any]:
        return self.aec_workflow().save_draft(
            project_id, draft, expected_revision=expected_revision)

    def get_aec_system(self, project_id: str, kind: str, floor_id: str,
                       system_id: str) -> dict[str, Any] | None:
        return self.aec_workflow().get(project_id, kind, floor_id, system_id)

    def preview_aec_system(self, project_id: str, kind: str, floor_id: str,
                           system_id: str) -> dict[str, Any]:
        return self.aec_workflow().preview(project_id, kind, floor_id, system_id)

    def commit_aec_system(self, project_id: str, kind: str, floor_id: str,
                          system_id: str, *, expected_revision: int) -> dict[str, Any]:
        return self.aec_workflow().commit(
            project_id, kind, floor_id, system_id, expected_revision=expected_revision)

    def review_roof_system(self,project_id,kind,floor_id,system_id,*,expected_revision,reviewer,note):
        return self.aec_workflow().review_roof(project_id,kind,floor_id,system_id,expected_revision=expected_revision,reviewer=reviewer,note=note)

    def create_roof_amendment(self,project_id,kind,floor_id,system_id,data,**kwargs):
        from core.takeoff.manual_formula_amendments import beam_create
        return beam_create(self,project_id,floor_id,system_id,data,roof_kind=kind,**kwargs)

    def export_stair_detail_report(self,project_id,floor_id,system_id,path,*,format):
        from core.reports.stair_detail_report import export
        return export(self,project_id,floor_id,system_id,path,format=format)

    def export_shear_wall_detail_report(self,project_id,floor_id,system_id,path,*,format):
        from core.reports.shear_wall_detail_report import export
        return export(self,project_id,floor_id,system_id,path,format=format)

    def export_roof_detail_report(self,project_id,kind,floor_id,system_id,path,*,format):
        from core.reports.roof_detail_report import export
        return export(self,project_id,kind,floor_id,system_id,path,format=format)

    def office_aec_report(self, project_id: str, mode: str, fmt: str, path,
                          *, statement: dict[str, Any] | None = None):
        from core.reports.aec_office_package import export_office_package
        project = self.open_project(project_id)
        if project is None:
            raise KeyError(project_id)
        return export_office_package(project, mode, fmt, path, statement=statement)

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

    def create_manual_formula_amendment(self, project_id, row_id, data, *, expected_revision, created_by, reason):
        from core.takeoff.manual_formula_amendments import proposal
        return proposal(self,project_id,row_id,data,expected_revision=expected_revision,created_by=created_by,reason=reason)

    def review_manual_formula_amendment(self, project_id, amendment_id, *, expected_revision, reviewer, note):
        from core.takeoff.manual_formula_amendments import review
        return review(self,project_id,amendment_id,expected_revision=expected_revision,reviewer=reviewer,note=note)

    def apply_manual_formula_amendment(self, project_id, amendment_id, *, expected_revision):
        from core.takeoff.manual_formula_amendments import apply
        return apply(self,project_id,amendment_id,expected_revision=expected_revision)

    def delete_manual_formulas(self, project_id, row_ids, *, expected_revisions, reason):
        from core.takeoff.manual_formula_history import delete
        return delete(self,project_id,row_ids,expected_revisions=expected_revisions,reason=reason)

    def undo_manual_formulas(self, project_id):
        from core.takeoff.manual_formula_history import step
        return step(self,project_id)

    def redo_manual_formulas(self, project_id):
        from core.takeoff.manual_formula_history import step
        return step(self,project_id,redo=True)

    def set_manual_formula_deduction(self, project_id, row_id, item, *, expected_revision, reason):
        from core.takeoff.manual_formula_deductions import set_item
        return set_item(self,project_id,row_id,item,expected_revision=expected_revision,reason=reason)

    def remove_manual_formula_deduction(self, project_id, row_id, source_id, *, expected_revision, reason):
        from core.takeoff.manual_formula_deductions import remove
        return remove(self,project_id,row_id,source_id,expected_revision=expected_revision,reason=reason)

    def manual_formula_deduction_summary(self, project_id, row_id):
        from core.takeoff.manual_formula_deductions import summary
        return summary(self,project_id,row_id)

    def relocate_manual_formulas(self, project_id, row_ids, *, destination, mode, expected_revisions, reason, deduction_sources=None):
        from core.takeoff.manual_formula_locations import relocate
        return relocate(self,project_id,row_ids,destination=destination,mode=mode,expected_revisions=expected_revisions,reason=reason,deduction_sources=deduction_sources)

    def save_manual_formula(self, project_id, row_id, data, *, expected_revision, reason):
        from core.takeoff.manual_formula_register import save
        return save(self,project_id,row_id,data,expected_revision=expected_revision,reason=reason)

    def preview_bulk_edit_manual_formulas(self, project_id, row_ids, *, changes, expected_revisions):
        from core.takeoff.manual_formula_register import preview_bulk_edit
        return preview_bulk_edit(self,project_id,row_ids,changes=changes,
                                 expected_revisions=expected_revisions)

    def bulk_edit_manual_formulas(self, project_id, row_ids, *, changes, expected_revisions, reason, expected_digest=None):
        from core.takeoff.manual_formula_register import bulk_edit
        return bulk_edit(self,project_id,row_ids,changes=changes,expected_revisions=expected_revisions,reason=reason,expected_digest=expected_digest)

    def copy_manual_formulas(self, project_id, row_ids, *, floor, expected_revisions, reason):
        from core.takeoff.manual_formula_register import copy_rows
        return copy_rows(self,project_id,row_ids,floor=floor,expected_revisions=expected_revisions,reason=reason)

    def export_manual_formula_report(self, project_id, path, *, format):
        from core.reports.manual_formula_report import export
        return export(self,project_id,path,format=format)

    def load_manual_formulas(self, project_id):
        from core.takeoff.manual_formula_register import load
        return load(self,project_id)

    def review_manual_formula(self, project_id, row_id, *, expected_revision, reviewer, note):
        from core.takeoff.manual_formula_register import review
        return review(self,project_id,row_id,expected_revision=expected_revision,reviewer=reviewer,note=note)

    def commit_manual_formula(self, project_id, row_id, *, expected_revision):
        from core.takeoff.manual_formula_register import commit
        return commit(self,project_id,row_id,expected_revision=expected_revision)

    def add_takeoff(self,project_id:str,domain:str,item:str,**params)->dict[str,Any]:
        """Save one explicitly sourced manual takeoff with a guarded SQLite CAS."""
        pid=str(project_id or "").strip()
        if not pid:
            raise ValueError("شناسه پروژه الزامی است")
        source_id=str(params.pop("source_id","")).strip()
        if not source_id:
            raise ValueError("ثبت متره بدون شناسه منبع یکتا ممنوع است")
        description=str(params.pop("description","")).strip()
        system=str(params.pop("system","")).strip() or None
        digest=self.store.current_digest(pid)
        self.store._cache.pop(pid,None)
        p=self.store.get(pid)
        if p is None:
            raise KeyError(pid)
        require_source_unused(p,source_id)
        if source_id in (p.get("deleted_takeoff_sources") or []):
            raise ValueError("منبع متره حذف‌شده قبلاً استفاده شده است؛ ثبت دوباره با همان منشأ مجاز نیست")
        location=str(params.get("manual_location_id", "")).strip()
        if location and not system: raise ValueError("شناسه عضو به طبقه صریح نیاز دارد")
        if location and any(str(r.get("system", ""))==system and str(r.get("item", ""))==str(item) and str(r.get("params",{}).get("manual_location_id", ""))==location for r in p.get("takeoffs", [])):
            raise ValueError("عضو همین عملیات و طبقه قبلاً متره شده است")
        calculation_params=deepcopy(params)
        normalized_domain=takeoff_domain(domain)
        require_explicit_measurement_params(normalized_domain,item,calculation_params)
        result=self.takeoff.calculate(normalized_domain,item,description=description or item,**calculation_params)
        row={"id":f"{len(p.get('takeoffs') or [])+1}",
             "member_code":str(params.get("member_code",item)),
             "source_id":source_id,"domain":normalized_domain,"item":str(item),
             "params":calculation_params,"revision":1,
             "description":description or item,"system":system,
             "provenance":{"mode":"manual","source_id":source_id},
             "quantities":[{"code":item,"title":description or item,"system":system,
                            "unit":result.unit,"amount":result.quantity,
                            "formula":result.formula,"warning":result.warning,
                            "price_code":params.get("price_code"),
                            "unit_price":params.get("unit_price")}]}
        validated=validate_commit_rows(p,[row],source_id=source_id)
        p["takeoffs"],p["boq"]=rebuild_project_boq(p,(p.get("takeoffs") or [])+validated)
        self.store.save(pid,p,expected_digest=digest)
        return deepcopy(row)

    def drawing_amendment_document(self,project_id,source_id,payload,**kwargs):
        from core.takeoff.manual_formula_amendments import drawing_document
        return drawing_document(self,project_id,source_id,payload,**kwargs)

    def create_drawing_amendment(self,project_id,source_id,payload,**kwargs):
        from core.takeoff.manual_formula_amendments import drawing_create
        return drawing_create(self,project_id,source_id,payload,**kwargs)

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
            "session": deepcopy(payload), "source_sha256": str(payload.get("source_sha256", "")), "committed_item_ids": committed,
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
        rows = verified_measurement_identities(record, rows)
        assert_new_measurements(project, record, rows)
        # E8 P7-P5: the existing commit guards cannot attribute a changed
        # source/quantity to the same member automatically. A new independent
        # review is mandatory for source-backed planar regions only. Legacy
        # length/count/AI candidates retain their original stricter gates.
        e8_area_ids = tuple(row["takeoff_id"] for row in rows
                            if row["kind"] == "area" and row.get("geometry_evidence"))
        if e8_area_ids:
            from core.reports.source_discrepancy_gate import require_no_pending_source_discrepancies
            require_no_pending_source_discrepancies(
                self, project_id=pid,
                expected_project_version=project["_meta"]["version"],
                session_id=sid, selected_item_ids=e8_area_ids,
            )
        from core.reports.ifc_crosswalk_source_audit import require_reviewed_ifc_crosswalks_for_boq
        require_reviewed_ifc_crosswalks_for_boq(
            self, project_id=pid,
            expected_project_version=project["_meta"]["version"],
            session_id=sid, selected_item_ids=tuple(selected),
        )
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
                           "source_sha256": row["source_sha256"], "measurement_identity": row["measurement_identity"],
                           "calibration": row["calibration"], "holes": row.get("holes", []),
                           "geometry_evidence": row.get("geometry_evidence"),
                           **({"cad_evidence":row["cad_evidence"]} if row.get("cad_evidence") else {}),
                           "page": row["page"], "geometry": row["geometry"],
                           "confidence": row["confidence"], "formula": row["formula"]},
                "revision": 1, "drawing_session_id": sid, "drawing_takeoff_id": row["takeoff_id"],
                "provenance": {"mode": "drawing", "source_id": source_id,
                               "drawing_session_id": sid, "drawing_source": row["drawing_source"],
                           "source_sha256": row["source_sha256"], "measurement_identity": row["measurement_identity"],
                           "calibration": row["calibration"], "holes": row.get("holes", []),
                           "geometry_evidence": row.get("geometry_evidence"),
                           **({"cad_evidence":row["cad_evidence"]} if row.get("cad_evidence") else {}),
                               "page": row["page"]},
                "description": row["description"], "system": f"صفحه {row['page']}",
                "quantities": [{
                    "code": row["item_code"], "title": row["description"], "system": f"صفحه {row['page']}",
                    "unit": row["unit"], "amount": row["quantity"], "formula": row["formula"],
                    "warning": "", "price_code": row["price_code"], "unit_price": None,
                    "source_ref": row["source"], "page": row["page"],
                }],
            })
        validated = validate_commit_rows(
            project, new_takeoffs, source_id=f"drawing-session:{sid}:{current_revision}")
        project["takeoffs"], project["boq"] = rebuild_project_boq(
            project, (project.get("takeoffs") or []) + validated)
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
        canonical_rows = session_to_boq_rows(record.get("session", {}), session_id=sid, selected_item_ids=list(candidate_item_ids))
        canonical_rows = verified_measurement_identities(record, canonical_rows)
        assert_new_measurements(project, record, canonical_rows)
        # The explicit user review of an AI proposal does not waive a known
        # cross-session source clash. Reuse the same E8 gate as manual commit.
        e8_area_ids = tuple(row["takeoff_id"] for row in canonical_rows
                            if row["kind"] == "area" and row.get("geometry_evidence"))
        if e8_area_ids:
            from core.reports.source_discrepancy_gate import require_no_pending_source_discrepancies
            require_no_pending_source_discrepancies(
                self, project_id=pid,
                expected_project_version=project["_meta"]["version"],
                session_id=sid, selected_item_ids=e8_area_ids,
            )
        from core.reports.ifc_crosswalk_source_audit import require_reviewed_ifc_crosswalks_for_boq
        require_reviewed_ifc_crosswalks_for_boq(
            self, project_id=pid,
            expected_project_version=project["_meta"]["version"],
            session_id=sid, selected_item_ids=tuple(sorted(candidate_item_ids)),
        )
        identities = {row["takeoff_id"]: row for row in canonical_rows}
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
                           "measurement_identity": identities[item_id]["measurement_identity"],
                           "source_sha256": identities[item_id]["source_sha256"],
                           "drawing_source": identities[item_id]["drawing_source"],
                           "geometry": identities[item_id]["geometry"],
                           "calibration": identities[item_id]["calibration"],
                           "geometry": [list(point) for point in measured_item.geometry],
                           "evidence": deepcopy(candidate["evidence"]), "confidence": candidate["confidence"],
                           "formula": candidate["formula"]},
                "revision": 1, "drawing_session_id": sid, "ai_generated": True,
                "provenance": {"mode": "drawing", "source_id": source_id,
                               "drawing_session_id": sid, "page": page,
                               "source_ref": source_ref},
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
        validated = validate_commit_rows(
            project, new_rows, source_id=f"drawing-ai-session:{sid}:{expected_session_revision}")
        project["takeoffs"], project["boq"] = rebuild_project_boq(
            project, (project.get("takeoffs") or []) + validated)
        record["ai_committed_item_ids"] = sorted(set(record.get("ai_committed_item_ids", [])) | seen_session_items)
        record["revision"] = expected_session_revision + 1
        record["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(pid, project, expected_digest=digest)
        return {"approved": True, "takeoffs_added": deepcopy(new_rows), "boq_count": len(project["boq"]),
                "drawing_session_id": sid, "drawing_session_revision": record["revision"]}

    def add_assembly_takeoff(self, project_id: str, assembly_code: str, inputs: dict[str, Any], *,
                             floor_id: str, description: str = "",
                             measurement_source: str | None = None,
                             approved_by: str | None = None, location_id: str = "",
                             component_prices: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
        """Commit all separately measured assembly parts as one reviewed transaction."""
        pid=str(project_id).strip()
        floor=str(floor_id or "").strip()
        if not pid or not floor:
            raise ValueError("شناسه پروژه و طبقه/ناحیه باید صریح مشخص شوند")
        result=AssemblyTemplateLibrary().expand(assembly_code,inputs)
        if not result.complete:
            raise ValueError("ورودی‌های قالب کامل نیستند: " + "، ".join(result.missing_inputs))
        if not result.components:
            raise ValueError("قالب متره مرکب هیچ جزء قابل ثبتی تولید نکرد")
        measurement = str(measurement_source or location_id or "").strip()
        reviewer = str(approved_by or "").strip()
        if not measurement:
            raise ValueError("شناسه ثابت محل یا مرجع واقعی برداشت عملیات مرکب الزامی است")
        if not reviewer:
            raise ValueError("نام تأییدکننده واقعی عملیات مرکب الزامی است")
        digest=self.store.current_digest(pid)
        self.store._cache.pop(pid,None)
        project=self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        bundle_id=uuid4().hex
        # Stable physical identity independent of randomly generated bundle IDs.
        # The same location cannot be re-billed as a new assembly.
        bundle_source=f"manual-assembly:{pid}:{floor}:{result.code}:{measurement}"
        require_source_unused(project,bundle_source)
        prices=deepcopy(component_prices or {})
        if not isinstance(prices,dict) or set(prices)-{c.code for c in result.components}:
            raise ValueError("نگاشت قیمت به جزء ناشناخته مجاز نیست")
        for c in result.components:
            if c.code not in prices:continue
            price=prices[c.code]
            if not isinstance(price,dict) or set(price)!={"price_code","unit","unit_price"}:
                raise ValueError("قیمت جزء به کد، واحد و قیمت صریح نیاز دارد")
            if not _is_payable_quantity({"params":{"assembly_code":result.code}},{"code":c.code}):
                raise ValueError("مصالح تأمین و مصرف دوباره وارد پرداخت نمی‌شوند")
            if not str(price["price_code"]).strip() or normalize_unit(price["unit"])!=normalize_unit(c.unit):
                raise ValueError("کد یا واحد قیمت جزء نامعتبر است")
            if isinstance(price["unit_price"],bool) or not math.isfinite(float(price["unit_price"])) or float(price["unit_price"])<0:
                raise ValueError("قیمت جزء باید نامنفی و متناهی باشد")
        created_at=datetime.now(timezone.utc).isoformat()
        parent={
            "id":bundle_id,"assembly_code":result.code,"title":result.title,
            "description":str(description or result.title).strip(),"floor_id":floor,
            "inputs":deepcopy(dict(inputs)),"inputs_used":list(result.inputs_used),
            "revision":1,"created_at":created_at,"component_source_ids":[],
            "measurement_source":measurement,"source_id":bundle_source,
            "location_id":str(location_id).strip(),"component_prices":prices,
            "approved_by":reviewer,
        }
        rows=[]
        previous_count=len(project.get("takeoffs") or [])
        for component in result.components:
            source_id=f"{bundle_source}:{component.code}"
            title=f"{parent['description']} — {component.title}"
            payable=_is_payable_quantity({"params":{"assembly_code":result.code}},{"code":component.code})
            role="work" if payable else "procurement" if component.code.endswith("_procurement") else "material"
            row={
                "id":f"{previous_count+len(rows)+1}",
                "member_code":component.code,"source_id":source_id,
                "domain":"assembly","item":component.code,
                "params":{"assembly_id":bundle_id,"assembly_code":result.code,
                          "component_code":component.code,"inputs":deepcopy(dict(inputs))},
                "revision":1,"assembly_id":bundle_id,
                "component_role":role,"location_id":str(location_id).strip(),
                "description":title,"system":floor,
                "provenance":{"mode":"manual","source_id":bundle_source,
                              "source_component_id":source_id,
                              "approved_by":reviewer,"assembly_id":bundle_id},
                "quantities":[{
                    "code":component.code,"title":title,"system":floor,
                    "role":role,
                    "unit":component.unit,"amount":float(component.quantity),
                    "formula":component.formula,"warning":component.warning,
                    "price_code":prices.get(component.code,{}).get("price_code"),
                    "unit_price":prices.get(component.code,{}).get("unit_price"),
                }],
            }
            rows.append(row)
            parent["component_source_ids"].append(source_id)
        validated=validate_commit_rows(project,rows,source_id=bundle_source)
        project["takeoffs"],project["boq"]=rebuild_project_boq(
            project,(project.get("takeoffs") or [])+validated)
        project.setdefault("takeoff_assemblies",[]).append(parent)
        self.store.save(pid,project,expected_digest=digest)
        return {"assembly":deepcopy(parent),"rows":deepcopy(rows)}

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
        # Reviewed, drawing and assembly quantities require their own dedicated
        # revision workflows; a generic item edit would bypass approval gates.
        if (row.get("review") or row.get("assembly_id") or
                row.get("drawing_session_id") or
                source.startswith(("beam-detail:", "structural:", "aec:"))):
            raise ValueError("ویرایش این متره باید از مسیر بازبینی تخصصی همان عضو/نقشه انجام شود")
        current = int(row.get("revision", 1))
        if current != expected:
            raise RuntimeError(f"تعارض نسخه متره؛ نسخه فعلی {current} است و نسخه ارسالی {expected} بود.")

        normalized_domain = takeoff_domain(domain)
        calculation_params = deepcopy(params)
        for name in ("manual_location_id", "price_code", "unit_price"):
            if name not in calculation_params and name in row.get("params", {}):
                calculation_params[name]=row["params"][name]
        effective_system=str(system).strip() if system is not None else row.get("system")
        location=str(calculation_params.get("manual_location_id", "")).strip()
        if location and not effective_system: raise ValueError("شناسه عضو به طبقه صریح نیاز دارد")
        if location and any(other is not row and str(other.get("system", ""))==effective_system and str(other.get("item", ""))==str(item) and str(other.get("params",{}).get("manual_location_id", ""))==location for other in project.get("takeoffs", [])):
            raise ValueError("نسخه جدید با عضو موجود تداخل دارد")
        require_explicit_measurement_params(normalized_domain,item,calculation_params)
        clean_description = str(description or row.get("description") or item).strip()
        result = self.takeoff.calculate(normalized_domain, item, description=clean_description,
                                        **calculation_params)
        if not math.isfinite(result.quantity) or result.quantity <= 0:
            raise ValueError("ریزکمیت ویرایش‌شده باید مثبت و مستند باشد")
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

        project["takeoffs"], project["boq"] = rebuild_project_boq(
            project, project.get("takeoffs") or [])
        self.store.save(pid, project, expected_digest=digest)
        return deepcopy(row)

    def delete_takeoff(self, project_id: str, source_id: str, *, expected_revision: int) -> dict[str, Any]:
        """Safely retire a single manual measurement without erasing its audit trail.

        Issued statements and reviewed/graphical measurement families require
        dedicated adjustment workflows; a generic delete must never bypass them.
        """
        pid = str(project_id or "").strip()
        source = str(source_id or "").strip()
        if not pid or not source:
            raise ValueError("شناسه پروژه و منبع متره برای حذف الزامی است")
        if isinstance(expected_revision, bool):
            raise ValueError("نسخه متره برای حذف باید عدد صحیح مثبت باشد")
        try:
            expected = int(expected_revision)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("نسخه متره برای حذف معتبر نیست") from exc
        if expected < 1 or expected != expected_revision:
            raise ValueError("نسخه متره برای حذف باید عدد صحیح مثبت باشد")
        digest = self.store.current_digest(pid)
        self.store._cache.pop(pid, None)
        project = self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        if project.get("statement_periods"):
            raise ValueError("متره دارای صورت‌وضعیت صادرشده است؛ حذف مستقیم ممنوع و اصلاحیه رسمی لازم است")
        rows = project.get("takeoffs") or []
        matches = [row for row in rows if str(row.get("source_id", "")).strip() == source]
        if len(matches) != 1:
            raise KeyError("منبع متره برای حذف باید دقیقاً یک ردیف موجود باشد")
        row = matches[0]
        if (row.get("review") or row.get("assembly_id") or row.get("drawing_session_id") or
                row.get("domain") in {"assembly", "drawing", "drawing_ai"} or
                source.startswith(("beam-detail:", "structural:", "aec:"))):
            raise ValueError("حذف این متره باید از گردش اصلاحیه تخصصی عضو یا نقشه انجام شود")
        current = int(row.get("revision", 1))
        if current != expected:
            raise RuntimeError("نسخه متره تغییر کرده است؛ حذف نسخه قدیمی رد شد")
        left = [other for other in rows if other is not row]
        project["takeoffs"], project["boq"] = rebuild_project_boq(project, left)
        tombstones = list(project.get("deleted_takeoff_sources") or [])
        if source in tombstones:
            raise ValueError("منبع قبلاً حذف شده است")
        tombstones.append(source)
        project["deleted_takeoff_sources"] = tombstones
        history = list(project.get("takeoff_revision_history") or [])
        history.append({"source_id": source, "event": "deleted", "from_revision": current,
                        "changed_at": datetime.now(timezone.utc).isoformat(),
                        "previous_row": deepcopy(row)})
        project["takeoff_revision_history"] = history
        self.store.save(pid, project, expected_digest=digest)
        return {"source_id": source, "deleted_revision": current,
                "remaining_takeoffs": len(project["takeoffs"]), "status": "retired"}

    def review_boq_price_mapping(self, project_id, mapping, *, reviewer, expected_digest):
        """Approve explicit BOQ indices against the imported file; preserve takeoffs."""
        from core.reports.aec_office_package import audit_boq
        from core.pricing.catalog import PriceCatalog
        from core.pricing.import_service import verify_reviewed_rates
        if not str(reviewer or "").strip() or not isinstance(mapping, dict) or not mapping:
            raise ValueError("نگاشت صریح ردیف و بازبین الزامی‌اند")
        digest = self.store.current_digest(project_id)
        if digest != expected_digest:
            raise RuntimeError("project changed since write began")
        self.store._cache.pop(str(project_id), None)
        project = self.store.get(project_id)
        audit_boq(project)
        book = project.get("user_pricebook_review") or {}
        if book.get("status") != "approved" or book.get("currency") not in {"IRR", "IRT"}:
            raise ValueError("فهرست‌بهای تأییدشده با واحد پولی صریح الزامی است")
        verify_reviewed_rates(Path(book["path"]), book)
        rows = deepcopy(project["boq"])
        changes = []
        used = set()
        for key, code in mapping.items():
            if isinstance(key, bool) or str(key) != str(int(key)):
                raise ValueError("شناسه ردیف نگاشت نامعتبر است")
            index = int(key)
            if index < 0 or index >= len(rows) or index in used:
                raise ValueError("ردیف نگاشت ناموجود یا تکراری است")
            used.add(index)
            row = rows[index]
            price = book["rows_by_code"].get(code)
            if not price or not PriceCatalog._units_compatible(row["unit"], price["unit"]):
                raise ValueError("کد قیمت مفقود یا واحد ناسازگار است")
            changes.append({"index": index, "source_ids": row.get("source_ids"),
                            "item_code": row.get("item_code"), "price_code": code})
            row["price_code"] = code
            row["unit_price"] = price["unit_price"]
        project["boq"] = build_boq(rows, aggregate=False)
        audit_boq(project, require_pricebook=True)
        project.setdefault("price_mapping_reviews", []).append({"reviewer": reviewer,
            "pricebook_sha256": book["sha256"], "basis_digest": digest, "changes": changes})
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(project["boq"])

    def review_project_factors(self, project_id, path, *, sha256, author, reviewer, expected_digest):
        """Review explicit sequential factor evidence; never infer a contract formula."""
        import hashlib, json
        from datetime import date
        if not str(author or "").strip() or not str(reviewer or "").strip() or author == reviewer:
            raise ValueError("ثبت‌کننده و بازبین مستقل ضرایب الزامی‌اند")
        digest = self.store.current_digest(project_id)
        if digest != expected_digest:
            raise RuntimeError("project changed since write began")
        source = Path(path).resolve()
        raw = source.read_bytes()
        if len(raw) > 1024 * 1024 or hashlib.sha256(raw).hexdigest() != sha256:
            raise ValueError("SHA-256 یا اندازه مدرک ضرایب نامعتبر است")
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("basis") != "sequential_compound":
            raise ValueError("فقط مبنای صریح ترکیب ترتیبی موجود پشتیبانی می‌شود")
        if not str(data.get("version", "")).strip():
            raise ValueError("نسخه مدرک ضرایب الزامی است")
        date.fromisoformat(data["effective_date"])
        self.store._cache.pop(str(project_id), None)
        project = self.store.get(project_id)
        book = project.get("user_pricebook_review") or {}
        if data.get("currency") not in {"IRR", "IRT"} or data["currency"] != book.get("currency"):
            raise ValueError("واحد پولی ضرایب با فهرست‌بها تطبیق ندارد")
        if data.get("year") != (book.get("receipt") or {}).get("year"):
            raise ValueError("سال ضرایب با فهرست‌بها تطبیق ندارد")
        if not isinstance(data.get("factors"), list):
            raise ValueError("ترتیب ضرایب باید صریح باشد")
        rates = {}
        for item in data["factors"]:
            name = str(item.get("name", "")).strip()
            if not name or name in rates:
                raise ValueError("نام ضریب نامعتبر یا تکراری است")
            rates[name] = wire(number(item.get("rate"), "ضریب مستند"))
        review = {**data, "rates": rates, "status": "approved", "path": str(source),
                  "sha256": sha256, "author": author, "reviewer": reviewer,
                  "pricebook_sha256": book["sha256"]}
        previous = project.get("factor_review")
        if previous:
            project.setdefault("factor_review_history", []).append(deepcopy(previous))
        project["factor_review"] = review
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(review)

    def recalculate_estimate(self, project_id: str, *, factors: dict[str,float] | None = None) -> dict[str,Any]:
        """Financial estimate needs priced BOQ, finite rates and a version-safe save."""
        pid=str(project_id or "").strip()
        digest=self.store.current_digest(pid)
        self.store._cache.pop(pid,None)
        project=self.store.get(pid)
        if project is None:
            raise KeyError(pid)
        boq=project.get("boq") or []
        if not boq:
            raise ValueError("برای برآورد مالی باید ریزمتره و BOQ موجود باشند")
        for row in boq:
            if row.get("unit_price") is None or not row.get("price_code"):
                raise ValueError("قیمت واحد و کد فهرست‌بها برای همه ردیف‌های برآورد الزامی است")
            number(row["unit_price"], "بهای واحد")
        # A nonempty hand-entered rate/code is not proof of a reviewed,
        # user-imported pricebook. The same source-to-BOQ reconciliation gate
        # used for financial exports must also protect the estimate service.
        from core.reports.aec_office_package import audit_boq
        audit_boq(project, require_pricebook=True)
        factor_review = project.get("factor_review")
        if factor_review:
            import hashlib
            raw_factor_document = Path(factor_review["path"]).read_bytes()
            if hashlib.sha256(raw_factor_document).hexdigest() != factor_review["sha256"]:
                raise ValueError("مدرک ضرایب تغییر کرده است")
            if factor_review["pricebook_sha256"] != project["user_pricebook_review"]["sha256"]:
                raise ValueError("ضرایب متعلق به نسخه دیگری از فهرست‌بها هستند")
            import json
            original_factors = json.loads(raw_factor_document)
            if any(factor_review.get(key) != value for key, value in original_factors.items()):
                raise ValueError("نسخه ذخیره‌شده ضرایب با مدرک منطبق نیست")
            documented_rates = {item["name"]: wire(number(item["rate"], "ضریب مستند"))
                                for item in original_factors["factors"]}
            if documented_rates != factor_review["rates"]:
                raise ValueError("نرخ ضرایب ذخیره‌شده با مدرک منطبق نیست")
            if factors is not None and factors != documented_rates:
                raise ValueError("تغییر ضرایب نیازمند مدرک و بازبینی جدید است")
            factors = documented_rates
        elif factors is None:
            factors = (project.get("estimate") or {}).get("factors", {})
        normalized_factors={}
        for name,value in (factors or {}).items():
            if isinstance(value,bool):
                raise ValueError("ضریب برآورد نباید بولی باشد")
            rate=number(value,'ضرایب برآورد')
            normalized_factors[str(name)]=wire(rate)
        estimate=build_estimate(boq,factors=normalized_factors,aggregate=False)
        estimate["numeric_encoding_version"]=2
        estimate["financial_policy_status"]="EXPLICIT_OWNER_POLICY" if project.get("statement_amendment_policy") else "LEGACY_PREVIEW_NOT_FINANCIALLY_APPROVED"
        if factor_review:
            estimate["factor_review_sha256"] = factor_review["sha256"]
            estimate["currency"] = factor_review["currency"]
        if project.get("estimate"):
            project.setdefault("estimate_history", []).append(deepcopy(project["estimate"]))
        project["estimate"]=estimate
        self.store.save(pid,project,expected_digest=digest)
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

    @exact
    def build_statement(self, project_id: str, *, previous_paid: float = 0.0,
                        retention_rate: float = 0.0, advance_recovery_rate: float = 0.0,
                        tax_rate: float = 0.0, insurance_rate: float = 0.0) -> dict[str, Any]:
        """Build a period payment statement directly from the project's BOQ."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.reports.aec_office_package import audit_boq
        audit_boq(p, require_pricebook=True)
        retention_rate = _statement_rate(retention_rate, "تضمین")
        advance_recovery_rate = _statement_rate(advance_recovery_rate, "بازگشت پیش‌پرداخت")
        tax_rate = _statement_rate(tax_rate, "مالیات")
        insurance_rate = _statement_rate(insurance_rate, "بیمه")
        previous_paid=number(previous_paid,'پرداخت قبلی')
        lines = []
        for row in p.get("boq", []):
            if row.get("current_quantity") is None or isinstance(row.get("current_quantity"), bool):
                raise ValueError("کارکرد دوره باید صریح وارد شود؛ مقدار نامعلوم صفر نیست")
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
        rates={'retention_rate':retention_rate,'advance_recovery_rate':advance_recovery_rate,'tax_rate':tax_rate,'insurance_rate':insurance_rate}
        amounts,status,money=self._statement_money(p,progress['lines'],rates)
        return wire({**progress,**amounts,'previous_paid':previous_paid,'balance_after_current':number(amounts['payable_current'],'پرداختنی')-previous_paid,
                     'rates':rates,'financial_policy_status':status,**({'money_policy':money} if money else {})})

    @exact
    def _statement_money(self, project, lines, rates):
        from core.commercial.statement_amendment import _money,policy,check_documents
        money=None;status='LEGACY_RECORD_NOT_FINANCIALLY_APPROVED'
        if project.get('statement_amendment_policy'):
            configured=policy(project);check_documents(configured['source_documents'])
            money=configured['money'];status='EXPLICIT_OWNER_POLICY'
        quantities={line['code']:number(line['current_quantity'],'کارکرد') for line in lines}
        prices={line['code']:number(line['unit_price'],'بهای واحد') for line in lines}
        values=_money(quantities,prices,{k:number(v,k) for k,v in rates.items()},money)
        return {k:wire(number(v,k)) for k,v in values.items()},status,money

    def create_contract_change_request(self, project_id, *, created_by, reason, source_documents, lines, expected_project_version):
        from core.commercial.contract_requests import create_request
        return create_request(self.store,project_id,'contract',created_by,reason,source_documents,expected_project_version,lines=lines)

    def create_settlement_request(self, project_id, *, created_by, reason, source_documents, receipt_ids, expected_project_version):
        from core.commercial.contract_requests import create_request
        return create_request(self.store,project_id,'settlement',created_by,reason,source_documents,expected_project_version,receipt_ids=receipt_ids)

    def post_contract_change_request(self, *args, **kwargs):
        from core.commercial.contract_requests import post_request
        return post_request(*args,**kwargs)

    def post_settlement_request(self, *args, **kwargs):
        from core.commercial.contract_requests import post_request
        return post_request(*args,**kwargs)

    def _amendment(self, project_id, op, actor, expected_project_version, **data):
        from core.commercial.statement_amendment import StatementAmendmentService
        return StatementAmendmentService(self.store).execute(project_id, op, actor, expected_project_version, **data)

    def configure_statement_amendments(self, project_id, *, owner_id, policy, source_documents, expected_project_version, establish_owner=False):
        return self._amendment(project_id, 'configure', owner_id, expected_project_version, policy=policy, source_documents=source_documents, establish_owner=establish_owner)

    def create_statement_amendment(self, project_id, period_no, *, created_by, expected_project_version, **data):
        return self._amendment(project_id, 'create', created_by, expected_project_version, period_no=period_no, **data)

    def edit_statement_amendment(self, project_id, amendment_id, *, edited_by, expected_project_version, **data):
        return self._amendment(project_id, 'edit', edited_by, expected_project_version, id=amendment_id, **data)

    def review_statement_amendment(self, project_id, amendment_id, *, reviewed_by, expected_project_version, **data):
        return self._amendment(project_id, 'review', reviewed_by, expected_project_version, id=amendment_id, **data)

    def approve_statement_amendment(self, project_id, amendment_id, *, approved_by, expected_project_version, **data):
        return self._amendment(project_id, 'approve', approved_by, expected_project_version, id=amendment_id, **data)

    def post_statement_amendment(self, project_id, amendment_id, *, posted_by, expected_project_version, **data):
        return self._amendment(project_id, 'post', posted_by, expected_project_version, id=amendment_id, **data)

    def reject_statement_amendment(self, project_id, amendment_id, *, rejected_by, expected_project_version, **data):
        return self._amendment(project_id, 'reject', rejected_by, expected_project_version, id=amendment_id, **data)

    def statement_amendments(self, project_id):
        return self.open_project(project_id).get('statement_amendments', [])

    def statement_amendment_summary(self, project_id, period_no):
        from core.commercial.statement_amendment import summary
        return summary(self.open_project(project_id), period_no)

    @exact
    def save_statement_period(self, project_id: str, *, period_no: int | None = None,
                              current_quantities: dict[str, float] | None = None,
                              retention_rate: float = 0.0, advance_recovery_rate: float = 0.0,
                              tax_rate: float = 0.0, insurance_rate: float = 0.0,
                              persist: bool = True) -> dict[str, Any]:
        """Persist a numbered statement period and roll its quantities into the next period."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        retention_rate = _statement_rate(retention_rate, "تضمین")
        advance_recovery_rate = _statement_rate(advance_recovery_rate, "بازگشت پیش‌پرداخت")
        tax_rate = _statement_rate(tax_rate, "مالیات")
        insurance_rate = _statement_rate(insurance_rate, "بیمه")
        from core.reports.aec_office_package import audit_boq
        audit_boq(p, require_pricebook=True)
        periods = list(p.get("statement_periods", []))
        if period_no is None:
            period_no = (max((int(x.get("number", 0)) for x in periods), default=0) + 1)
        if isinstance(period_no,bool) or float(period_no) != int(period_no):
            raise ValueError("شماره دوره باید عدد صحیح مثبت باشد")
        period_no = int(period_no)
        if period_no <= 0 or any(int(x.get("number", 0)) == period_no for x in periods):
            raise ValueError("statement period number must be positive and unique")
        previous = {}
        if periods:
            previous = {
                str(x.get("code", "")): number(x.get('cumulative_quantity',0),'کارکرد تجمعی')
                for x in periods[-1].get("lines", [])
            }
        if any(d.get('status') == 'POSTED' for d in p.get('statement_amendments', [])):
            from core.commercial.statement_amendment import cumulative_quantities
            previous = {code: value for code, value in cumulative_quantities(p).items()}
        raw_quantities = current_quantities or {}
        known_codes = {str(row.get("price_code", "") or "") for row in p.get("boq", [])}
        if any(str(code) not in known_codes for code in raw_quantities):
            raise ValueError("کد کارکرد در BOQ پروژه وجود ندارد")
        if any(isinstance(value, bool) for value in raw_quantities.values()):
            raise ValueError("کارکرد باید عددی باشد، نه مقدار منطقی")
        overrides = {str(k): number(v,'کارکرد دوره') for k, v in raw_quantities.items()}
        lines = []
        for row in p.get("boq", []):
            code = str(row.get("price_code", "") or "")
            if code not in overrides and row.get("current_quantity") is None:
                raise ValueError("کارکرد دوره باید صریح وارد شود؛ مقدار نامعلوم صفر نیست")
            cur = number(overrides.get(code, row.get('current_quantity')),'کارکرد دوره')
            prev = number(previous.get(code,row.get('previous_quantity',0)),'کارکرد قبلی')
            if not all(math.isfinite(value) and value >= 0 for value in (cur, prev)):
                raise ValueError("statement quantities must be finite and non-negative")
            lines.append({
                "code": code, "description": row.get("description", ""), "unit": row.get("unit", ""),
                "contract_quantity": number(row.get('quantity'),'مقدار قرارداد'),
                "unit_price": number(row.get('unit_price'),'بهای واحد'),
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
                "retention_rate": wire(retention_rate), "advance_recovery_rate": wire(advance_recovery_rate),
                "tax_rate": wire(tax_rate), "insurance_rate": wire(insurance_rate),
            },
        }
        amounts,status,money=self._statement_money(p,period['lines'],period['rates'])
        period.update(amounts);period['financial_policy_status']=status
        if money:period['money_policy']=dict(money)
        period["numeric_encoding_version"]=2
        period=wire(period)
        periods.append(period)
        p["statement_periods"] = periods
        if persist:
            self.store.save(project_id, p)
        return period


    def financial_command(self, project_id, op, *, actor, expected_version, **data):
        from core.commercial.financial_ledger import ledger_dispatch
        from datetime import datetime, timezone
        from uuid import uuid4
        p=self.open_project(project_id)
        if isinstance(expected_version,bool) or expected_version!=p['_meta']['version']:
            raise RuntimeError('نسخه پروژه تغییر کرده است')
        command={**data,'domain':'ledger','op':op,'actor':actor,'at':datetime.now(timezone.utc).isoformat()}
        if op=='create':
            from core.commercial.financial_ledger import COLLECTIONS
            ids=[int(r['id']) for key in COLLECTIONS.values() for r in p.get(key,[]) if str(r.get('id','')).isdigit()]
            ids += [int(r['id']) for r in p.get('financial_records',[]) if str(r['id']).isdigit()]
            command['id']=max(ids,default=0)+1
        if op=='reverse':command['reversal_id']=uuid4().hex
        result=ledger_dispatch(p,command)
        self.store.save(project_id,result,expected_digest=__import__('core.platform.concurrency',fromlist=['begin_write']).begin_write({k:v for k,v in p.items() if k!='_meta'}),phase3_command=command)
        if op=='reverse':return result['financial_reversals'][-1]
        return next(r for r in result['financial_records'] if r['id']==command['id'])

    def verified_financial_snapshot(self, project_id):
        from core.commercial.financial_ledger import verified_snapshot
        return verified_snapshot(self.open_project(project_id))

    def verified_financial_report(self, project_id, fmt, path):
        from core.reports.project_report import build_report
        from core.reports.exporters import report_date
        from datetime import date
        p=self.open_project(project_id);snap=self.verified_financial_snapshot(project_id)
        labels={'estimate':'برآورد پایه','budget':'بودجه مصوب','commitments':'تعهدات','actual_cost':'هزینه واقعی','paid':'پرداخت واقعی',
                'received':'دریافت واقعی','debt':'مانده بدهی','unpaid_commitments':'مانده تعهدات','budget_variance':'بودجه منهای هزینه',
                'statement_net':'خالص صورت‌وضعیت‌ها','receivable':'مطالبات','cash_net':'خالص جریان نقد'}
        rows=[{'field':label,'value':snap[k] if snap[k] is not None else snap['missing_message']} for k,label in labels.items()]
        kinds={'budget':'بودجه','commitment':'تعهد','cost':'هزینه','payment':'پرداخت','receipt':'دریافت'}
        for r in snap['documents']:
            rows.extend([{'field':'مرجع سند '+r['reference'],'value':kinds[r['kind']]+' / '+r['counterparty']+' / '+report_date(date.fromisoformat(r['date']))},
                         {'field':'مبلغ سند '+r['reference'],'value':r['amount']},
                         {'field':'منبع سند '+r['reference'],'value':', '.join(d['sha256'] for d in r['source_documents'])}])
        for r in snap['reversals']:rows.append({'field':'مرجع برگشت '+r['reference'],'value':str(r['target_id'])+' / '+r['reason']})
        return build_report(p['name']+' — دفتر مالی و کنترل هزینه',rows,metadata={'project_id':project_id,'currency':snap['currency'],'عنوان بخش':'ریز دفتر مالی و اسناد پشتیبان'}).export(path,fmt)

    @exact
    def verified_statement_report(self, project_id, period_no, fmt, path):
        from core.reports.project_report import build_report
        from core.commercial.statement_amendment import summary
        from core.reports.exporters import report_date
        from datetime import date
        p=self.open_project(project_id);period=self.project_statement_period(project_id,period_no)
        net=summary(p,period_no)
        previous_effective={}
        for prior in p.get('statement_periods',[]):
            if prior['number']<period_no:
                for r in summary(p,prior['number'])['lines']:
                    code=r['price_code'];previous_effective[code]=previous_effective.get(code,number(0,'صفر'))+number(r['net_quantity'],'کارکرد قبلی')
        rows=[]
        for line in period['lines']:
            code=line['code'];effective=next(x['net_quantity'] for x in net['lines'] if x['price_code']==code)
            rows.extend([{'field':'شرح ردیف '+code,'value':line['description']},
                         {'field':'واحد ردیف '+code,'value':__import__('core.reports.exporters',fromlist=['FA_UNITS']).FA_UNITS.get(line['unit'],line['unit'])},
                         {'field':'مقدار قبلی '+code,'value':wire(previous_effective.get(code,number(0,'صفر')))},
                         {'field':'مقدار این دوره '+code,'value':effective},
                         {'field':'مقدار تجمعی مؤثر '+code,'value':wire(previous_effective.get(code,number(0,'صفر'))+number(effective,'کارکرد مؤثر'))},
                         {'field':'مقدار تجمعی اصل سند '+code,'value':line['cumulative_quantity']},
                         {'field':'بهای واحد '+code,'value':line['unit_price']},
                         {'field':'منبع ردیف '+code,'value':', '.join(line.get('source_ids',[])) or 'اصل BOQ محفوظ پروژه'}])
        labels={'gross_current':'ناخالص','retention':'سپرده حسن انجام کار','advance_recovery':'استهلاک پیش‌پرداخت','other_deductions':'سایر کسورات','tax':'مالیات','insurance':'بیمه','payable_current':'خالص قابل پرداخت'}
        for key,label in labels.items():
            rows.append({'field':'مبلغ اصل '+label,'value':net['original'][key]})
            rows.append({'field':'مبلغ اصلاح '+label,'value':net['amendment_deltas'][key]})
            rows.append({'field':'مبلغ مؤثر '+label,'value':net['net'][key]})
        metadata={'project_id':project_id,'currency':p['statement_amendment_policy']['money']['currency'],'شماره دوره':period_no,
                  'شماره قرارداد':period.get('contract_id','در سند اولیه ثبت نشده'),
                  'شماره سند':period.get('reference',str(period_no)),'عنوان بخش':'ریز کارکرد و کسورات صورت‌وضعیت'}
        if period.get('date'):metadata['تاریخ شمسی سند']=report_date(date.fromisoformat(period['date']))
        return build_report(p['name']+' — صورت‌وضعیت دوره '+str(period_no),rows,metadata=metadata).export(path,fmt)

    def configure_statement_workflow(self, project_id, *, actor, expected_version, terms, source_documents):
        return self.statement_workflow(project_id, 'configure', actor=actor, expected_version=expected_version, terms=terms, source_documents=source_documents)

    def statement_workflow(self, project_id, op, *, actor, expected_version, **data):
        from core.commercial.statement import statement_dispatch
        from datetime import datetime, timezone
        from uuid import uuid4
        p=self.open_project(project_id)
        if isinstance(expected_version,bool) or p['_meta']['version']!=expected_version:
            raise RuntimeError('نسخه پروژه تغییر کرده است')
        command={**data,'domain':'statement','op':op,'actor':actor,'at':datetime.now(timezone.utc).isoformat()}
        if op=='create':command['id']=uuid4().hex
        result=statement_dispatch(p,command)
        self.store.save(project_id,result,expected_digest=__import__('core.platform.concurrency',fromlist=['begin_write']).begin_write({k:v for k,v in p.items() if k!='_meta'}),phase3_command=command)
        if op=='configure':return result['statement_workflow_terms']
        return next(d for d in result['statement_workflow'] if d['id']==command['id'])

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
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
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

    @exact
    def project_statement_summary(self, project_id: str) -> dict[str, Any]:
        """Summarize persisted statement periods."""
        periods = self.statement_periods(project_id)
        p=self.open_project(project_id)
        if any(d.get('status')=='POSTED' for d in p.get('statement_amendments',[])):
            from core.commercial.statement_amendment import summary
            money_rows=[summary(p,x['number'])['net'] for x in periods]
        else:money_rows=periods
        return {
            "project_id": project_id,
            "period_count": len(periods),
            "latest_period": periods[-1] if periods else None,
            "gross_total": wire(sum(number(x["gross_current"],"ناخالص") for x in money_rows)),
            "payable_total": wire(sum(number(x["payable_current"],"خالص") for x in money_rows)),
            "retention_total": wire(sum(number(x["retention"],"سپرده") for x in money_rows)),
            "tax_total": wire(sum(number(x["tax"],"مالیات") for x in money_rows)),
        }

    def project_statement_period(self, project_id: str, period_no: int) -> dict[str, Any]:
        """Return one persisted statement period by number."""
        period_no = int(period_no)
        return next((x for x in self.statement_periods(project_id) if int(x.get("number", 0)) == period_no), None) or (_ for _ in ()).throw(KeyError(period_no))

    def project_control_command(self, project_id, op, *, actor, reason, expected_version, **data):
        from copy import deepcopy
        from core.projects.controls import apply
        from core.platform.concurrency import begin_write
        p=self.store.get(project_id)
        if p is None: raise KeyError(project_id)
        if p['_meta']['version'] != expected_version: raise RuntimeError('نسخه پروژه تغییر کرده است')
        clean=deepcopy(p);clean.pop('_meta',None)
        command={'op':op,'actor':actor,'reason':reason,'data':data,'at':datetime.now(timezone.utc).isoformat()}
        updated,result=apply(p,command)
        self.store.save(project_id,updated,expected_digest=begin_write(clean),project_control_command=command)
        return result

    def activity_locations(self, project_id, activity_id):
        from core.projects.locations import targets
        return targets(self,project_id,activity_id)

    def site_command(self, project_id, op, *, actor, reason, expected_version, **data):
        if isinstance(expected_version,bool) or not isinstance(expected_version,int):
            raise ValueError('شماره نسخه معتبر لازم است')
        if op=='purchase_commit':
            from core.projects.controls import apply
            from core.commercial.financial_ledger import ledger_dispatch,COLLECTIONS
            from core.platform.concurrency import begin_write
            p=self.store.get(project_id)
            if p is None:raise KeyError(project_id)
            if p['_meta']['version']!=expected_version:raise RuntimeError('نسخه پروژه تغییر کرده است')
            ids=[int(r['id']) for key in tuple(COLLECTIONS.values())+('financial_records',) for r in p.get(key,[]) if str(r.get('id','')).isdigit()]
            site={'op':'site_purchase_commit','actor':actor,'reason':reason,'data':{**data,'ledger_id':max(ids,default=0)+1},'at':datetime.now(timezone.utc).isoformat()}
            _,link=apply(p,site)
            finance={**{k:link[k] for k in ('amount','currency','counterparty','date','reference','description','source_documents')},'domain':'ledger','op':'create','kind':'commitment','id':link['ledger_id'],'actor':actor,'at':site['at'],'site_purchase':site}
            result=ledger_dispatch(p,finance)
            self.store.save(project_id,result,expected_digest=begin_write({k:v for k,v in p.items() if k!='_meta'}),project_control_command=site,phase3_command=finance)
            return link
        return self.project_control_command(project_id,'site_'+op,actor=actor,reason=reason,expected_version=expected_version,**data)

    def site_lookahead(self, project_id, *, start, days=None, end=None):
        from core.projects.site_resources import lookahead
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return lookahead(p,start=start,days=days,end=end)

    def site_materials(self, project_id, *, as_of, activity_id=None):
        from core.projects.site_materials import snapshot
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return snapshot(p,as_of=as_of,activity_id=activity_id)

    def site_dashboard(self, project_id, *, as_of, days=7, end=None):
        from core.projects.site_dashboard import snapshot
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return snapshot(p,as_of=as_of,days=days,end=end)

    def site_report(self, project_id, kind, fmt, path, *, as_of, days=7, end=None, document_id=None):
        from core.reports.site_operations import export
        return export(self,project_id,kind,fmt,path,as_of=as_of,days=days,end=end,document_id=document_id)

    def site_package_candidates(self, project_id):
        from core.projects.site_office import package_candidates
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return package_candidates(p)

    def project_controls_report(self, project_id, kind, fmt, path, *, as_of=None):
        from core.reports.project_controls import export
        return export(self,project_id,kind,fmt,path,as_of=as_of)

    def project_progress(self, project_id, *, as_of):
        from core.projects.physical_progress import calculate
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return calculate(p,as_of=as_of)

    def project_progress_curve(self, project_id, *, frequency='daily'):
        from core.projects.physical_progress import curve
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return curve(p,frequency)

    def project_schedule(self, project_id):
        from core.projects.scheduling import current
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return current(p)

    def project_controls(self, project_id):
        from core.projects.controls import snapshot
        p=self.store.get(project_id)
        if p is None:raise KeyError(project_id)
        return snapshot(p)

    def project_management_snapshot(self, project_id: str, *, as_of: str | None = None) -> dict[str, Any]:
        """Return a read-only operational management dashboard for a project."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        def _load(cls, key):
            return [cls(**{k:v for k,v in row.items() if k in cls.__dataclass_fields__}) for row in p.get(key, [])]
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
        digest=self.store.current_digest(project_id)
        self.store._cache.pop(project_id,None)
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
        self.store.save(project_id, p, expected_digest=digest)
        return self.project_management_snapshot(project_id)

    def project_activity_summary(self, project_id: str) -> dict[str, Any]:
        """Provide a compact project activity inventory for dashboards."""
        p = self.store.get(project_id)
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
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
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
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
        amount = number(amount, 'مبلغ')
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
            "amount": wire(amount),
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
        from core.commercial.financial_ledger import financial_projection
        return list(financial_projection(p).get("cost_entries", []))

    @exact
    def project_cost_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_costs(project_id)
        by_category = {}
        for entry in entries:
            category = str(entry.get("category", "سایر"))
            by_category[category] = by_category.get(category, 0) + number(entry.get('amount'), 'مبلغ هزینه')
        return wire({
            "project_id": project_id,
            "entry_count": len(entries),
            "actual_cost": sum(by_category.values()),
            "by_category": by_category,
        })

    def project_financial_control(self, project_id: str, *, planned_cost: float | None = None,
                                  actual_cost: float = 0.0) -> dict[str, Any]:
        """Calculate cost variance indicators from explicit project cost inputs."""
        if actual_cost < 0 or (planned_cost is not None and planned_cost < 0):
            raise ValueError("cost values cannot be negative")
        dashboard = self.financial_dashboard(project_id)
        if dashboard["contract_amount"] is None or dashboard["cumulative_work"] is None:
            raise ValueError("برای شاخص‌های ارزش کسب‌شده و پیشرفت، BOQ و برآورد تأییدشده الزامی است")
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

    @exact
    def financial_dashboard(self, project_id: str) -> dict[str, Any]:
        """Return a compact financial/progress snapshot for the project dashboard."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        boq = p.get("boq", []) or []
        # Cost / receipts / commitments can exist before the first BOQ item.
        # Such a project has no *known* contract or earned-value figures.
        # In particular, missing estimates must never be silently valued at 0.
        # Independent cost/receipt/commitment ledgers remain viewable when
        # physical BOQ exists but has no approved, traceable pricebook.
        # Never infer a contract, margin or earned value from an unreviewed rate.
        estimate = None
        blocked_reason = None
        if boq:
            from core.reports.aec_office_package import audit_boq
            try:
                audit_boq(p, require_pricebook=True)
            except ValueError as exc:
                blocked_reason = str(exc)
            else:
                estimate = p.get("estimate") or self.recalculate_estimate(project_id)
        cost = (estimate.get("cost", {}) or {}) if estimate else {}
        contract = number(cost['grand_total'],'برآورد') if estimate else None
        base = number(cost['base'],'مبنا') if estimate else None
        snapshot = self.build_commercial_snapshot(project_id) if estimate else {}
        progress = snapshot.get("progress", {}) or {}
        periods = list(p.get("statement_periods", []))
        latest = periods[-1] if periods else None
        cumulative = number(progress.get('completed_total',0),'کارکرد') if estimate else None
        if estimate and latest is not None:
            cumulative = number(latest.get('completed_total',cumulative),'کارکرد')
        remaining = max(contract - cumulative, 0.0) if estimate else None
        percent = display_percent(cumulative,contract) if estimate and contract else (0.0 if estimate else None)
        total_payable = sum(number(x.get('payable_current',0),'پرداختنی') for x in periods)
        if any(d.get('status') == 'POSTED' for d in p.get('statement_amendments', [])):
            from core.commercial.statement_amendment import summary
            net_periods = [summary(p, period['number'])['net'] for period in periods]
            cumulative = sum(number(net['gross_current'],'کارکرد') for net in net_periods)
            total_payable = sum(number(net['payable_current'],'پرداختنی') for net in net_periods)
            remaining = max(contract - cumulative, 0.0) if estimate else None
            percent = display_percent(cumulative,contract) if estimate and contract else (0.0 if estimate else None)
        cost_summary = self.project_cost_summary(project_id)
        actual_cost = number(cost_summary['actual_cost'],'هزینه')
        gross_margin = cumulative - actual_cost if estimate else None
        return wire({
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
            "latest_payable": (number(net_periods[-1]['payable_current'],'پرداختنی') if any(d.get("status") == "POSTED" for d in p.get("statement_amendments", [])) else number(latest.get('payable_current',0),'پرداختنی')) if latest else 0.0,
            "total_payable": total_payable,
            "actual_cost": actual_cost,
            "gross_margin": gross_margin,
            "cost_entry_count": cost_summary["entry_count"],
            "cost_by_category": cost_summary["by_category"],
            "warnings": (list(estimate.get("warnings") or []) if estimate else
                         ["برآورد قرارداد در دسترس نیست؛ BOQ تأییدشده ثبت نشده است"
                          if not boq else "برآورد تأییدشده در دسترس نیست؛ " +
                          (blocked_reason or "فهرست‌بهای معتبر لازم است")]),
            "estimate_status": "verified" if estimate else "unavailable",
        })

    def _finance_depth_control(self, project_id: str) -> FinancePaymentControl:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.commercial.financial_ledger import financial_projection
        p=financial_projection(p)
        payments = [
            PaymentRecord(
                id=str(x.get("id")),
                amount=number(x.get("amount"),"پرداخت"),
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
                amount=number(x.get("amount"),"پرداخت"),
            )
            for x in p.get("payment_allocations", [])
        ]
        budget = [
            BudgetLine(
                code=str(x.get("code")),
                category=str(x.get("category", "")),
                description=str(x.get("description", "")),
                planned=number(x.get("planned"),"بودجه"),
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
            "id": payment_id, "amount": wire(number(amount,"پرداخت")), "date": str(date).strip(),
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
            target_id=target_id, amount=wire(number(amount,"پرداخت")),
        )
        control.allocate(allocation)
        records = list(p.get("payment_allocations", []))
        row = {
            "id": allocation_id, "payment_id": str(payment_id), "target_type": str(target_type),
            "target_id": target_id, "amount": wire(number(amount,"پرداخت")),
        }
        records.append(row)
        p["payment_allocations"] = records
        self.store.save(project_id, p)
        return row

    def project_payments(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.commercial.financial_ledger import financial_projection
        return list(financial_projection(p).get("payment_entries", []))

    def project_payment_summary(self, project_id: str) -> dict[str, Any]:
        return self._finance_depth_control(project_id).payment_summary()

    def add_financial_budget_line(self, project_id: str, code: str, category: str,
                                  planned: float, *, description: str = "") -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        records = list(p.get("financial_budget", []))
        row = {"code": str(code).strip(), "category": str(category).strip(),
               "description": str(description).strip(), "planned": wire(number(planned,"بودجه"))}
        candidate = FinancePaymentControl(budget=[
            BudgetLine(str(x.get("code")), str(x.get("category", "")), str(x.get("description", "")),
                       number(x.get("planned"),"بودجه")) for x in records + [row]
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
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
        if p is None:
            raise KeyError(project_id)
        return self._finance_depth_control(project_id).budget_control(
            actual_costs=p.get("cost_entries", []),
            commitments=p.get("commitment_entries", []),
        )

    def project_cash_flow_control(self, project_id: str) -> dict[str, Any]:
        p = self.store.get(project_id)
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
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
        from core.commercial.financial_ledger import financial_projection
        if p is not None:p=financial_projection(p)
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
        amount = number(amount, 'مبلغ')
        paid_amount = number(paid_amount, 'پرداخت تعهد')
        if amount < 0 or paid_amount < 0 or paid_amount > amount:
            raise ValueError("invalid commitment amount")
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        entries = list(p.get("commitment_entries", []))
        entry = {"id": len(entries) + 1, "amount": wire(amount), "paid_amount": wire(paid_amount), "category": str(category).strip() or "سایر", "description": str(description).strip(), "date": str(date).strip(), "due_date": str(due_date).strip(), "reference": str(reference).strip(), "document_id": int(document_id) if document_id is not None else None, "counterparty": str(counterparty).strip(), "counterparty_id": self._counterparty_id_for_name(p, counterparty)}
        entries.append(entry)
        p["commitment_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def project_commitments(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.commercial.financial_ledger import financial_projection
        return list(financial_projection(p).get("commitment_entries", []))

    @exact
    def project_commitment_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_commitments(project_id)
        total = sum(number(x.get('amount'), 'مبلغ') for x in entries)
        paid = sum(number(x.get('paid_amount'), 'پرداخت تعهد') for x in entries)
        p=self.open_project(project_id)
        if p.get('financial_records'):
            from core.commercial.financial_ledger import active_records
            paid+=sum((number(r['amount'],'پرداخت تعهد') for r in active_records(p) if r['kind']=='payment' and r.get('commitment_id')),number(0,'صفر'))
        return wire({"project_id": project_id, "entry_count": len(entries), "committed_total": total, "paid_total": paid, "unpaid_total": max(total - paid, 0)})

    def add_project_receipt(self, project_id: str, amount: float, *, description: str = "", date: str = "", reference: str = "", document_id: int | None = None, counterparty: str = "") -> dict[str, Any]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        amount = number(amount, 'مبلغ')
        if amount < 0:
            raise ValueError("receipt amount cannot be negative")
        if document_id is not None and not any(int(x.get("id", 0)) == int(document_id) for x in p.get("financial_documents", [])):
            raise KeyError(f"financial document {document_id}")
        entries = list(p.get("receipt_entries", []))
        entry = {"id": len(entries) + 1, "amount": wire(amount), "description": str(description).strip(), "date": str(date).strip(), "reference": str(reference).strip(), "document_id": int(document_id) if document_id is not None else None, "counterparty": str(counterparty).strip(), "counterparty_id": self._counterparty_id_for_name(p, counterparty)}
        entries.append(entry)
        p["receipt_entries"] = entries
        self.store.save(project_id, p)
        return entry

    def project_receipts(self, project_id: str) -> list[dict[str, Any]]:
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.commercial.financial_ledger import financial_projection
        return list(financial_projection(p).get("receipt_entries", []))

    @exact
    def project_receipt_summary(self, project_id: str) -> dict[str, Any]:
        entries = self.project_receipts(project_id)
        return wire({"project_id": project_id, "entry_count": len(entries), "total_received": sum(number(x.get('amount'), 'مبلغ') for x in entries)})

    @exact
    def project_financial_position(self, project_id: str) -> dict[str, Any]:
        dashboard = self.financial_dashboard(project_id)
        receipts = self.project_receipt_summary(project_id)
        commitments = self.project_commitment_summary(project_id)
        contract = (number(dashboard["contract_amount"],"مبلغ")
                    if dashboard["contract_amount"] is not None else None)
        received = number(receipts["total_received"],"مبلغ")
        receivable = max(contract - received, 0.0) if contract is not None else None
        committed = number(commitments["committed_total"],"مبلغ")
        return wire({
            "project_id": project_id, "contract_amount": contract,
            "earned_value": (number(dashboard["cumulative_work"],"مبلغ")
                             if dashboard["cumulative_work"] is not None else None),
            "actual_cost": number(dashboard["actual_cost"],"مبلغ"),
            "received": received, "receivable": receivable,
            "committed_cost": committed, "unpaid_commitments": number(commitments["unpaid_total"],"مبلغ"),
            "cash_exposure": max(committed - received, 0.0),
            "cost_margin": (number(dashboard["gross_margin"],"مبلغ",True)
                            if dashboard["gross_margin"] is not None else None),
            "receipt_count": receipts["entry_count"],
            "commitment_count": commitments["entry_count"],
        })

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
            "شرح": entry.get("description") or entry.get("category", ""),
            "تاریخ": entry.get("date", ""),
            "مبلغ": entry.get("amount"),
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


    @exact
    def project_counterparty_financial_rollup(self, project_id: str) -> list[dict[str, Any]]:
        """Aggregate financial activity by stable counterparty ID, including legacy name-only records."""
        p = self.store.get(project_id)
        if p is None:
            raise KeyError(project_id)
        from core.commercial.financial_ledger import financial_projection
        p = financial_projection(p)
        parties = self.project_counterparties(project_id)
        rows = {x['id']: {'counterparty_id': x['id'], 'name': x.get('name', ''), 'role': x.get('role', ''), 'active': x.get('active', True), 'documents': 0, 'document_amount': 0, 'commitments': 0, 'commitment_amount': 0, 'paid_commitments': 0, 'costs': 0, 'cost_amount': 0, 'receipts': 0, 'receipt_amount': 0} for x in parties}
        for coll, key, count, amount in [('financial_documents', 'documents', 'document_amount', 'amount'), ('commitment_entries', 'commitments', 'commitment_amount', 'amount'), ('cost_entries', 'costs', 'cost_amount', 'amount'), ('receipt_entries', 'receipts', 'receipt_amount', 'amount')]:
            for item in p.get(coll, []):
                cid = item.get('counterparty_id') or self._counterparty_id_for_name(p, item.get('counterparty', ''))
                if cid not in rows:
                    continue
                rows[cid][key] += 1
                target_key = {'amount': 'document_amount'}.get(amount, amount)
                if coll == 'commitment_entries':
                    target_key = 'commitment_amount'
                elif coll == 'cost_entries':
                    target_key = 'cost_amount'
                elif coll == 'receipt_entries':
                    target_key = 'receipt_amount'
                rows[cid][target_key] += number(item.get('amount', 0) or 0, 'مبلغ', True)
                if coll == 'commitment_entries':
                    rows[cid]['paid_commitments'] += number(item.get('paid_amount', 0) or 0, 'مبلغ', True)
        for payment in p.get('payment_entries', []):
            if payment.get('commitment_id') is None:
                continue
            cid = payment.get('counterparty_id') or self._counterparty_id_for_name(p, payment.get('counterparty', ''))
            if cid in rows:
                rows[cid]['paid_commitments'] += number(payment['amount'], 'پرداخت')
        return wire(sorted(rows.values(), key=lambda x: (not bool(x['active']), str(x['name']).casefold())))

    @exact
    def project_counterparty_summary(self, project_id: str) -> dict[str, Any]:
        """Aggregate project financial exposure by counterparty."""
        p = self.store.get(project_id)
        from core.commercial.financial_ledger import financial_projection
        if p is not None:
            p = financial_projection(p)
        if p is None:
            raise KeyError(project_id)
        result: dict[str, dict[str, Any]] = {}

        def bucket(name: str) -> dict[str, Any]:
            key = str(name or '').strip() or 'نامشخص'
            return result.setdefault(key, {'counterparty': key, 'documents': 0, 'document_amount': 0, 'commitments': 0, 'committed_amount': 0, 'paid_commitments': 0, 'cost_entries': 0, 'actual_cost': 0, 'receipts': 0, 'received': 0})
        for d in p.get('financial_documents', []):
            b = bucket(d.get('counterparty', ''))
            b['documents'] += 1
            b['document_amount'] += number(d.get('amount', 0) or 0, 'مبلغ', True)
        for c in p.get('commitment_entries', []):
            b = bucket(c.get('counterparty', ''))
            b['commitments'] += 1
            b['committed_amount'] += number(c.get('amount', 0) or 0, 'مبلغ', True)
            b['paid_commitments'] += number(c.get('paid_amount', 0) or 0, 'مبلغ', True)
        for c in p.get('cost_entries', []):
            b = bucket(c.get('counterparty', ''))
            b['cost_entries'] += 1
            b['actual_cost'] += number(c.get('amount', 0) or 0, 'مبلغ', True)
        for r in p.get('receipt_entries', []):
            b = bucket(r.get('counterparty', ''))
            b['receipts'] += 1
            b['received'] += number(r.get('amount', 0) or 0, 'مبلغ', True)
        for payment in p.get('payment_entries', []):
            if payment.get('commitment_id') is not None:
                bucket(payment.get('counterparty', ''))['paid_commitments'] += number(payment['amount'], 'پرداخت')
        for b in result.values():
            b['unpaid_commitments'] = max(b['committed_amount'] - b['paid_commitments'], 0)
            b['net_cash'] = b['received'] - b['paid_commitments']
        return wire({'project_id': project_id, 'counterparties': list(result.values()), 'counterparty_count': len(result)})

    def project_counterparty_ledger_by_id(self, project_id: str, counterparty_id: str) -> dict[str, Any]:
        """Return a detailed ledger using the stable counterparty ID."""
        party = self.find_project_counterparty_by_id(project_id, counterparty_id)
        if party is None:
            raise KeyError(counterparty_id)
        return self.project_counterparty_ledger(project_id, party["name"])

    @exact
    def project_counterparty_ledger(self, project_id: str, counterparty: str) -> dict[str, Any]:
        """Return chronological financial activity for one project counterparty."""
        p = self.store.get(project_id)
        from core.commercial.financial_ledger import financial_projection
        if p is not None:
            p = financial_projection(p)
        if p is None:
            raise KeyError(project_id)
        name = str(counterparty).strip()
        if not name:
            raise ValueError('counterparty cannot be empty')
        rows = []

        def add(source: str, entry: dict[str, Any], amount: float, direction: str):
            rows.append({'source': source, 'id': entry.get('id', ''), 'date': entry.get('date', ''), 'reference': entry.get('reference', ''), 'description': entry.get('description', ''), 'amount': number(amount, 'مبلغ', True), 'direction': direction, 'cash_in': number(amount, 'مبلغ', True) if direction == 'in' else 0, 'cash_out': number(amount, 'مبلغ', True) if direction == 'out' else 0, 'document_id': entry.get('document_id')})
        for entry in p.get('financial_documents', []):
            if str(entry.get('counterparty', '')).strip() == name:
                add('سند مالی', entry, entry.get('amount', 0), 'info')
        for entry in p.get('commitment_entries', []):
            if str(entry.get('counterparty', '')).strip() == name:
                add('تعهد', entry, entry.get('amount', 0), 'info')
                if number(entry.get('paid_amount',0),'پرداخت قدیمی'):
                    add('پرداخت تعهد قدیمی',entry,entry['paid_amount'],'out')
        for entry in p.get('cost_entries', []):
            if str(entry.get('counterparty', '')).strip() == name:
                add('هزینه', entry, entry.get('amount', 0), 'info')
        for entry in p.get('payment_entries', []):
            if str(entry.get('counterparty', '')).strip() == name:
                add('پرداخت', entry, entry.get('amount', 0), 'out')
        for entry in p.get('receipt_entries', []):
            if str(entry.get('counterparty', '')).strip() == name:
                add('دریافتی', entry, entry.get('amount', 0), 'in')
        rows.sort(key=lambda x: (str(x.get('date', '')), str(x.get('source', '')), str(x.get('id', ''))))
        cash_in = sum((x['cash_in'] for x in rows))
        cash_out = sum((x['cash_out'] for x in rows))
        return wire({'project_id': project_id, 'counterparty': name, 'rows': rows, 'row_count': len(rows), 'cash_in': cash_in, 'cash_out': cash_out, 'net_cash': cash_in - cash_out})

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

    @exact
    def project_financial_due_summary(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Compact due-date control summary suitable for dashboard cards."""
        aging=self.project_financial_aging(project_id,as_of)
        return {
            "project_id":project_id, "as_of":aging["as_of"],
            "overdue_count":aging["overdue_count"], "overdue_amount":aging["overdue_amount"],
            "due_today_count":aging["due_today_count"], "upcoming_count":aging["upcoming_count"],
            "no_due_date_count":aging["no_due_date_count"],
            "total_open_amount":wire(sum(number(x.get("outstanding",0) or 0,"مانده") for x in aging["rows"])),
            "highest_risk":aging["rows"][0] if aging["rows"] else None,
        }

    @exact
    def project_financial_aging(self, project_id: str, as_of: str) -> dict[str, Any]:
        """Return deterministic due-date aging for unpaid project financial items.

            The caller supplies the reporting date explicitly. This avoids mixing the
            project's Jalali date strings with the machine's Gregorian clock.
            """
        p = self.store.get(project_id)
        from core.commercial.financial_ledger import financial_projection
        if p is not None:
            p = financial_projection(p)
        if p is None:
            raise KeyError(project_id)
        as_of_key = _normalize_date_key(as_of)
        if as_of_key is None:
            raise ValueError('invalid aging date; expected YYYY/MM/DD')
        rows = []

        def classify(due_date: str) -> str:
            due_key = _normalize_date_key(due_date)
            if due_key is None:
                return 'بدون سررسید'
            if due_key < as_of_key:
                return 'معوق'
            if due_key == as_of_key:
                return 'سررسید امروز'
            return 'آتی'
        for entry in p.get('commitment_entries', []):
            amount = number(entry.get('amount', 0) or 0, 'مبلغ', True)
            paid = number(entry.get('paid_amount', 0) or 0, 'مبلغ', True)
            paid+=sum((number(r['amount'],'پرداخت') for r in p.get('payment_entries',[]) if r.get('commitment_id')==entry['id']),number(0,'صفر'))
            outstanding = max(amount - paid, 0)
            if outstanding <= 0:
                continue
            due_date = str(entry.get('due_date', '')).strip()
            status = classify(due_date)
            rows.append({'source': 'تعهد', 'id': entry.get('id', ''), 'counterparty': entry.get('counterparty', ''), 'reference': entry.get('reference', ''), 'due_date': due_date, 'status': status, 'amount': amount, 'paid_amount': paid, 'outstanding': outstanding})
        for entry in p.get('financial_documents', []):
            payment_status = str(entry.get('payment_status', 'unpaid')).strip().lower()
            if payment_status == 'paid':
                continue
            amount = number(entry.get('amount', 0) or 0, 'مبلغ', True)
            due_date = str(entry.get('due_date', '')).strip()
            status = classify(due_date)
            rows.append({'source': 'سند مالی', 'id': entry.get('id', ''), 'counterparty': entry.get('counterparty', ''), 'reference': entry.get('document_number', ''), 'due_date': due_date, 'status': status, 'amount': amount, 'paid_amount': None, 'outstanding': amount if payment_status == 'unpaid' else None})
        order = {'معوق': 0, 'سررسید امروز': 1, 'آتی': 2, 'بدون سررسید': 3}
        rows.sort(key=lambda x: (order.get(x['status'], 9), _normalize_date_key(x['due_date']) or '9999/99/99', str(x['source']), int(x.get('id', 0) or 0)))
        overdue_commitments = sum((x['outstanding'] for x in rows if x['source'] == 'تعهد' and x['status'] == 'معوق'))
        overdue_unpaid_documents = sum((x['outstanding'] or 0 for x in rows if x['source'] == 'سند مالی' and x['status'] == 'معوق'))
        return wire({'project_id': project_id, 'as_of': as_of_key, 'rows': rows, 'row_count': len(rows), 'overdue_count': sum((1 for x in rows if x['status'] == 'معوق')), 'due_today_count': sum((1 for x in rows if x['status'] == 'سررسید امروز')), 'upcoming_count': sum((1 for x in rows if x['status'] == 'آتی')), 'no_due_date_count': sum((1 for x in rows if x['status'] == 'بدون سررسید')), 'overdue_commitments': overdue_commitments, 'overdue_unpaid_documents': overdue_unpaid_documents, 'overdue_amount': overdue_commitments + overdue_unpaid_documents})

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
                "مبلغ": entry.get("amount"),
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
                "مبلغ": entry.get("amount"),
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
                "مبلغ": entry.get("amount"),
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
                "مبلغ": entry.get("amount"),
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
        from core.reports.aec_office_package import audit_boq
        audit_boq(p, require_pricebook=True)
        estimate=p.get("estimate") or self.recalculate_estimate(project_id)
        selected=None
        periods=p.get("statement_periods",[])
        if period_no is not None:
            selected=next((x for x in periods if int(x.get("number",0))==int(period_no)),None)
            if selected is None: raise KeyError(f"statement period {period_no}")
        if selected is None:
            if any(row.get("current_quantity") is None for row in p.get("boq", [])):
                # An estimate is reportable without inventing unknown period work.
                # Only an explicit current-period input can produce a statement.
                summary = {**estimate.get("cost", {}),
                           "statement_status": "کارکرد دوره وارد نشده است"}
                rows = [{"کد": row.get("price_code", ""), "شرح": row.get("description", ""),
                         "واحد": row.get("unit", ""), "مقدار قرارداد": row["quantity"],
                         "قیمت واحد": row["unit_price"], "مبلغ قرارداد": row["total"],
                         "منابع متره": "، ".join(row.get("source_ids", []))}
                        for row in p.get("boq", [])]
                return build_report(p.get("name", ""), rows, summary).export(path, fmt)
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
