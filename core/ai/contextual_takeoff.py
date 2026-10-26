"""Phase 6 W1/A2: deterministic, read-only contextual takeoff guidance.

Reuse the accepted assembly templates and canonical SQLite application, NOT a
second takeoff engine. Never infer dimensions, pricing, assembly factors, or
member identity. Proposal review is presentation-only, not BOQ acceptance.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from typing import Mapping

from core.takeoff.assembly_templates import AssemblyTemplateLibrary

# Links below are *review questions*, not automatically activated / payable
# components. Labels and inputs come from the existing specialist templates.
_FAMILY_TEMPLATES = {
    "joist_block": ("joist_foam_roof_assembly",),  # only when actually foam
    "joist_foam": ("joist_foam_roof_assembly",),
    "solid_slab": ("concrete_slab",),
    "block_wall": ("block_wall",),
    "wall_with_opening": ("block_wall",),
    "waffle_one_way": (),
    "waffle_two_way": (),
    "mep": (),
    "floor_finish": ("floor_finish",),
    "false_ceiling": ("false_ceiling",),
}
_QUESTIONS = {
    "joist_block": ("جهت تیرچه", "نوع بلوک پرکننده", "تعداد و ابعاد تیرچه", "تعداد و ابعاد بلوک", "بتن رویه", "میلگرد حرارتی", "بازشوها و کسورات", "مالکیت اجزای مشترک"),
    "joist_foam": ("جهت تیرچه", "ابعاد و تعداد یونولیت", "تیرچه و فاصله واقعی", "بتن رویه", "میلگرد حرارتی با دیتایل", "بازشوها و کسورات", "مالکیت اجزای مشترک"),
    "solid_slab": ("ابعاد و ضخامت دال", "بازشوها", "آرماتور فقط با دیتایل", "مالکیت بتن و قالب"),
    "block_wall": ("ارتفاع و طول دیوار", "مشخصات بلوک و بند ملات", "بازشوها", "ملات و مصالح وابسته", "مالکیت لایه‌های نازک‌کاری"),
    "wall_with_opening": ("بازشوهای دارای ابعاد معتبر", "ابعاد دیوار و بلوک", "ملات و بندها", "کسر و مالکیت هر بازشو"),
    "waffle_one_way": ("جهت ریب‌ها", "ابعاد ریب و تعداد", "ناحیه توپر و بازشو", "قالب وافل", "بتن و آرماتور از دیتایل تخصصی", "جلوگیری از دوباره‌شماری ریب"),
    "waffle_two_way": ("دو جهت ریب", "ابعاد ریب و شبکه", "تقاطع و حجم مشترک", "ناحیه توپر و بازشو", "بتن، قالب و آرماتور از دیتایل تخصصی"),
    "mep": ("رشته و عملیات برق یا مکانیک", "مسیر یا تجهیز با سند", "ابعاد و تعداد مستقل", "مبنای اندازه‌گیری و واحد", "مالکیت اجزای مشترک"),
    "floor_finish": ("ناحیه و کف واقعی", "بازشو و کسورات", "لایه و ضخامت مستند", "مصرف مصالح و پرت فقط با منبع"),
    "false_ceiling": ("سطح و بازشو", "نوع سقف کاذب", "زیرسازی و آویز مستند", "چراغ و تأسیسات مشترک"),
}
# Do not silently treat a joist-block assembly as foam. Ask for the correct
# specialist tool until a matching reviewed template is provided.
_FAMILY_TEMPLATES["joist_block"] = ()

# Explicit W1-specific fields are review metadata only, not geometry numbers
# accepted by any secondary calculator. Only the original specialist workflow
# may measure them after engineering validation.
_SPECIALIST_REQUIRED = {
    "joist_block": ("joist_direction", "joist_count", "joist_length_ref",
                    "block_count", "block_spec_ref", "topping_thickness_ref",
                    "thermal_rebar_detail_ref", "openings_ref", "ownership_ref"),
    "waffle_one_way": ("rib_direction", "rib_count", "rib_detail_ref",
                       "solid_area_ref", "opening_ref", "ownership_ref"),
    "waffle_two_way": ("rib_direction_x", "rib_direction_y", "rib_grid_ref",
                       "intersections_ref", "solid_area_ref", "opening_ref", "ownership_ref"),
    "mep": ("discipline", "operation_ref", "route_or_equipment_ref",
            "measurement_unit_ref", "ownership_ref"),
}


def _id(value, label):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("شناسه معتبر " + label + " لازم است.")
    return value


@dataclass(frozen=True)
class GuidedContext:
    project_id: str
    floor_id: str
    member_id: str | None
    source_id: str | None
    source_sha256: str | None
    revision: str | None
    operation: str
    current_tab: str = "متره"
    zone_id: str | None = None
    boq_row_id: str | None = None
    review_status: str = "unreviewed"


@dataclass(frozen=True)
class GuidedProposal:
    id: str
    project_id: str
    cas_digest: str
    source_sha256: str | None
    revision: str | None
    family: str
    title: str
    missing_inputs: tuple[str, ...]
    review_questions: tuple[str, ...]
    components_for_review: tuple[str, ...]
    suggested_action: str
    limitations: tuple[str, ...]
    requires_confirmation: bool = True
    mode: str = "offline_rules_no_model"
    quantity_authority: bool = False


class ContextualTakeoffGuide:
    """Project-bound, cancellable proposals with real provenance and no writes."""

    def __init__(self, service, *, templates=None):
        self.service = service
        self.templates = templates or AssemblyTemplateLibrary()
        self._requests = {}  # ephemerally reviewed only; never persisted BOQ
        self.enabled = True

    def _project(self, context: GuidedContext):
        _id(context.project_id, "پروژه")
        _id(context.floor_id, "طبقه")
        if not isinstance(context.operation, str) or not context.operation.strip():
            raise ValueError("عملیات منتخب مشخص نیست.")
        try:
            digest = self.service.store.current_digest(context.project_id)
            p = self.service.open_project(context.project_id)
        except KeyError as exc:
            raise ValueError("پروژه ذخیره‌شده معتبر پیدا نشد.") from exc
        if not isinstance(p, dict) or p.get("id") != context.project_id or not digest:
            raise ValueError("پروژه ذخیره‌شده معتبر پیدا نشد.")
        floors = p.get("floors", [])
        if not any(isinstance(f, dict) and f.get("id")==context.floor_id for f in floors):
            raise ValueError("طبقه صریح در این پروژه وجود ندارد.")
        if context.member_id:
            if not any(isinstance(m, dict) and m.get("id")==context.member_id and
                       m.get("floor_id")==context.floor_id for m in p.get("members",[])):
                raise ValueError("عضو واقعی متعلق به این طبقه نیست.")
        if context.source_sha256 is not None:
            sha = context.source_sha256
            if not isinstance(sha,str) or len(sha)!=64 or any(c not in "0123456789abcdef" for c in sha):
                raise ValueError("هش سند معتبر نیست.")
            if not context.revision or not context.source_id:
                raise ValueError("مدرک IFC با Revision و منبع لازم است.")
            source=Path(context.source_id)
            if not source.is_file():
                raise ValueError("فایل منبع بازشده موجود نیست.")
            h=sha256()
            with source.open("rb") as file:
                for chunk in iter(lambda:file.read(1024*1024),b""):
                    h.update(chunk)
            if h.hexdigest()!=sha:
                raise ValueError("منبع در حین انتخاب تغییر کرده است.")
        return digest, p

    def propose(self, context: GuidedContext, *, inputs: Mapping[str, object] | None = None):
        if not self.enabled:
            raise RuntimeError("دستیار خاموش است؛ متره دستی اصلی همچنان در دسترس است.")
        if context.operation not in _QUESTIONS:
            raise ValueError("خانواده متره انتخاب‌شده در W1 تعریف نشده است.")
        digest, _project = self._project(context)
        provided=dict(inputs or {})
        templates = _FAMILY_TEMPLATES[context.operation]
        if provided and not templates:
            raise ValueError("برای این خانواده قالب محاسباتی عام تأیید نشده؛ فرم تخصصی را باز کنید.")
        required = _SPECIALIST_REQUIRED.get(context.operation, ())
        allowed=set(required)
        for code in templates:
            t=self.templates.get(code)
            allowed.update(t.required_inputs)
            allowed.update(t.optional_inputs)
            required += t.required_inputs
        unknown=set(provided)-allowed
        if unknown:
            raise ValueError("ورودی ناشناخته: "+", ".join(sorted(unknown)))
        missing=tuple(dict.fromkeys(k for k in required
                          if k not in provided or provided[k] in ("",None)))
        # No numeric preview: the authoritative calculator is the existing
        # specialist/Decimal BOQ API after an independent human acceptance.
        warnings = ["نتیجه فقط پیشنهاد بازبینی است؛ هیچ مبلغ یا مقدار تولید یا ثبت نشده."]
        if not templates:
            warnings.append("قالب عمومی سازگار موجود نیست؛ برای محاسبه از فرم تخصصی معتبر استفاده کنید.")
        if not context.source_sha256:
            warnings.append("مدرک هندسه ثبت نشده؛ هیچ ابعادی از مدل حدس زده نمی‌شود.")
        if context.review_status != "approved":
            warnings.append("هویت/عملیات مهندسی هنوز تأیید مستقل ندارد.")
        p = GuidedProposal(
            id="W1-"+uuid4().hex,
            project_id=context.project_id,cas_digest=digest,
            source_sha256=context.source_sha256,revision=context.revision,
            family=context.operation,title=context.operation,
            missing_inputs=missing,
            review_questions=_QUESTIONS[context.operation],
            components_for_review=tuple(t.title_fa for t in
                                        (self.templates.get(code) for code in templates)),
            suggested_action="بازکردن فرم تخصصی واقعی و تأیید جداگانه مهندس",
            limitations=tuple(warnings))
        self._requests[p.id]=(context,p,tuple(sorted(provided)))
        return p

    def check_current(self, proposal: GuidedProposal):
        record=self._requests.get(proposal.id)
        if record is None or record[1] != proposal:
            raise ValueError("پیشنهاد لغو شده یا متعلق به نشست دیگری است.")
        context, _, _ = record
        digest, _ = self._project(context)
        if digest!=proposal.cas_digest:
            raise RuntimeError("نسخه پروژه تغییر کرده؛ پیشنهاد نیازمند بازبینی دوباره است.")
        return True

    def review(self, proposal: GuidedProposal, *, accepted: tuple[str,...]=(),
               rejected: tuple[str,...]=()):
        self.check_current(proposal)
        if set(accepted)&set(rejected):
            raise ValueError("یک قلم را نمی‌توان هم تأیید و هم رد کرد.")
        if not set(accepted+rejected).issubset(set(proposal.review_questions)):
            raise ValueError("اقلام بازبینی ناشناخته‌اند.")
        # A review is an explicit UI record, NOT permission to commit BOQ.
        return {
            "proposal_id":proposal.id,"status":"review_only",
            "accepted_questions":tuple(accepted),"rejected_questions":tuple(rejected),
            "missing_inputs":proposal.missing_inputs,
            "requires_separate_engineering_approval":True,
            "boq_write":False,"quantity":None,"price":None,
            "next_action":proposal.suggested_action,
        }

    def cancel(self, proposal_id: str):
        return self._requests.pop(proposal_id,None) is not None

    def disable(self):
        self.enabled=False
        self._requests.clear()

    def enable(self):
        self.enabled=True

    def explain_persisted_boq(self, context: GuidedContext, *, index: int):
        digest, p = self._project(context)
        boq=p.get("boq",[])
        if isinstance(index,bool) or not isinstance(index,int) or index<0 or index>=len(boq):
            raise ValueError("ردیف واقعی BOQ یافت نشد.")
        row=boq[index]
        if not isinstance(row,dict) or not row.get("unit"):
            raise ValueError("ردیف BOQ مستند نیست.")
        qty=row.get("quantity")
        if isinstance(qty,bool) or qty is None:
            raise ValueError("مقدار قطعی در ردیف وجود ندارد.")
        try:
            number=Decimal(str(qty))
        except (ValueError,InvalidOperation):
            raise ValueError("مقدار معتبر قابل استناد نیست.")
        if not number.is_finite():
            raise ValueError("مقدار معتبر قابل استناد نیست.")
        return {"source":"persisted_project_boq","project_id":context.project_id,
                "cas_digest":digest,"quantity":str(number),"unit":row["unit"],
                "source_ids":tuple(row.get("source_ids") or []),
                "read_only":True}
