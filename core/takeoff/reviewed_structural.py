"""Reviewed concrete column, grade-beam and foundation takeoff, using canonical engines.

Beam takeoff stays in BeamDetailWorkflow. This module handles the other
structural members and never derives unobserved reinforcement or form faces.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import json
import math
from typing import Any

from core.takeoff.boq import build_boq
from core.takeoff.commit_guards import require_source_unused, validate_commit_rows, rebuild_project_boq, require_reset_of_changed_approvals
from core.drawings.beam_detail_match import validate_evidence_link
from core.takeoff.reviewed_components import (
    require_text, positive, reviewed_steel, net_concrete, net_formwork,
)
from core.takeoff.stirrup_zones import validate_stirrup_zones

REGISTER = "reviewed_structural_members"
KINDS = {
    "column": ("ستون", "building", "column",
               ("width", "depth", "height", "count"),
               ("longitudinal", "ties", "crossties", "starters")),
    "tie_beam": ("شناژ", "building", "tie_beam",
                 ("length", "width", "depth", "count"),
                 ("longitudinal", "stirrups", "crossties", "additional")),
    "isolated_footing": ("پی منفرد", "advanced", "footing_concrete",
                         ("length", "width", "thickness", "count"),
                         ("bottom_x", "bottom_y", "top_x", "top_y", "starters", "additional")),
    "strip_footing": ("پی نواری", "advanced", "footing_concrete",
                      ("length", "width", "thickness", "count"),
                      ("bottom_x", "bottom_y", "top_x", "top_y", "starters", "additional")),
    "mat_footing": ("پی گسترده", "advanced", "footing_concrete",
                    ("length", "width", "thickness", "count"),
                    ("bottom_x", "bottom_y", "top_x", "top_y", "starters", "additional")),
    "pile_cap": ("کلاهک شمع", "advanced", "footing_concrete",
                 ("length", "width", "thickness", "count"),
                 ("bottom_x", "bottom_y", "top_x", "top_y", "starters", "additional")),
    "bored_pile": ("شمع بتنی درجا", "building", "column",
                   ("diameter", "height", "count"),
                   ("longitudinal", "spiral_ties", "crossties", "starters")),
}


def _key(kind: str, floor: str, member: str) -> str:
    digits = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    return json.dumps([x.translate(digits).casefold().strip()
                       for x in (kind, floor, member)], ensure_ascii=False)


def empty_member(kind: str, floor_id: str, member_id: str) -> dict:
    if kind not in KINDS:
        raise KeyError(f"عضو بتنی ناشناخته است: {kind}")
    return {"kind": kind, "floor_id": require_text(floor_id, "طبقه"),
            "member_id": require_text(member_id, "شناسه عضو"),
            "source": {}, "geometry": {}, "formwork": {"status": "unreviewed"},
            "rebars": {name: {"status": "unreviewed"} for name in KINDS[kind][4]}}


def _validate_source(source: dict, member_id: str) -> str:
    if not isinstance(source, dict) or source.get("mode") not in {"manual", "drawing"}:
        raise ValueError("منبع معتبر متره دستی یا نقشه لازم است")
    sid = require_text(source.get("source_id"), "شناسه منبع")
    if source["mode"] == "drawing":
        digest = require_text(source.get("sha256"), "اثر انگشت نقشه")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("SHA-256 نقشه نامعتبر است")
        positive(source.get("page"), "شماره صفحه", integer=True)
        path = Path(require_text(source.get("drawing_path"), "مسیر واقعی فایل نقشه"))
        if not path.is_file():
            raise ValueError("فایل منبع نقشه در دسترس نیست")
        computed = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                computed.update(block)
        if computed.hexdigest() != digest.lower():
            raise ValueError("محتوای نقشه با اثر انگشت ذخیره‌شده یکسان نیست")
        region = source.get("selected_region")
        if (not isinstance(region, (list, tuple)) or len(region) != 4 or
                not all(math.isfinite(float(x)) for x in region) or
                float(region[2]) <= 0 or float(region[3]) <= 0):
            raise ValueError("ناحیه انتخابی نقشه معتبر نیست")
        validate_evidence_link(source, member_id)
    elif "detail_evidence" in source:
        raise ValueError("مرجع دیتایل باید به نقشه تأییدشده مربوط باشد")
    return sid


def _structural_shape(record: dict) -> tuple[str, str, str]:
    if not isinstance(record, dict):
        raise ValueError("ساختار عضو نامعتبر است")
    kind = record.get("kind")
    if kind not in KINDS:
        raise ValueError("نوع عضو باید ستون، شناژ یا نوع معتبر پی باشد")
    return (kind, require_text(record.get("floor_id"), "طبقه"),
            require_text(record.get("member_id"), "شناسه عضو"))


def preview_member(data: dict, engine: Any) -> dict:
    """Preview every individually approved row, block commit on any missing group."""
    kind, floor, member_id = _structural_shape(data)
    if kind=='column' and data.get('measurement_policy')=='column_specialist_v1':return _preview_column_specialist(data,engine)
    if data.get('measurement_policy')=='foundation_tie_specialist_v1':
        return _preview_foundation_tie_specialist(data,engine)
    title, domain, item, fields, groups = KINDS[kind]
    blockers: list[str] = []
    rows: list[dict] = []
    source = data.get("source", {})
    try:
        sid = _validate_source(source, member_id)
    except (ValueError, TypeError) as exc:
        sid = ""
        blockers.append(f"منبع: {exc}")
    geometry = data.get("geometry", {})
    prefix = f"structural:{kind}:{floor}:{member_id}"
    if not isinstance(geometry, dict):
        geometry = {}
    try:
        require_text(geometry.get("source_ref"), "مرجع هندسه")
        require_text(geometry.get("approved_by"), "تأییدکننده هندسه")
        shape = require_text(geometry.get("shape"), "نوع هندسه واقعی عضو")
        count = int(positive(geometry.get("count"), "تعداد فیزیکی عضو", integer=True))
        sections = []
        if shape == "rectangular":
            if kind == "bored_pile":
                raise ValueError("شمع درجا به قطر واقعی و شکل دایره‌ای تأییدشده نیاز دارد")
            dims = {field: (count if field == "count" else positive(geometry.get(field), field))
                    for field in fields}
            gross = engine.calculate(domain, item, description=f"بتن {title} {member_id}", **dims)
            if gross.unit != "m3":
                raise ValueError("واحد حجم سازه ناسازگار است")
            gross_m3 = gross.quantity
            formula = "حجم مستطیلی موتور اصلی منهای کسورات مستقل تأییدشده"
        elif shape == "circular_column" and kind in {"column", "bored_pile"}:
            if any(k in geometry for k in ("width", "depth", "sections")):
                raise ValueError("ابعاد مستطیلی و دایره‌ای نباید برای یک ستون ترکیب شوند")
            diameter = positive(geometry.get("diameter"), "قطر واقعی ستون")
            height = positive(geometry.get("height"), "ارتفاع واقعی ستون")
            gross_m3 = math.pi * (diameter / 2)**2 * height * count
            formula = "π×قطر²/۴×ارتفاع×تعداد منهای کسورات مستند"
            dims = {"diameter": diameter, "height": height, "count": count}
        elif shape == "reviewed_sections":
            # A list of positive rectangle/section volumes alone does not
            # establish nonoverlap. Require the checked layout and reviewer.
            require_text(geometry.get("section_layout_ref"), "مرجع جانمایی ناحیه‌های مقطع")
            require_text(geometry.get("nonoverlap_reviewed_by"), "تأییدکننده عدم هم‌پوشانی")
            if kind == "bored_pile":
                raise ValueError("شمع با مقطع متغیر نیازمند دیتایل و روش تأیید مستقل است")
            if any(k in geometry for k in ("width", "depth", "thickness", "length")):
                raise ValueError("ابعاد کلی با جدول ناحیه‌های هندسی مستقل تعارض دارد")
            parts = geometry.get("sections")
            if not isinstance(parts, list) or not parts:
                raise ValueError("مقطع متغیر باید جدول ناحیه‌های واقعی داشته باشد")
            used = set()
            volumes = []
            for part in parts:
                if not isinstance(part, dict):
                    raise ValueError("ساختار مقطع هندسی نامعتبر است")
                identity = require_text(part.get("id"), "شناسه ناحیه هندسی")
                if identity in used:
                    raise ValueError("مقطع هندسی با شناسه تکراری ثبت شده است")
                used.add(identity)
                ref = require_text(part.get("source_ref"), "مرجع هندسه ناحیه")
                reviewer = require_text(part.get("approved_by"), "تأییدکننده ناحیه")
                if kind == "column":
                    if set(part) != {"id", "source_ref", "approved_by",
                                    "net_section_area_m2", "start_m", "end_m"}:
                        raise ValueError("ستون چندمقطعی به ابتدا و انتهای واقعی هر ناحیه نیاز دارد")
                    area = positive(part.get("net_section_area_m2"), "سطح واقعی مقطع")
                    start = positive(part.get("start_m"), "موقعیت شروع", allow_zero=True)
                    end = positive(part.get("end_m"), "موقعیت پایان")
                    if end <= start:
                        raise ValueError("ارتفاع ناحیه ستون باید مثبت باشد")
                    span = end - start
                    # Boundaries cannot overlap, repeat or silently leave gaps.
                    if sections:
                        expected_start = sections[-1]["end_m"]
                    else:
                        expected_start = 0.0
                    if not math.isclose(start, expected_start, abs_tol=1e-9):
                        raise ValueError("ناحیه‌های ستون دارای فاصله یا هم‌پوشانی‌اند")
                    qty = area * span * count
                else:
                    if set(part) != {"id", "source_ref", "approved_by",
                                    "length_m", "width_m", "thickness_m"}:
                        raise ValueError("پی/شناژ مقطع‌بندی‌شده به طول، عرض و ضخامت واقعی نیاز دارد")
                    length = positive(part.get("length_m"), "طول واقعی قطعه")
                    width = positive(part.get("width_m"), "عرض واقعی قطعه")
                    thickness = positive(part.get("thickness_m"), "ضخامت واقعی قطعه")
                    qty = length * width * thickness * count
                volumes.append(qty)
                section_info = {"id": identity, "source_ref": ref,
                                "approved_by": reviewer, "volume_m3": qty}
                if kind == "column":
                    section_info["start_m"], section_info["end_m"] = start, end
                sections.append(section_info)
            gross_m3 = math.fsum(volumes)
            positive(gross_m3, "حجم ناحیه‌بندی‌شده")
            dims = {"count": count, "sections": sections}
            formula = "جمع حجم ناحیه‌های واقعی جداگانه منهای کسورات مستند"
        else:
            raise ValueError("نوع شکل عضو باید مستطیلی، ستون دایره‌ای یا مقاطع مستند باشد")
        net, deductions = net_concrete(gross_m3, geometry.get("intersections"))
        rows.append({"source_id": prefix + ":concrete", "item": item, "code": "concrete",
                     "domain": domain, "description": f"بتن خالص {title} {member_id}",
                     "quantity": net, "unit": "m3",
                     "formula": formula,
                     "params": {"dimensions": dims, "shape": shape,
                                "sections": sections, "intersections": deductions,
                                "source_ref": geometry["source_ref"]}})
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        blockers.append(f"بتن {title}: {exc}")
    form = data.get("formwork", {})
    if not isinstance(form, dict):
        form = {}
    if form.get("status") == "not_applicable":
        try:
            require_text(form.get("reason"), "دلیل نبود قالب")
            require_text(form.get("source_ref"), "مرجع عدم کاربرد قالب")
            require_text(form.get("approved_by"), "تأییدکننده عدم کاربرد قالب")
        except ValueError as exc:
            blockers.append(f"قالب‌بندی: {exc}")
    elif form.get("status") == "confirmed":
        try:
            if positive(geometry.get("count"), "تعداد اعضا", integer=True) > 1:
                if form.get("area_scope") != "total_group":
                    raise ValueError("برای اعضای تکراری باید مشخص شود مساحت قالب جمع کل اعضا است")
                require_text(form.get("area_scope_ref"), "مرجع جمع قالب کل اعضا")
            area, faces = net_formwork(form)
            rows.append({"source_id": prefix + ":formwork", "item": "formwork",
                         "code": "formwork", "domain": "building",
                         "description": f"قالب‌بندی {title} {member_id}",
                         "quantity": area, "unit": "m2",
                         "formula": "جمع سطوح واقعی در تماس با قالب",
                         "params": {"surfaces": faces}})
        except ValueError as exc:
            blockers.append(f"قالب‌بندی: {exc}")
    else:
        blockers.append("قالب‌بندی هنوز بررسی و تأیید نشده است")
    rebars = data.get("rebars", {})
    if not isinstance(rebars, dict) or set(rebars) != set(groups):
        blockers.append("گروه‌های میلگرد عضو ناقص یا اضافه هستند")
    else:
        for group_name in groups:
            bar = rebars[group_name]
            if not isinstance(bar, dict):
                blockers.append(f"میلگرد {group_name}: ساختار نامعتبر")
                continue
            state = bar.get("status")
            if state == "not_applicable":
                try:
                    require_text(bar.get("reason"), "دلیل نبود آرماتور")
                    require_text(bar.get("approved_by"), "تأییدکننده عدم کاربرد")
                    require_text(bar.get("source_ref"), "مرجع دیتایل")
                except ValueError as exc:
                    blockers.append(f"میلگرد {group_name}: {exc}")
            elif state == "confirmed":
                try:
                    member_count = int(positive(geometry.get("count"), "تعداد اعضا", integer=True))
                    if member_count > 1:
                        if bar.get("count_scope") != "total_group":
                            raise ValueError("تعداد میلگرد باید به‌صورت صریح جمع کل اعضای تکراری باشد")
                        require_text(bar.get("count_scope_ref"), "مرجع تعداد کل گروه میلگرد")
                    if (kind == "column" and group_name == "ties") or (
                            kind == "tie_beam" and group_name == "stirrups"):
                        # A single physical station schedule cannot represent
                        # several identical columns without explicit per-member rows.
                        if member_count > 1:
                            raise ValueError("خاموت اعضای تکراری باید برای هر عضو جداگانه متره شود")
                        # Physical ties need an actual zone plan. Merely giving
                        # spacing is not evidence of a count.
                        raw_axis = geometry.get("height" if kind == "column" else "length")
                        if kind == "column" and geometry.get("shape") == "reviewed_sections" and raw_axis is None:
                            raw_axis = sections[-1]["end_m"] if sections else None
                        axial_length = positive(raw_axis, "طول واقعی عضو برای جانمایی خاموت")
                        validate_stirrup_zones(bar.get("segments"), axial_length)
                    mass, parts = reviewed_steel(bar, label=group_name, engine=engine)
                    rows.append({"source_id": prefix + ":rebar:" + group_name,
                                 "item": "rebar", "code": "rebar", "domain": "building",
                                 "description": f"آرماتور {group_name} {title} {member_id}",
                                 "quantity": mass, "unit": "kg",
                                 "formula": "جمع تعداد × طول برش مستند × وزن واحد مستند",
                                 "params": {"series": parts}})
                except (ValueError, TypeError, KeyError) as exc:
                    blockers.append(f"میلگرد {group_name}: {exc}")
            else:
                blockers.append(f"میلگرد {group_name}: تأیید نشده است")
    return {"kind": kind, "floor_id": floor, "member_id": member_id,
            "source_id": sid, "ready": not blockers, "blockers": blockers,
            "rows": rows, "preview_only": True}


class ReviewedStructuralWorkflow:
    """Separate non-beam register, reusing StructuralPro ProjectStore and BOQ."""

    def __init__(self, store: Any, engine: Any):
        self.store, self.engine = store, engine

    def _load(self, project_id: str):
        digest = self.store.current_digest(project_id)
        if hasattr(self.store, "_cache"):
            self.store._cache.pop(project_id, None)
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return project, digest

    def get(self, project_id: str, kind: str, floor: str, member_id: str):
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        record=(project.get(REGISTER) or {}).get(_key(kind,floor,member_id))
        if record and record['data'].get('measurement_policy') in ('column_specialist_v1','foundation_tie_specialist_v1'):
            from core.takeoff.manual_formula_amendments import beam_current
            return beam_current(project,_key(kind,floor,member_id))
        return deepcopy(record)

    def save_draft(self, project_id: str, draft: dict, *, expected_revision: int = 0, reason: str = "ثبت پیش‌نویس", _copy_source=None):
        kind, floor, member_id = _structural_shape(draft)
        source = draft.get("source")
        if source:
            _validate_source(source, member_id)
        try:
            json.dumps(draft, allow_nan=False, ensure_ascii=False)
        except (TypeError, ValueError) as exc:
            raise ValueError("پیش‌نویس دارای داده نامعتبر است") from exc
        project, digest = self._load(project_id)
        register = project.setdefault(REGISTER, {})
        if not isinstance(register, dict):
            raise ValueError("ساختار ثبت اعضای سازه نامعتبر است")
        key = _key(kind, floor, member_id)
        previous = register.get(key)
        if previous is None and any(h.get('member_key')==key and h.get('action')=='delete_draft' for h in project.get('structural_member_history',[])):
            raise ValueError('شناسه حذف‌شده قابل استفاده مجدد نیست؛ شناسه مستقل لازم است')
        from core.takeoff.manual_formula_amendments import digest as payload_digest
        if _copy_source is not None:
            source_key,source_digest=_copy_source
            from core.takeoff.manual_formula_amendments import beam_current
            current=beam_current(project,source_key) if (project.get(REGISTER,{}).get(source_key,{}).get('data',{}).get('measurement_policy') in ('column_specialist_v1','foundation_tie_specialist_v1')) else project.get(REGISTER,{}).get(source_key)
            if payload_digest(current)!=source_digest:raise RuntimeError('مبنای کپی هم‌زمان تغییر کرده است')
        proposal=deepcopy(draft);review=proposal.pop('component_review',None)
        fresh=draft.get('measurement_policy') in ('column_specialist_v1','foundation_tie_specialist_v1') and isinstance(review,dict) and review.get('base_revision')==expected_revision and bool(review.get('reviewer')) and review.get('digest')==payload_digest(proposal)
        if fresh and not preview_member(proposal,self.engine)['ready']:raise ValueError('بازبینی داده ناقص معتبر نیست')
        if previous and previous['data'].get('measurement_policy')=='column_specialist_v1':
            if draft.get('measurement_policy')!='column_specialist_v1':raise ValueError('حذف قرارداد تخصصی ستون ممنوع است')
            if any(draft.get(k)!=previous['data'].get(k) for k in ('building_id','axis','member_id','floor_id')) or any(draft.get('source',{}).get(k)!=previous['data'].get('source',{}).get(k) for k in ('source_id','mode')):raise ValueError('تغییر هویت فیزیکی ستون نیازمند گردش مستقل است')
        if previous and previous['data'].get('measurement_policy')=='foundation_tie_specialist_v1':
            if draft.get('measurement_policy')!='foundation_tie_specialist_v1':
                raise ValueError('حذف قرارداد واحدهای تخصصی پی و شناژ ممنوع است')
            if (any(draft.get(k)!=previous['data'].get(k) for k in
                    ('building_id','kind','member_id','floor_id')) or
                any(draft.get('source',{}).get(k)!=previous['data'].get('source',{}).get(k)
                    for k in ('source_id','mode'))):
                raise ValueError('تغییر هویت فیزیکی پی و شناژ نیازمند گردش مستقل است')
        if previous and previous.get("status") == "committed":
            raise ValueError("عضو قبلاً به ریزمتره انتقال یافته است")
        revision = previous["revision"] if previous else 0
        if revision != expected_revision:
            raise RuntimeError("تعارض نسخه؛ دوباره بارگذاری کنید")
        if previous and previous["data"].get("source") != source and not fresh:
            if (draft.get("geometry", {}).get("approved_by") or
                    any(isinstance(x, dict) and x.get("status") in ("confirmed", "not_applicable")
                        for x in [draft.get("formwork")] + list(draft.get("rebars", {}).values()))):
                raise ValueError("منبع تغییر یافته است؛ تأیید هندسه، قالب و آرماتور باید بازنشانی شوند")
        source_id = source.get("source_id") if isinstance(source, dict) else None
        if source_id:
            require_source_unused(project, source_id, exclude=(REGISTER, key))
        if not fresh:require_reset_of_changed_approvals(previous['data'] if previous else None,draft)
        if previous:project.setdefault('structural_member_history',[]).append({'member_key':key,'previous':deepcopy(previous),'revision':revision+1,'reason':require_text(reason,'علت نسخه'),'at':datetime.now(timezone.utc).isoformat()})
        record = {"status": "draft", "revision": revision+1, "data": deepcopy(draft),
                  "updated_at": datetime.now(timezone.utc).isoformat()}
        register[key] = record
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(record)

    def copy_draft(self, project_id, kind, floor, member_id, *, new_member_id,
                   new_source_id, expected_revision, reason):
        from uuid import uuid4
        original = self.get(project_id, kind, floor, member_id)
        if original is None:raise KeyError(member_id)
        if original['revision'] != expected_revision:raise RuntimeError('تعارض نسخه؛ دوباره بارگذاری کنید')
        new_member_id=require_text(new_member_id,'شناسه عضو جدید')
        new_source_id=require_text(new_source_id,'منبع مستقل جدید')
        if new_member_id==member_id or new_source_id==original['data'].get('source',{}).get('source_id'):
            raise ValueError('کپی نیازمند هویت و منبع مستقل است')
        if self.get(project_id,kind,floor,new_member_id) is not None:raise ValueError('عضو مقصد موجود است')
        data=deepcopy(original['data']);data['member_id']=new_member_id
        data['source']['source_id']=new_source_id
        def reset(value):
            if isinstance(value,dict):
                for key in ('approved_by','reviewed_by','review_digest','component_review'):
                    value.pop(key,None)
                if 'id' in value:value['id']='SC-'+uuid4().hex
                if 'status' in value:value['status']='unreviewed'
                for child in value.values():reset(child)
            elif isinstance(value,list):
                for child in value:reset(child)
        reset(data)
        return self.save_draft(project_id,data,expected_revision=0,reason=require_text(reason,'علت کپی'),_copy_source=(_key(kind,floor,member_id),hashlib.sha256(json.dumps(original,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()))

    def delete_draft(self, project_id, kind, floor, member_id, *, expected_revision, reason):
        project,token=self._load(project_id);key=_key(kind,floor,member_id)
        record=project.get(REGISTER,{}).get(key)
        if record is None:raise KeyError(member_id)
        if record['status']=='committed':raise ValueError('حذف عضو قطعی ممنوع است')
        if record['revision']!=expected_revision:raise RuntimeError('تعارض نسخه؛ حذف رد شد')
        project.setdefault('structural_member_history',[]).append({
            'member_key':key,'previous':deepcopy(record),'revision':record['revision']+1,
            'reason':require_text(reason,'علت حذف'),'action':'delete_draft',
            'at':datetime.now(timezone.utc).isoformat()})
        del project[REGISTER][key]
        self.store.save(project_id,project,expected_digest=token)
        return {'status':'deleted','member_key':key}

    def preview(self, project_id: str, kind: str, floor: str, member_id: str):
        item = self.get(project_id, kind, floor, member_id)
        if item is None:
            raise KeyError(member_id)
        report = preview_member(item["data"], self.engine)
        report["revision"] = item["revision"]
        report["committed"] = item["status"] == "committed"
        return report

    def commit(self, project_id: str, kind: str, floor: str, member_id: str,
               *, expected_revision: int):
        project, digest = self._load(project_id)
        record = (project.get(REGISTER) or {}).get(_key(kind, floor, member_id))
        if record is None:
            raise KeyError(member_id)
        if record["status"] == "committed":
            raise ValueError("عضو قبلاً ثبت قطعی شده است")
        if record["revision"] != expected_revision:
            raise RuntimeError("تعارض نسخه؛ ثبت قطعی رد شد")
        report = preview_member(record["data"], self.engine)
        if not report["ready"]:
            raise ValueError("متره ناقص؛ ورود به BOQ مسدود است: " + "؛ ".join(report["blockers"]))
        prior = project.get("takeoffs", [])
        ids = {row["source_id"] for row in report["rows"]}
        takeoffs = deepcopy(prior)
        for row in report["rows"]:
            takeoffs.append({"id": row["source_id"], "source_id": row["source_id"],
                             "member_code": member_id, "system": floor,
                             "domain": row["domain"], "item": row["item"],
                             "description": row["description"], "params": row["params"],
                             "provenance": deepcopy(record["data"]["source"]),
                             "revision": record["revision"],
                             "quantities": [{"code": row["code"], "title": row["description"],
                                             "unit": row["unit"], "amount": row["quantity"],
                                             "formula": row["formula"], "price_code": None,
                                             "unit_price": None}]})
        validated = validate_commit_rows(
            project, takeoffs[len(prior):], source_id=record["data"]["source"]["source_id"],
            expected_current_registry=(REGISTER, _key(kind, floor, member_id)))
        project["takeoffs"], project["boq"] = rebuild_project_boq(
            project, list(prior) + validated)
        record["status"] = "committed"
        record["committed_source_ids"] = sorted(ids)
        record["committed_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(project_id, project, expected_digest=digest)
        return {"status": "committed", "revision": record["revision"],
                "takeoff_rows": len(report["rows"]), "source_ids": sorted(ids)}


# Circular-column geometry is a versioned subset of the existing column contract.
# PI is a fixed explicit 50-decimal approximation, not an exact real number.
# Square roots in helix geometry use a documented 50-significant-digit
# ROUND_HALF_EVEN policy; all non-irrational arithmetic remains Decimal.
from decimal import (
    Decimal as _D, localcontext as _localcontext,
    ROUND_HALF_EVEN as _HALF_EVEN, Inexact as _Inexact, Rounded as _Rounded,
)

_CIRCULAR_PI = _D('3.14159265358979323846264338327950288419716939937510')
_CIRCULAR_PI_POLICY = 'pi_fixed_50_decimal_v1'
_HELIX_LENGTH_POLICY = 'decimal_sqrt_50_sig_half_even_v1'


def _reviewed_spiral_length(part, column_diameter, *, check, require):
    """Helical centreline length from an explicit reviewed pitch/turn schedule.

    Does not infer the number of turns, end details, hooks or extra bars.
    Adjacent half-open axial zones share a point, not a measurable length.
    """
    if part.get('shape_kind') != 'spiral':
        raise ValueError('نوع خاموت مارپیچ معتبر نیست')
    if 'cut_length_m' in part or 'length_parts_m' in part:
        raise ValueError('برش دستی با محاسبه محور مارپیچ نباید ترکیب شود')
    start = check(part.get('start_m'),'شروع ناحیه',True)
    end = check(part.get('end_m'),'پایان ناحیه')
    pitch = check(part.get('pitch_m'),'گام مارپیچ')
    turns = check(part.get('turns'),'تعداد دور مارپیچ',integer=True)
    axis = check(part.get('axis_diameter_m'),'قطر محور مارپیچ')
    cover = check(part.get('cover_m'),'پوشش مستند')
    bar_diameter = check(part.get('nominal_diameter_mm'),'قطر میلگرد')/_D(1000)
    if end <= start or end-start != turns*pitch:
        raise ValueError('ارتفاع ناحیه، گام و تعداد دور صریح ناسازگارند')
    if axis + bar_diameter + 2*cover != column_diameter:
        raise ValueError('قطر محور، پوشش و قطر میلگرد با ستون ناسازگارند')
    require(part.get('cut_length_ref'),'مرجع طول هندسی مارپیچ')
    require(part.get('end_condition_ref'),'مرجع جزئیات انتهای مارپیچ')
    extras=part.get('end_parts_m')
    if not isinstance(extras,list):raise ValueError('اجزای انتهایی مارپیچ باید صریح باشند')
    if not extras and part.get('end_condition')!='no_extension_reviewed':
        raise ValueError('نبود طول اضافی انتهایی نیازمند تأیید صریح است')
    if extras and part.get('end_condition')!='detailed_extensions':
        raise ValueError('قرارداد اجزای انتهایی مارپیچ مشخص نیست')
    from core.takeoff.reviewed_components import PARTS
    extra=_D(0)
    for piece in extras:
        if not isinstance(piece,dict) or piece.get('kind') not in PARTS:
            raise ValueError('نوع جزء انتهایی نامعتبر است')
        require(piece.get('source_ref'),'مرجع جزء انتهایی')
        extra += check(piece.get('length_m'),'طول جزء انتهایی')
    # Decimal sqrt is irrational in general: the only intentional rounding
    # boundary, to 50 significant digits, is isolated from @exact traps.
    with _localcontext() as ctx:
        ctx.prec=50
        ctx.rounding=_HALF_EVEN
        ctx.traps[_Inexact]=False
        ctx.traps[_Rounded]=False
        length_per_turn = ((_CIRCULAR_PI*axis)**2+pitch**2).sqrt()
    return start,end,turns*length_per_turn+extra


# Contract adapter over the shared dimensional AST/Decimal evaluator. No new engine.
from core.commercial.exact_values import exact as _exact,number as _decimal,wire as _wire

@_exact
def _preview_column_specialist(data,engine):
    from core.takeoff.formulas import evaluate
    from core.takeoff.beam_detail import component_reviewed
    from core.takeoff.reviewed_components import PARTS
    kind,floor,member=_structural_shape(data);errors=[];rows=[];prefix=f'structural:column:{floor}:{member}'
    def text(v,label):return require_text(v,label)
    def num(v,label,zero=False,integer=False):
        x=_decimal(v,label,True)
        if x<0 or (not zero and x==0) or (integer and x!=x.to_integral_value()):raise ValueError(label+' باید مثبت و معتبر باشد')
        return x
    def reviewed(r):text(r.get('source_ref'),'مرجع مستقل');text(r.get('approved_by') or r.get('reviewed_by'),'بازبین');component_reviewed(r)
    def calc(expr,values,units,output):return _decimal(evaluate(expr,values,variable_units=units,output_unit=output),'نتیجه')
    def cutting(p):
        if ('cut_length_m' in p)==('length_parts_m' in p):raise ValueError('فقط یک روش طول برش مجاز است')
        if 'cut_length_m' in p:return num(p['cut_length_m'],'طول برش')
        parts=p['length_parts_m'];total=_decimal(0,'جمع')
        if not isinstance(parts,list) or not any(v.get('kind')=='straight' for v in parts):raise ValueError('طول مستقیم صریح لازم است')
        for v in parts:
            if v.get('kind') not in PARTS:raise ValueError('نوع جزء برش نامعتبر')
            text(v.get('source_ref'),'مرجع خم/مهار/وصله');total+=num(v.get('length_m'),'طول جزء')
        return total
    try:
        source=data.get('source',{});sid=_validate_source(source,member)
        for k in ('plan_ref','detail_ref'):text(source.get(k),'مرجع پلان و دیتایل')
        for k in ('building_id','axis'):text(data.get(k),'ساختمان و محور')
        if not isinstance(data.get('rebars'),dict) or set(data['rebars'])!=set(KINDS['column'][4]):raise ValueError('گروه میلگرد ناقص یا ناشناخته؛ ثبت بخشی از داده مجاز نیست')
        g=data['geometry'];reviewed(g);n=num(g.get('count'),'تعداد',integer=True)
        if g.get('repeat_scope')!='identical_members':raise ValueError('دامنه ستون‌های هم‌تیپ باید صریح باشد')
        units=g.get('variable_units',{});height=calc('height',{'height':g.get('height')},{'height':units.get('height')},'m');num(height,'ارتفاع')
        if units.get('count') not in ('عدد','1'):raise ValueError('واحد تعداد معتبر لازم است')
        if g.get('shape')=='rectangular':
            num(g.get('width'),'عرض');num(g.get('depth'),'عمق')
            gross=calc('width*depth*height*count',{k:g.get(k) for k in ('width','depth','height','count')},{k:units.get(k) for k in ('width','depth','height','count')},'m3');num(gross,'حجم')
        elif g.get('shape')=='circular_column':
            if any(k in g for k in ('width','depth','sections')):
                raise ValueError('ابعاد مستطیلی و دایره‌ای نباید ترکیب شوند')
            diameter=calc('diameter',{'diameter':g.get('diameter')},{'diameter':units.get('diameter')},'m')
            num(diameter,'قطر ستون')
            gross=calc('pi*diameter**2*height*count/4',
                       {'pi':str(_CIRCULAR_PI),'diameter':str(diameter),'height':str(height),'count':str(n)},
                       {'pi':'1','diameter':'m','height':'m','count':'عدد'},'m3')
            num(gross,'حجم ستون دایره‌ای')
        elif g.get('shape')=='reviewed_sections':
            parts=g.get('sections');seen=set();cursor=_decimal(0,'شروع محور');gross=_decimal(0,'جمع')
            if not isinstance(parts,list) or not parts:raise ValueError('نواحی مقطع واقعی لازم است')
            for p in parts:
                reviewed(p);ident=text(p.get('id'),'شناسه مقطع')
                if ident in seen:raise ValueError('مقطع تکراری')
                seen.add(ident);a=num(p.get('start_m'),'شروع',True);b=num(p.get('end_m'),'پایان')
                if a!=cursor or b<=a:raise ValueError('فاصله یا هم‌پوشانی در نواحی ستون')
                cursor=b;w=num(p.get('width_m'),'عرض مقطع');d=num(p.get('depth_m'),'عمق مقطع');gross+=calc('width*depth*span*count',{'width':str(w),'depth':str(d),'span':str(b-a),'count':str(n)},{'width':'m','depth':'m','span':'m','count':'عدد'},'m3')
            if cursor!=height:raise ValueError('پوشش نواحی با ارتفاع واقعی برابر نیست')
        else:raise ValueError('قرارداد این نوبت فقط ستون مستطیلی است؛ دایره‌ای و مارپیچ نیازمند قرارداد مستقل')
        deductions=g.get('intersections');ded=_decimal(0,'جمع');seen=set()
        if not isinstance(deductions,list) or g.get('intersection_scope') not in ('per_member','total_group'):raise ValueError('فهرست و دامنه کسورات صریح لازم است')
        text(g.get('intersection_ref'),'مرجع دامنه کسورات')
        for p in deductions:
            reviewed(p);ident=text(p.get('id'),'شناسه تقاطع')
            if ident in seen:raise ValueError('تقاطع تکراری')
            seen.add(ident);ded+=num(p.get('volume_m3'),'کسر حجم')
        if g['intersection_scope']=='per_member':ded*=n
        net=gross-ded;num(net,'بتن خالص')
        rows.append({'source_id':prefix+':concrete','item':'column','code':'concrete','domain':'building','description':'بتن ستون '+member,'quantity':_wire(net),'unit':'m3','formula':('π ثابت ۵۰رقمی × قطر² × ارتفاع × تعداد / ۴ − کسورات مستند' if g.get('shape')=='circular_column' else 'جمع حجم نواحی واقعی × تعداد − کسورات مستند'),'params':{'gross_m3':_wire(gross),'net_m3':_wire(net),'deductions_m3':_wire(ded),'intersections':deepcopy(deductions),'geometry':deepcopy(g),'building_id':data['building_id'],'axis':data['axis'],**({'pi_policy':_CIRCULAR_PI_POLICY} if g.get('shape')=='circular_column' else {})}})
    except (ValueError,TypeError,KeyError) as e:errors.append('بتن و منشأ: '+str(e));n=None;height=None
    try:
        if n is None:raise ValueError('تعداد معتبر برای محاسبه قالب موجود نیست')
        f=data['formwork'];reviewed(f)
        if f.get('status')=='not_applicable':text(f.get('reason'),'علت عدم کاربرد')
        elif f.get('status')=='confirmed':
            scope=f.get('area_scope');text(f.get('area_scope_ref'),'مرجع دامنه قالب')
            if scope not in ('per_member','total_group'):raise ValueError('دامنه قالب صریح لازم است')
            faces=f.get('surfaces');seen=set();area=_decimal(0,'جمع');grossarea=_decimal(0,'جمع')
            if not isinstance(faces,list) or not faces:raise ValueError('سطوح واقعی لازم است')
            circular=data['geometry'].get('shape')=='circular_column'
            if circular:
                if len(faces)!=1 or faces[0].get('role')!='curved_wall':
                    raise ValueError('قالب دایره‌ای ساده باید یک سطح جانبی کامل و صریح داشته باشد')
            elif not {'side1','side2','side3','side4'}<=set(v.get('role') for v in faces):
                raise ValueError('هر چهار وجه ستون، حتی وجه بدون تماس، باید صریح اعلام شود')
            for face in faces:
                reviewed(face);ident=text(face.get('id'),'شناسه سطح')
                if ident in seen:raise ValueError('سطح تکراری')
                seen.add(ident)
                if type(face.get('contact')) is not bool:raise ValueError('تماس واقعی قالب باید صریح باشد')
                if circular:
                    if face.get('coverage')!='full_lateral' or face.get('area_method')!='circular_lateral' or 'gross_area_m2' in face:
                        raise ValueError('سطح جانبی دایره‌ای باید از قطر و ارتفاع مستند محاسبه شود')
                    diameter=calc('diameter',{'diameter':data['geometry'].get('diameter')},
                                  {'diameter':data['geometry'].get('variable_units',{}).get('diameter')},'m')
                    value=calc('pi*diameter*height',{'pi':str(_CIRCULAR_PI),'diameter':str(diameter),'height':str(height)},
                               {'pi':'1','diameter':'m','height':'m'},'m2')
                else:value=num(face.get('gross_area_m2'),'سطح ناخالص')
                grossarea+=value;loss=_decimal(0,'جمع');subseen=set()
                for p in face.get('deductions',[]):
                    reviewed(p);pid=text(p.get('id'),'شناسه کسر سطح')
                    if pid in subseen:raise ValueError('کسر سطح تکراری')
                    subseen.add(pid);loss+=num(p.get('area_m2'),'کسر سطح')
                if loss>value:raise ValueError('کسورات بیش از سطح')
                if face['contact']:area+=value-loss
            factor=n if scope=='per_member' else _decimal(1,'کل گروه');num(area,'قالب خالص')
            rows.append({'source_id':prefix+':formwork','item':'formwork','code':'formwork','domain':'building','description':'قالب ستون '+member,'quantity':_wire(area*factor),'unit':'m2','formula':'سطوح واقعی در تماس منهای کسورات × دامنه صریح','params':{'gross_area_m2':_wire(grossarea*factor),'surfaces':deepcopy(faces),'area_scope':scope}})
        else:raise ValueError('قالب نیازمند بازبینی')
    except (ValueError,TypeError,KeyError) as e:errors.append('قالب: '+str(e))
    physical=set()
    for group in KINDS['column'][4]:
        try:
            if n is None:raise ValueError('تعداد معتبر ستون برای وزن موجود نیست')
            bar=data['rebars'][group];reviewed(bar)
            if bar.get('status')=='not_applicable':text(bar.get('reason'),'علت عدم کاربرد');continue
            if bar.get('status')!='confirmed':raise ValueError('گروه نیازمند بازبینی')
            scope=bar.get('count_scope');text(bar.get('count_scope_ref'),'مرجع دامنه میلگرد')
            if scope not in ('per_member','total_group'):raise ValueError('دامنه تعداد میلگرد صریح لازم است')
            series=bar.get('segments')
            if not isinstance(series,list) or not series:raise ValueError('سری واقعی لازم است')
            if group=='ties':
                if scope!='per_member':raise ValueError('جانمایی خاموت باید برای یک ستون باشد')
                circular=data['geometry'].get('shape')=='circular_column'
                if circular:
                    if not all(p.get('shape_kind')=='spiral' for p in series):
                        raise ValueError('ستون دایره‌ای در این قرارداد فقط مارپیچ مستند دارد')
                else:
                    normalized=deepcopy(series)
                    for p in normalized:p['cut_length_m']=str(cutting(p))
                    validate_stirrup_zones(normalized,str(height))
                cursor=_decimal(0,'شروع');last=None
                for p in series:
                    if circular:
                        diameter=calc('diameter',{'diameter':data['geometry'].get('diameter')},
                                      {'diameter':data['geometry'].get('variable_units',{}).get('diameter')},'m')
                        start,end,_=_reviewed_spiral_length(p,diameter,check=num,require=text)
                        if start!=cursor or end<=start:raise ValueError('مرز نواحی مارپیچ فاصله یا هم‌پوشانی دارد')
                        cursor=end
                    else:
                        if p.get('shape_kind')!='rectangular':raise ValueError('قرارداد خاموت مستطیلی فقط شکل مستطیلی دارد')
                        start=num(p.get('start_m'),'شروع ناحیه',True);end=num(p.get('end_m'),'پایان ناحیه');first=num(p.get('first_bar_m'),'اولین خاموت',True);final=num(p.get('last_bar_m'),'آخرین خاموت',True)
                        if start!=cursor or end<=start or first<start or final>end or (last is not None and first<=last):raise ValueError('مرز یا جانمایی واقعی خاموت تکراری/ناسازگار است')
                        cursor=end;last=final
                if cursor!=height:raise ValueError('نواحی خاموت ارتفاع واقعی را پوشش نمی‌دهند')
            mass=_decimal(0,'جمع')
            for p in series:
                reviewed(p);ident=text(p.get('id'),'شناسه فیزیکی میلگرد')
                if ident in physical:raise ValueError('میلگرد فیزیکی تکراری است')
                physical.add(ident);num(p.get('nominal_diameter_mm'),'قطر');text(p.get('shape_ref'),'شکل');text(p.get('cut_length_ref'),'مرجع برش');text(p.get('unit_weight_source'),'مرجع وزن واحد');count=num(p.get('count'),'تعداد',integer=True);weight=num(p.get('unit_weight_kg_m'),'وزن واحد')
                if group=='ties' and data['geometry'].get('shape')=='circular_column':
                    if count!=1:raise ValueError('هر ناحیه مارپیچ یک قطعه فیزیکی مستقل و صریح دارد')
                    diameter=calc('diameter',{'diameter':data['geometry'].get('diameter')},
                                  {'diameter':data['geometry'].get('variable_units',{}).get('diameter')},'m')
                    _,_,cut=_reviewed_spiral_length(p,diameter,check=num,require=text)
                else:
                    cut=cutting(p)
                if group=='ties' and data['geometry'].get('shape')!='circular_column':
                    distance=num(p['last_bar_m'],'آخرین خاموت',True)-num(p['first_bar_m'],'اولین خاموت',True)
                    if distance!=(count-1)*num(p['spacing_m'],'فاصله'):raise ValueError('تعداد و جانمایی خاموت ناسازگار')
                mass+=calc('count*cut*weight',{'count':str(count),'cut':str(cut),'weight':str(weight)},{'count':'عدد','cut':'m','weight':'kg/m'},'kg')
            if scope=='per_member':mass*=n
            rows.append({'source_id':prefix+':rebar:'+group,'item':'rebar','code':'rebar','domain':'building','description':{'longitudinal':'میلگرد طولی','ties':'خاموت','crossties':'سنجاقی','starters':'انتظار و وصله'}[group]+' ستون '+member,'quantity':_wire(mass),'unit':'kg','formula':'تعداد صریح × برش مستند × وزن واحد × دامنه','params':{'series':deepcopy(series),'count_scope':scope,**({'helix_length_policy':_HELIX_LENGTH_POLICY,'pi_policy':_CIRCULAR_PI_POLICY} if group=='ties' and data['geometry'].get('shape')=='circular_column' else {})}})
        except (ValueError,TypeError,KeyError) as e:errors.append('میلگرد '+group+': '+str(e))
    return {'kind':'column','floor_id':floor,'member_id':member,'source_id':data.get('source',{}).get('source_id'),'ready':not errors,'blockers':errors,'rows':rows,'preview_only':True}


# Stage 2.3: a versioned specialization of the SAME register, Decimal AST,
# source guards, SQLite CAS and BOQ. Historical records retain old behavior.
_STAGE23_KINDS = frozenset({"tie_beam", "isolated_footing", "strip_footing", "mat_footing", "pile_cap"})


@_exact
def _preview_foundation_tie_specialist(data, engine):
    """Reviewed concrete, contact form and bar series; no design inference.

    This is the calculation core, NOT approval of a real foundation or an
    amendment mechanism for already committed quantities. Only explicit
    section geometry and physical bar schedules may become payable rows.
    """
    from core.takeoff.formulas import evaluate
    from core.takeoff.reviewed_components import PARTS
    from core.takeoff.beam_detail import component_reviewed

    kind, floor, member = _structural_shape(data)
    errors, rows = [], []
    prefix = f"structural:{kind}:{floor}:{member}"
    if kind not in _STAGE23_KINDS:
        return {"kind": kind, "floor_id": floor, "member_id": member,
                "source_id": "", "ready": False, "blockers": ["قرارداد تخصصی برای این عضو تعریف نشده است"],
                "rows": [], "preview_only": True}

    def txt(value, label):
        return require_text(value, label)

    def num(value, label, zero=False, integer=False):
        value = _decimal(value, label, True)
        if value < 0 or (value == 0 and not zero) or (integer and value != value.to_integral_value()):
            raise ValueError(label + ": مقدار مثبت/نامنفی مستند لازم است")
        return value

    def checked(record, label):
        if not isinstance(record, dict):
            raise ValueError(label + ": ساختار معتبر لازم است")
        txt(record.get('source_ref'), label + ': مرجع')
        txt(record.get('approved_by'), label + ': بازبین')
        return record

    def calc(expr, values, units, output):
        return _decimal(evaluate(expr, values, variable_units=units, output_unit=output), 'مقدار محاسبه')

    source_id = ''
    quantity_count = None
    axis = None
    try:
        source = data.get('source')
        source_id = _validate_source(source, member)
        txt(source.get('plan_ref'), 'مرجع پلان')
        txt(source.get('detail_ref'), 'مرجع دیتایل')
        txt(data.get('building_id'), 'ساختمان')
        checked(data.get('geometry'), 'هندسه')
        geometry = data['geometry']
        if geometry.get('shape') != 'rectangular':
            raise ValueError('هندسه منشوری مستطیلی لازم است؛ شکل متغیر به قرارداد مستقل نیاز دارد')
        if geometry.get('repeat_scope') != 'identical_members':
            raise ValueError('تکرار اعضای هم‌تیپ باید صریح باشد')
        fields = ('length','width','depth','count') if kind=='tie_beam' else ('length','width','thickness','count')
        units = geometry.get('variable_units')
        if not isinstance(units, dict) or set(units) != set(fields):
            raise ValueError('واحد ساختاریافته تمام ابعاد و تعداد لازم است')
        values = {k:geometry.get(k) for k in fields}
        quantity_count = num(calc('count',{'count':values['count']},{'count':units['count']},'عدد'), 'تعداد اعضا',integer=True)
        dims = {}
        for field in fields[:-1]:
            dims[field] = calc(field,{field:values[field]},{field:units[field]},'m')
            num(dims[field],field)
        if kind == 'tie_beam':
            axis = dims['length']
            expression='length*width*depth*count'
        else:expression='length*width*thickness*count'
        gross=calc(expression,values,units,'m3');num(gross,'حجم ناخالص')
        intersections=geometry.get('intersections')
        if not isinstance(intersections,list) or geometry.get('intersection_scope') not in ('per_member','total_group'):
            raise ValueError('کسورات و دامنه آن‌ها باید صریح باشند')
        txt(geometry.get('intersection_ref'),'مرجع کسورات')
        ids=set();deductions=_D(0)
        for item in intersections:
            checked(item,'کسر حجم')
            ident=txt(item.get('id'),'شناسه کسر')
            if ident in ids:raise ValueError('کسر حجم تکراری است')
            ids.add(ident)
            deductions+=num(item.get('volume_m3'),'حجم کسر')
        effective_deductions=deductions*(quantity_count if geometry['intersection_scope']=='per_member' else 1)
        net=gross-effective_deductions;num(net,'بتن خالص')
        rows.append({'source_id':prefix+':concrete','item':KINDS[kind][2],
                     'code':'concrete','domain':KINDS[kind][1],
                     'description':'بتن خالص '+KINDS[kind][0]+' '+member,
                     'quantity':_wire(net),'unit':'m3',
                     'formula':'حجم منشوری دقیق با واحدهای مستند × تعداد − کسورات تأییدشده',
                     'params':{'geometry':deepcopy(geometry),'gross_m3':_wire(gross),
                               'deductions_m3':_wire(effective_deductions),'net_m3':_wire(net),
                               'intersections':deepcopy(intersections),'building_id':data['building_id'],
                               'numeric_policy':'dimensional_decimal_v1'}})
    except (TypeError,ValueError,KeyError,AttributeError) as exc:
        errors.append('بتن و منشأ: '+str(exc));quantity_count=None

    try:
        if quantity_count is None:raise ValueError('هندسه و تعداد معتبر نیست')
        form=checked(data.get('formwork'),'قالب')
        if form.get('status')=='not_applicable':
            txt(form.get('reason'),'دلیل عدم کاربرد قالب')
        elif form.get('status')=='confirmed':
            scope=form.get('area_scope')
            if scope not in ('per_member','total_group'):raise ValueError('دامنه قالب صریح نیست')
            txt(form.get('area_scope_ref'),'مرجع دامنه قالب')
            surfaces=form.get('surfaces')
            if not isinstance(surfaces,list) or not surfaces:raise ValueError('سطوح قالب مستند نیست')
            seen=set();gross_area=_D(0);net_area=_D(0)
            for item in surfaces:
                checked(item,'سطح تماس')
                sid=txt(item.get('id'),'شناسه سطح')
                if sid in seen:raise ValueError('شناسه سطح قالب تکراری است')
                seen.add(sid)
                if type(item.get('contact')) is not bool:raise ValueError('تماس سطح باید صریح و بولی باشد')
                area=num(item.get('gross_area_m2'),'مساحت ناخالص سطح')
                sub=_D(0);seen_ded=set()
                for deduction in item.get('deductions',[]):
                    checked(deduction,'کسر سطح')
                    did=txt(deduction.get('id'),'شناسه کسر سطح')
                    if did in seen_ded:raise ValueError('کسر سطح تکراری است')
                    seen_ded.add(did)
                    sub+=num(deduction.get('area_m2'),'مساحت کسر')
                if sub>area:raise ValueError('کسر قالب از سطح بیشتر است')
                if item['contact']:
                    gross_area+=area;net_area+=area-sub
            if not net_area>0:raise ValueError('هیچ سطح واقعی قالب در تماس نیست')
            factor=quantity_count if scope=='per_member' else _D(1)
            rows.append({'source_id':prefix+':formwork','item':'formwork','code':'formwork',
                         'domain':'building','description':'قالب '+KINDS[kind][0]+' '+member,
                         'quantity':_wire(net_area*factor),'unit':'m2',
                         'formula':'جمع سطوح واقعی تماس منهای کسورات، در دامنه تأییدشده',
                         'params':{'surfaces':deepcopy(surfaces),'gross_area_m2':_wire(gross_area*factor),
                                   'area_scope':scope}})
        else:raise ValueError('وضعیت قالب باید مستند و بازبینی‌شده باشد')
    except (ValueError,TypeError,KeyError,AttributeError) as exc:errors.append('قالب: '+str(exc))

    rebars=data.get('rebars')
    groups=KINDS[kind][4]
    if not isinstance(rebars,dict) or set(rebars)!=set(groups):
        errors.append('گروه‌های میلگرد ناقص یا اضافه هستند')
    else:
        physical_ids=set()
        for group in groups:
            try:
                if quantity_count is None:raise ValueError('تعداد عضو معتبر نیست')
                bar=checked(rebars[group],'گروه میلگرد '+group)
                if bar.get('status')=='not_applicable':
                    txt(bar.get('reason'),'دلیل عدم کاربرد میلگرد');continue
                if bar.get('status')!='confirmed':raise ValueError('میلگرد نیازمند بازبینی است')
                scope=bar.get('count_scope')
                if scope not in ('per_member','total_group'):raise ValueError('دامنه میلگرد صریح نیست')
                txt(bar.get('count_scope_ref'),'مرجع دامنه میلگرد')
                segments=bar.get('segments')
                if not isinstance(segments,list) or not segments:raise ValueError('سری میلگرد لازم است')
                used=set();mass=_D(0);cursor=_D(0);previous_station=None
                for segment in segments:
                    checked(segment,'سری میلگرد')
                    ident=txt(segment.get('id'),'شناسه سری میلگرد')
                    if ident in used or ident in physical_ids:raise ValueError('شناسه فیزیکی سری تکراری است')
                    used.add(ident);physical_ids.add(ident)
                    quantity=num(segment.get('count'),'تعداد میلگرد',integer=True)
                    num(segment.get('nominal_diameter_mm'),'قطر اسمی میلگرد')
                    txt(segment.get('shape_ref'),'مرجع شکل میلگرد')
                    unit_weight=num(segment.get('unit_weight_kg_m'),'وزن واحد میلگرد')
                    txt(segment.get('unit_weight_source'),'منبع وزن واحد')
                    if ('cut_length_m' in segment)==('length_parts_m' in segment):
                        raise ValueError('طول برش باید دقیقاً یک روش داشته باشد')
                    if 'cut_length_m' in segment:
                        length=num(segment['cut_length_m'],'طول برش');txt(segment.get('cut_length_ref'),'مرجع طول برش')
                    else:
                        parts=segment['length_parts_m']
                        if not isinstance(parts,list) or not any(isinstance(p,dict) and p.get('kind')=='straight' for p in parts):
                            raise ValueError('طول مستقیم و اجزای برش لازم است')
                        length=_D(0)
                        for part in parts:
                            if not isinstance(part,dict) or part.get('kind') not in PARTS:
                                raise ValueError('شکل جزء میلگرد نامعتبر است')
                            txt(part.get('source_ref'),'مرجع جزء برش')
                            length+=num(part.get('length_m'),'طول جزء میلگرد')
                    if kind=='tie_beam' and group=='stirrups':
                        if scope!='per_member':raise ValueError('خاموت شناژ باید دامنه هر عضو داشته باشد')
                        start=num(segment.get('start_m'),'شروع ناحیه',True)
                        end=num(segment.get('end_m'),'پایان ناحیه')
                        first=num(segment.get('first_bar_m'),'اولین خاموت',True)
                        last=num(segment.get('last_bar_m'),'آخرین خاموت',True)
                        spacing=num(segment.get('spacing_m'),'فاصله خاموت')
                        if start!=cursor or end<=start or first<start or last>end or first>last:
                            raise ValueError('مرز خاموت/جانمایی ناسازگار')
                        if last-first!=(quantity-1)*spacing:
                            raise ValueError('تعداد و فاصله خاموت با موقعیت‌ها ناسازگار است')
                        if previous_station is not None and first<=previous_station:
                            raise ValueError('خاموت مرزی دوبار شمرده شده است')
                        if first-start>spacing or end-last>spacing:
                            raise ValueError('فاصله ابتدا یا انتهای ناحیه بیش از گام صریح است')
                        previous_station=last;cursor=end
                    mass+=quantity*length*unit_weight
                if kind=='tie_beam' and group=='stirrups' and cursor!=axis:
                    raise ValueError('خاموت‌ها کل محور شناژ را پوشش نمی‌دهند')
                factor=quantity_count if scope=='per_member' else _D(1)
                rows.append({'source_id':prefix+':rebar:'+group,'item':'rebar','code':'rebar',
                             'domain':'building','description':'میلگرد '+group+' '+KINDS[kind][0]+' '+member,
                             'quantity':_wire(mass*factor),'unit':'kg',
                             'formula':'تعداد واقعی × طول برش مستند × وزن واحد × دامنه شمارش',
                             'params':{'series':deepcopy(segments),'count_scope':scope}})
            except (ValueError,TypeError,KeyError,AttributeError) as exc:
                errors.append('میلگرد '+group+': '+str(exc))
    return {'kind':kind,'floor_id':floor,'member_id':member,'source_id':source_id,
            'ready':not errors,'blockers':errors,'rows':rows,'preview_only':True}
