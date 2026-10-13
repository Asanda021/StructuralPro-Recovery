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
        shape = geometry.get("shape", "rectangular")
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
                        if kind == "column" and shape == "reviewed_sections" and raw_axis is None:
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
        return deepcopy((project.get(REGISTER) or {}).get(_key(kind, floor, member_id)))

    def save_draft(self, project_id: str, draft: dict, *, expected_revision: int = 0):
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
        if previous and previous.get("status") == "committed":
            raise ValueError("عضو قبلاً به ریزمتره انتقال یافته است")
        revision = previous["revision"] if previous else 0
        if revision != expected_revision:
            raise RuntimeError("تعارض نسخه؛ دوباره بارگذاری کنید")
        if previous and previous["data"].get("source") != source:
            if (draft.get("geometry", {}).get("approved_by") or
                    any(isinstance(x, dict) and x.get("status") in ("confirmed", "not_applicable")
                        for x in [draft.get("formwork")] + list(draft.get("rebars", {}).values()))):
                raise ValueError("منبع تغییر یافته است؛ تأیید هندسه، قالب و آرماتور باید بازنشانی شوند")
        source_id = source.get("source_id") if isinstance(source, dict) else None
        if source_id:
            require_source_unused(project, source_id, exclude=(REGISTER, key))
        require_reset_of_changed_approvals(previous["data"] if previous else None, draft)
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
