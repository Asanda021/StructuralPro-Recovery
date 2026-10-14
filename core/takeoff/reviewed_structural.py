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
        if record and kind=='column':
            from core.takeoff.manual_formula_amendments import beam_current
            return beam_current(project,_key(kind,floor,member_id))
        return deepcopy(record)

    def save_draft(self, project_id: str, draft: dict, *, expected_revision: int = 0, reason: str = "ثبت پیش‌نویس"):
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
        from core.takeoff.manual_formula_amendments import digest as payload_digest
        proposal=deepcopy(draft);review=proposal.pop('component_review',None)
        fresh=kind=='column' and draft.get('measurement_policy')=='column_specialist_v1' and isinstance(review,dict) and review.get('base_revision')==expected_revision and bool(review.get('reviewer')) and review.get('digest')==payload_digest(proposal)
        if fresh and not preview_member(proposal,self.engine)['ready']:raise ValueError('بازبینی داده ناقص معتبر نیست')
        if previous and previous['data'].get('measurement_policy')=='column_specialist_v1':
            if draft.get('measurement_policy')!='column_specialist_v1':raise ValueError('حذف قرارداد تخصصی ستون ممنوع است')
            if any(draft.get(k)!=previous['data'].get(k) for k in ('building_id','axis','member_id','floor_id')) or any(draft.get('source',{}).get(k)!=previous['data'].get('source',{}).get(k) for k in ('source_id','mode')):raise ValueError('تغییر هویت فیزیکی ستون نیازمند گردش مستقل است')
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
        rows.append({'source_id':prefix+':concrete','item':'column','code':'concrete','domain':'building','description':'بتن ستون '+member,'quantity':_wire(net),'unit':'m3','formula':'جمع حجم نواحی واقعی × تعداد − کسورات مستند','params':{'gross_m3':_wire(gross),'net_m3':_wire(net),'deductions_m3':_wire(ded),'intersections':deepcopy(deductions),'geometry':deepcopy(g),'building_id':data['building_id'],'axis':data['axis']}})
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
            if not {'side1','side2','side3','side4'}<=set(v.get('role') for v in faces):raise ValueError('هر چهار وجه ستون، حتی وجه بدون تماس، باید صریح اعلام شود')
            for face in faces:
                reviewed(face);ident=text(face.get('id'),'شناسه سطح')
                if ident in seen:raise ValueError('سطح تکراری')
                seen.add(ident)
                if type(face.get('contact')) is not bool:raise ValueError('تماس واقعی قالب باید صریح باشد')
                value=num(face.get('gross_area_m2'),'سطح ناخالص');grossarea+=value;loss=_decimal(0,'جمع');subseen=set()
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
                normalized=deepcopy(series)
                for p in normalized:p['cut_length_m']=str(cutting(p))
                validate_stirrup_zones(normalized,str(height))
                cursor=_decimal(0,'شروع');last=None
                for p in series:
                    if p.get('shape_kind')!='rectangular':raise ValueError('قرارداد خاموت این نوبت فقط مستطیلی است؛ مارپیچ مسدود')
                    start=num(p.get('start_m'),'شروع ناحیه',True);end=num(p.get('end_m'),'پایان ناحیه');first=num(p.get('first_bar_m'),'اولین خاموت',True);final=num(p.get('last_bar_m'),'آخرین خاموت',True)
                    if start!=cursor or end<=start or first<start or final>end or (last is not None and first<=last):raise ValueError('مرز یا جانمایی واقعی خاموت تکراری/ناسازگار است')
                    cursor=end;last=final
                if cursor!=height:raise ValueError('نواحی خاموت ارتفاع واقعی را پوشش نمی‌دهند')
            mass=_decimal(0,'جمع')
            for p in series:
                reviewed(p);ident=text(p.get('id'),'شناسه فیزیکی میلگرد')
                if ident in physical:raise ValueError('میلگرد فیزیکی تکراری است')
                physical.add(ident);num(p.get('nominal_diameter_mm'),'قطر');text(p.get('shape_ref'),'شکل');text(p.get('cut_length_ref'),'مرجع برش');text(p.get('unit_weight_source'),'مرجع وزن واحد');count=num(p.get('count'),'تعداد',integer=True);weight=num(p.get('unit_weight_kg_m'),'وزن واحد')
                cut=cutting(p)
                if group=='ties':
                    distance=num(p['last_bar_m'],'آخرین خاموت',True)-num(p['first_bar_m'],'اولین خاموت',True)
                    if distance!=(count-1)*num(p['spacing_m'],'فاصله'):raise ValueError('تعداد و جانمایی خاموت ناسازگار')
                mass+=calc('count*cut*weight',{'count':str(count),'cut':str(cut),'weight':str(weight)},{'count':'عدد','cut':'m','weight':'kg/m'},'kg')
            if scope=='per_member':mass*=n
            rows.append({'source_id':prefix+':rebar:'+group,'item':'rebar','code':'rebar','domain':'building','description':{'longitudinal':'میلگرد طولی','ties':'خاموت','crossties':'سنجاقی','starters':'انتظار و وصله'}[group]+' ستون '+member,'quantity':_wire(mass),'unit':'kg','formula':'تعداد صریح × برش مستند × وزن واحد × دامنه','params':{'series':deepcopy(series),'count_scope':scope}})
        except (ValueError,TypeError,KeyError) as e:errors.append('میلگرد '+group+': '+str(e))
    return {'kind':'column','floor_id':floor,'member_id':member,'source_id':data.get('source',{}).get('source_id'),'ready':not errors,'blockers':errors,'rows':rows,'preview_only':True}
