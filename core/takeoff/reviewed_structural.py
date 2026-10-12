"""Reviewed concrete column, grade-beam and foundation takeoff, using canonical engines.

Beam takeoff stays in BeamDetailWorkflow. This module handles the other
structural members and never derives unobserved reinforcement or form faces.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from typing import Any

from core.takeoff.boq import build_boq
from core.drawings.beam_detail_match import validate_evidence_link
from core.takeoff.reviewed_components import (
    require_text, positive, reviewed_steel, net_concrete, net_formwork,
)

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
        dims = {field: (int(positive(geometry.get(field), field, integer=True))
                        if field == "count" else positive(geometry.get(field), field))
                for field in fields}
        gross = engine.calculate(domain, item, description=f"بتن {title} {member_id}", **dims)
        if gross.unit != "m3":
            raise ValueError("واحد حجم سازه ناسازگار است")
        net, deductions = net_concrete(gross.quantity, geometry.get("intersections"))
        rows.append({"source_id": prefix + ":concrete", "item": item, "code": "concrete",
                     "domain": domain, "description": f"بتن خالص {title} {member_id}",
                     "quantity": net, "unit": "m3",
                     "formula": "حجم ناخالص موتور اصلی منهای کسورات مستقل تأییدشده",
                     "params": {"dimensions": dims, "intersections": deductions,
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
            if any(isinstance(x, dict) and x.get("status") in ("confirmed", "not_applicable")
                   for x in [draft.get("formwork")] + list(draft.get("rebars", {}).values())):
                raise ValueError("منبع تغییر یافته است؛ تأییدها باید بازنشانی شوند")
        source_id = source.get("source_id") if isinstance(source, dict) else None
        if source_id:
            for other_key, item in register.items():
                if other_key != key and item["data"].get("source", {}).get("source_id") == source_id:
                    raise ValueError("منبع متره تکراری است")
            for item in (project.get("beam_detail_register") or {}).values():
                if item["data"].get("source", {}).get("source_id") == source_id:
                    raise ValueError("منبع نقشه قبلاً برای تیر استفاده شده است")
            if any(row.get("source_id") == source_id for row in project.get("takeoffs", [])):
                raise ValueError("منبع قبلاً در ریزمتره استفاده شده است")
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
        prior_ids = {row.get("source_id") for row in prior}
        ids = {row["source_id"] for row in report["rows"]}
        if prior_ids & ids or report["source_id"] in prior_ids:
            raise ValueError("ریزمتره تکراری است")
        # No two members may subtract the same physical concrete intersection.
        current_deductions = {d["id"] for row in report["rows"] if row["code"] == "concrete"
                              for d in row["params"]["intersections"]}
        for other in prior:
            if other.get("item") == "concrete":
                other_deductions = other.get("params", {}).get("intersections", [])
                if current_deductions & {d.get("id") for d in other_deductions}:
                    raise ValueError("حجم هم‌پوشانی قبلاً از عضو دیگری کسر شده است")
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
        boq_input = [{"source": row.get("source_id", ""), "source_id": row["source_id"],
                      "source_type": "takeoff", "description": q["title"],
                      "quantity": q["amount"], "unit": q["unit"], "item_code": q["code"],
                      "price_code": q["price_code"], "unit_price": q["unit_price"],
                      "category": row["domain"], "group": row["domain"]}
                     for row in takeoffs for q in row.get("quantities", ())]
        project["boq"] = build_boq(boq_input)
        project["takeoffs"] = takeoffs
        record["status"] = "committed"
        record["committed_source_ids"] = sorted(ids)
        record["committed_at"] = datetime.now(timezone.utc).isoformat()
        self.store.save(project_id, project, expected_digest=digest)
        return {"status": "committed", "revision": record["revision"],
                "takeoff_rows": len(report["rows"]), "source_ids": sorted(ids)}
