"""Phase 6 / P4 (W1+A2): governed stepwise takeoff and contextual engineering advice.

This adapter never guesses a dimension, pays an AI proposal, or owns new
project data. Quantity previews delegate exclusively to the existing
AssemblyTemplateLibrary. Financial writes use the existing reviewed CAS service.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any

from core.takeoff.assembly_templates import AssemblyTemplateLibrary


# Existing, tested assemblies only; these are prompts, NOT implied quantities.
COMPANIONS = {
    "joist_foam_roof_assembly": ("ceiling_paint", "floor_screed", "waterproofing_floor"),
    "joist_block_roof_assembly": ("ceiling_paint", "floor_screed", "waterproofing_floor"),
    "concrete_slab": ("floor_screed", "ceiling_paint", "waterproofing_floor"),
    "block_wall": ("gypsum_scratch", "gypsum_finish", "wall_paint", "wall_tile"),
    "floor_screed": ("floor_tile", "waterproofing_floor"),
    "floor_tile": ("skirting",),
    "concrete_beam": ("rebar",),
    "concrete_column": ("rebar",),
    "false_ceiling": ("ceiling_paint",),
}
SPECIALIST_ONLY = {
    "waffle_one_way": "دیتایل سقف وافل یک‌طرفه",
    "waffle_two_way": "دیتایل سقف وافل دوطرفه",
    "hollowcore": "دیتایل هالوکور",
    "mep_pipe": "فرم تخصصی تأسیسات مکانیکی",
    "mep_electrical": "فرم تخصصی تأسیسات برقی",
}


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("ورودی معتبر برای " + label + " الزامی است.")
    return value


def _digest_file(path):
    p = Path(path)
    if not p.is_file():
        raise ValueError("فایل مستند انتخاب‌شده در دسترس نیست.")
    h = sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass(frozen=True)
class ContextualPreview:
    code: str
    title: str
    missing: tuple[str, ...]
    components: tuple[dict, ...]
    companions: tuple[dict, ...]
    blockers: tuple[str, ...]
    project_digest: str
    ready_to_review: bool
    financial_approved: bool = False


class GovernedTakeoffAssistant:
    """Explicit user context and reusable services, read-only until commit."""

    def __init__(self, service, project_id, *, floor_id="", member_id="",
                 document_path="", document_sha256="", revision="", global_id=""):
        self.service = service
        self.project_id = _text(project_id, "شناسه پروژه")
        self.floor_id = str(floor_id or "").strip()
        self.member_id = str(member_id or "").strip()
        self.document_path = str(document_path or "").strip()
        self.document_sha256 = str(document_sha256 or "").strip()
        self.revision = str(revision or "").strip()
        self.global_id = str(global_id or "").strip()
        self.library = AssemblyTemplateLibrary()
        self.disabled = False
        self.cancelled = False
        self._snapshot = None
        if self.document_path:
            if not self.document_sha256 or _digest_file(self.document_path) != self.document_sha256:
                raise ValueError("SHA-256 منبع نقشه معتبر نیست.")
        elif self.document_sha256 or self.global_id or self.revision:
            raise ValueError("سند واقعی برای زمینه IFC/Revision الزامی است.")
        self._checked_project()

    def _checked_project(self):
        if self.disabled or self.cancelled:
            raise RuntimeError("دستیار غیرفعال یا لغو شده است.")
        project = self.service.open_project(self.project_id)
        if not isinstance(project, dict) or project.get("id") != self.project_id:
            raise KeyError("پروژه واقعی در SQLite پیدا نشد.")
        digest = self.service.store.current_digest(self.project_id)
        if not digest:
            raise ValueError("نسخه CAS پروژه موجود نیست.")
        floors = project.get("floors") or []
        members = project.get("members") or []
        if not isinstance(floors,list) or not isinstance(members,list):
            raise ValueError("ساختار پروژه معتبر نیست.")
        if self.floor_id and not any(x.get("id") == self.floor_id for x in floors):
            raise ValueError("طبقه انتخاب‌شده در پروژه واقعی نیست.")
        if self.member_id:
            found=[m for m in members if m.get("id")==self.member_id]
            if len(found) != 1 or (self.floor_id and found[0].get("floor_id")!=self.floor_id):
                raise ValueError("عضو و طبقه با داده پروژه مطابقت ندارند.")
        if self.document_path and _digest_file(self.document_path)!=self.document_sha256:
            raise RuntimeError("سند نقشه بعد از انتخاب تغییر کرده است.")
        return project, digest

    def disable(self):
        self.disabled = True
        self._snapshot = None

    def cancel(self):
        self.cancelled = True
        self._snapshot = None

    def reset(self):
        self.cancelled = False
        self.disabled = False
        self._snapshot = None

    def _existing_conflicts(self, project, code, source):
        clashes=[]
        for assembly in project.get("takeoff_assemblies",[]) or []:
            if not isinstance(assembly,dict):
                raise ValueError("دفتر اسمبلی واقعی ساختار معتبر ندارد.")
            same_floor = assembly.get("floor_id") == self.floor_id
            same_code = assembly.get("assembly_code") == code
            if same_floor and same_code and (
                (source and assembly.get("measurement_source")==source)
                or (self.member_id and assembly.get("location_id")==self.member_id)
            ):
                clashes.append("عملیات همین اسمبلی برای محل/عضو قبلاً ثبت شده؛ ثبت دوباره ممنوع است.")
        return tuple(sorted(set(clashes)))

    def preview(self, code, inputs=None, *, measurement_source=""):
        """Rules only; every missing item is shown, none is silently supplied."""
        project,digest=self._checked_project()
        code=_text(code,"خانواده متره")
        values=dict(inputs or {})
        if not isinstance(inputs if inputs is not None else {}, dict):
            raise ValueError("ورودی‌های متره باید از فرم صریح کاربر باشند.")
        if code in SPECIALIST_ONLY:
            self._snapshot = None
            return ContextualPreview(code,SPECIALIST_ONLY[code],(),(),(),
                ("برای این خانواده فقط فرم تخصصی موجود معتبر است؛ اسمبلی عمومی ساخته نمی‌شود.",),
                digest,False)
        template=self.library.get(code)
        if any(isinstance(v,float) for v in values.values()):
            raise ValueError("ورودی float دودویی پذیرفته نمی‌شود؛ مقدار صریح متنی/Decimal وارد کنید.")
        unknown = set(values)-set(template.required_inputs)-set(template.optional_inputs)
        if unknown:
            raise ValueError("پارامتر غیرمجاز: "+", ".join(sorted(unknown)))
        missing=tuple(x for x in template.required_inputs
                      if x not in values or values[x] is None or values[x] == "")
        # Do not calculate partial assemblies, especially with unknown openings.
        components=()
        if not missing:
            result=self.library.expand(code,values)
            missing=result.missing_inputs
            components=tuple(dict(code=c.code,title=c.title,unit=c.unit,formula=c.formula,
                                  quantity=str(Decimal(str(c.quantity))),source=c.source,
                                  warning=c.warning) for c in result.components)
        companions=tuple(dict(code=c,title=self.library.get(c).title_fa,
                        status="پیشنهاد بررسی، بدون مقدار") for c in COMPANIONS.get(code,()))
        source=str(measurement_source or "").strip()
        blockers=list(self._existing_conflicts(project,code,source))
        if not self.floor_id: blockers.append("طبقه یا ناحیه واقعی هنوز انتخاب نشده است.")
        if not source: blockers.append("شناسه برداشت/محل صریح برای ثبت لازم است.")
        if not self.member_id: blockers.append("عضو واقعی انتخاب نشده؛ مالکیت عضو برای پیشنهاد قطعی نیست.")
        ready=bool(not missing and not blockers and components)
        self._snapshot = (digest, code, deepcopy(values), source) if ready else None
        return ContextualPreview(code,template.title_fa,missing,components,companions,
                                 tuple(blockers),digest,ready)

    def advise(self, question, *, code="", inputs=None, measurement_source=""):
        """A2: deterministic offline recommendations; NEVER invent a numeric answer."""
        project,digest=self._checked_project()
        q=_text(question,"پرسش")
        if code:
            p=self.preview(code,inputs,measurement_source=measurement_source)
            missing="، ".join(p.missing) if p.missing else "ورودی اجباری باقی نمانده است"
            items="، ".join(x["title"] for x in p.companions) or "مورد وابسته مشخص نشده است"
            msg=("گام بعدی: بررسی ورودی‌های مفقود: "+missing+
                 ". اقلام مرتبط برای بازبینی مستقل: "+items+
                 ". پیشنهادها مقدار یا قیمت ندارند؛ ثبت تنها پس از تأیید مجاز است.")
        else:
            msg="برای پیشنهاد دقیق، خانواده متره و زمینه معتبر عضو و طبقه را انتخاب کنید."
        if any(x in q.casefold() for x in ("چقدر","مقدار","عدد","قیمت","هزینه","total","sum","quantity")):
            msg += " پاسخ عددی قطعی صرفاً از ردیف‌های تأییدشده BOQ/Decimal ممکن است؛ در این درخواست عددی استنتاج نمی‌شود."
        return {"text":msg,"offline":True,"deterministic":True,
                "project_id":self.project_id,"project_digest":digest,
                "floor_id":self.floor_id,"member_id":self.member_id,
                "source_sha256":self.document_sha256,"revision":self.revision,
                "global_id":self.global_id,"requires_confirmation":True,
                "commit_allowed":False}

    def commit(self, *, code, inputs, measurement_source, approver, expected_digest):
        """Only explicit approval, exact preview and CAS may invoke existing service."""
        project,digest=self._checked_project()
        if not self._snapshot or digest!=expected_digest or digest!=self._snapshot[0]:
            raise RuntimeError("پیش‌نمایش منقضی شده؛ ورودی و نسخه پروژه را دوباره بررسی کنید.")
        if (code,inputs,str(measurement_source).strip()) != (
            self._snapshot[1],self._snapshot[2],self._snapshot[3]):
            raise RuntimeError("ورودی یا منبع پس از پیش‌نمایش تغییر کرده است.")
        if not self.member_id or not self.floor_id:
            raise ValueError("مالک و طبقه واقعی برای ثبت الزامی است.")
        reviewer=_text(approver,"تأییدکننده")
        collab=getattr(self.service,"collaboration",None)
        user=collab.users.get(reviewer) if collab is not None else None
        if user is None or not collab.roles[user.role].allows("approve"):
            raise PermissionError("تأییدکننده باید کاربر ثبت‌شده با مجوز approve باشد.")
        check=self.preview(code,inputs,measurement_source=measurement_source)
        if not check.ready_to_review:
            raise ValueError("پیشنهاد فاقد قابلیت ثبت امن است.")
        self._snapshot = None
        return self.service.add_assembly_takeoff(
            self.project_id,code,deepcopy(inputs),floor_id=self.floor_id,
            measurement_source=str(measurement_source).strip(),
            approved_by=reviewer,location_id=self.member_id)
