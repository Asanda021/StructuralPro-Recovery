"""Reviewed beam-detail takeoff against the existing ProjectStore and TakeoffEngine.

Drafts remain in ProjectStore's SQLite-backed project payload.  Only a completely
reviewed beam can be atomically transferred to the existing takeoffs/BOQ path.
This module does NOT parse reinforcement or infer section dimensions from drawings.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import math
from typing import Any

from core.takeoff.boq import build_boq
from core.drawings.beam_detail_match import validate_evidence_link
from core.takeoff.stirrup_zones import validate_stirrup_zones

BAR_TYPES = ("longitudinal", "stirrups", "side_bars", "crossties", "additional")
BAR_LABELS = {
    "longitudinal": "میلگرد طولی", "stirrups": "خاموت", "side_bars": "کمرکش تیر",
    "crossties": "سنجاقی", "additional": "میلگرد تقویتی",
}
INITIAL_STATUSES = {
    "longitudinal": "needs_detail", "stirrups": "needs_detail", "side_bars": "unreviewed",
    "crossties": "unreviewed", "additional": "unreviewed",
}
VALID_STATUSES = frozenset({"needs_detail", "unreviewed", "needs_review", "confirmed", "not_applicable"})
REGISTER = "beam_detail_register"


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} الزامی است")
    return value.strip()


def _number(value: Any, label: str, *, zero: bool = False, integer: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} باید عدد معتبر باشد")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} باید عدد معتبر باشد") from exc
    if not math.isfinite(number) or number < 0 or (number == 0 and not zero):
        raise ValueError(f"{label} باید {'نامنفی' if zero else 'مثبت'} و متناهی باشد")
    if integer and not number.is_integer():
        raise ValueError(f"{label} باید عدد صحیح باشد")
    return number


_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _beam_key(floor_id: str, beam_id: str) -> str:
    """One physical identity despite Latin/Persian digits or letter casing."""
    normalized = [" ".join(value.translate(_DIGITS).casefold().split())
                  for value in (floor_id, beam_id)]
    return json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))


def empty_beam(floor_id: str, beam_id: str) -> dict[str, Any]:
    """Initial UI state: never convert 'unreviewed' to absent/zero."""
    return {
        "floor_id": _text(floor_id, "طبقه"), "beam_id": _text(beam_id, "شناسه تیر"),
        "source": {}, "geometry": {}, "formwork": {},
        "bars": {kind: {"status": status} for kind, status in INITIAL_STATUSES.items()},
    }


def _validate_identity(data: dict[str, Any]) -> tuple[str, str]:
    if not isinstance(data, dict):
        raise ValueError("اطلاعات تیر باید ساختار معتبر داشته باشد")
    return _text(data.get("floor_id"), "طبقه"), _text(data.get("beam_id"), "شناسه تیر")


def _validate_source(source: dict[str, Any]) -> None:
    if not isinstance(source, dict):
        raise ValueError("ساختار منبع نقشه معتبر نیست")
    mode = source.get("mode")
    if mode not in {"manual", "drawing"}:
        raise ValueError("منبع باید دستی یا نقشه تأییدشده باشد")
    _text(source.get("source_id"), "شناسه یکتای برداشت")
    if mode == "drawing":
        digest = _text(source.get("sha256"), "اثر انگشت SHA-256 نقشه")
        if len(digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in digest):
            raise ValueError("SHA-256 نقشه باید ۶۴ رقم شانزده‌شانزدهی باشد")
        _number(source.get("page"), "صفحه نقشه", integer=True)


def _validate_bar_shape(bars: dict[str, Any]) -> None:
    if not isinstance(bars, dict) or set(bars) != set(BAR_TYPES):
        raise ValueError("وضعیت هر پنج قلم میلگرد باید جداگانه ثبت شود")
    for name, bar in bars.items():
        if not isinstance(bar, dict) or bar.get("status") not in VALID_STATUSES:
            raise ValueError(f"وضعیت {BAR_LABELS[name]} معتبر نیست")
        if "count" in bar:
            _number(bar["count"], "تعداد پیشنهادی میلگرد", integer=True)
        if "nominal_diameter_mm" in bar:
            nominal = _number(bar["nominal_diameter_mm"], "قطر اسمی میلگرد")
            if nominal > 100:
                raise ValueError("قطر اسمی میلگرد خارج از محدوده معتبر است")


def preview_beam(data: dict[str, Any], engine: Any) -> dict[str, Any]:
    """Return individually approved rows and blockers; never invent missing values.

    Preview rows are NOT suitable for final BOQ until `ready` becomes True.
    """
    floor_id, beam_id = _validate_identity(data)
    bars = data.get("bars")
    _validate_bar_shape(bars)
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    source = data.get("source", {})
    try:
        _validate_source(source)
        validate_evidence_link(source, beam_id)
    except ValueError as exc:
        errors.append(str(exc))

    src_id = source.get("source_id", "") if isinstance(source, dict) else ""
    base_id = f"beam-detail:{floor_id}:{beam_id}"
    geometry = data.get("geometry", {})
    if not isinstance(geometry, dict):
        geometry = {}
    try:
        _text(geometry.get("approved_by"), "تأییدکننده هندسه")
        _text(geometry.get("source_ref"), "مرجع ابعاد تیر")
        dims = {key: _number(geometry.get(key), key) for key in ("length", "width", "depth")}
        dims["count"] = int(_number(geometry.get("count"), "تعداد تیر", integer=True))
        deduction = _number(geometry.get("deductions_m3"), "کسر هم‌پوشانی بتن", zero=True)
        gross = engine.calculate("building", "beam", description=f"بتن تیر {beam_id}", **dims)
        net = gross.quantity - deduction
        if not math.isfinite(net) or net <= 0:
            raise ValueError("کسر هم‌پوشانی، حجم خالص بتن تیر را نامعتبر می‌کند")
        rows.append({"source_id": base_id+":concrete", "code": "beam", "domain": "building",
                     "description": f"بتن خالص تیر {beam_id}", "quantity": net, "unit": "m3",
                     "formula": f"{gross.formula} − کسر هم‌پوشانی مستند {deduction:g} m³",
                     "params": {**dims, "deductions_m3": deduction}})
    except (ValueError, TypeError, KeyError) as exc:
        errors.append("بتن تیر: " + str(exc))

    formwork = data.get("formwork", {})
    if not isinstance(formwork, dict):
        formwork = {}
    try:
        _text(formwork.get("approved_by"), "تأییدکننده قالب‌بندی")
        _text(formwork.get("source_ref"), "مرجع سطوح در تماس با قالب")
        area = _number(formwork.get("net_area_m2"), "مساحت خالص قالب‌بندی")
        rows.append({"source_id": base_id+":formwork", "code": "formwork", "domain": "building",
                     "description": f"قالب‌بندی تیر {beam_id}", "quantity": area, "unit": "m2",
                     "formula": "سطوح واقعی و تأییدشده در تماس با قالب", "params": {"net_area_m2": area}})
    except (ValueError, TypeError) as exc:
        errors.append("قالب‌بندی: " + str(exc))

    for kind in BAR_TYPES:
        bar = bars[kind]
        state = bar["status"]
        if state == "not_applicable":
            try:
                _text(bar.get("approved_by"), "تأییدکننده عدم کاربرد")
                _text(bar.get("reason"), "دلیل عدم کاربرد")
                _text(bar.get("source_ref"), "مرجع بررسی دیتایل")
            except ValueError as exc:
                errors.append(f"{BAR_LABELS[kind]}: {exc}")
        elif state == "confirmed":
            try:
                _text(bar.get("approved_by"), "تأییدکننده میلگرد")
                _text(bar.get("source_ref"), "مرجع دیتایل میلگرد")
                # Explicit segments support variable stirrup zones and differing bar sizes.
                # Cut length includes reviewed hooks, laps and bends; never infer it from span.
                segments = bar.get("segments", [bar])
                if kind == "stirrups" and "segments" in bar:
                    # A partial or overlapping zone schedule must never enter BOQ.
                    segments = validate_stirrup_zones(segments, geometry.get("length"))
                if not isinstance(segments, list) or not segments:
                    raise ValueError("بازه‌های میلگرد باید فهرست غیرخالی باشند")
                quantities = []
                validated = []
                for segment in segments:
                    if not isinstance(segment, dict):
                        raise ValueError("دیتایل هر بازه میلگرد باید ساختار معتبر داشته باشد")
                    _text(segment.get("source_ref"), "مرجع بازه میلگرد")
                    count = int(_number(segment.get("count"), "تعداد میلگرد", integer=True))
                    cut = _number(segment.get("cut_length_m"), "طول برش تأییدشده")
                    weight = _number(segment.get("unit_weight_kg_m"), "وزن واحد تأییدشده")
                    result = engine.calculate("building", "rebar", description=BAR_LABELS[kind],
                                              count=count, length=cut, unit_weight=weight)
                    quantities.append(result.quantity)
                    segment_parameters = {"count": count, "length": cut, "unit_weight": weight,
                                          "source_ref": segment["source_ref"]}
                    if kind == "stirrups" and "segments" in bar:
                        segment_parameters.update({field: segment[field] for field in (
                            "name", "start_m", "end_m", "spacing_m", "first_bar_m", "last_bar_m")})
                    validated.append(segment_parameters)
                total = math.fsum(quantities)
                if not math.isfinite(total) or total <= 0:
                    raise ValueError("مجموع وزن میلگرد معتبر نیست")
                rows.append({"source_id": base_id+":"+kind, "code": "rebar", "domain": "building",
                             "description": f"{BAR_LABELS[kind]} تیر {beam_id}", "quantity": total,
                             "unit": "kg", "formula": "جمع (تعداد × طول برش × وزن واحد) بازه‌های تأییدشده",
                             "params": {"segments": validated}})
            except (ValueError, TypeError, KeyError) as exc:
                errors.append(f"{BAR_LABELS[kind]}: {exc}")
        else:
            errors.append(f"{BAR_LABELS[kind]}: هنوز {state} است")

    if not rows:
        errors.append("هیچ کمیت تأییدشده‌ای قابل پیش‌نمایش نیست")
    return {"floor_id": floor_id, "beam_id": beam_id, "source_id": src_id,
            "ready": not errors, "blockers": errors, "preview_only": True, "rows": rows}


class BeamDetailWorkflow:
    """SQLite-backed beam detail lifecycle reusing canonical store and BOQ engine."""

    def __init__(self, store: Any, engine: Any):
        self.store, self.engine = store, engine

    def _project(self, project_id: str) -> tuple[dict[str, Any], str]:
        digest = self.store.current_digest(project_id)
        # Existing ProjectStore caches payloads; invalidate before an optimistic write.
        if hasattr(self.store, "_cache"):
            self.store._cache.pop(project_id, None)
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        return project, digest

    def get(self, project_id: str, floor_id: str, beam_id: str) -> dict[str, Any] | None:
        project = self.store.get(project_id)
        if project is None:
            raise KeyError(project_id)
        key = _beam_key(_text(floor_id, "طبقه"), _text(beam_id, "شناسه تیر"))
        record = (project.get(REGISTER) or {}).get(key)
        return deepcopy(record) if record else None

    def save_draft(self, project_id: str, draft: dict[str, Any], *, expected_revision: int = 0) -> dict[str, Any]:
        floor_id, beam_id = _validate_identity(draft)
        _validate_bar_shape(draft.get("bars"))
        # Reject malformed source at the time it is supplied; an empty source is okay for a draft.
        if draft.get("source"):
            _validate_source(draft["source"])
            validate_evidence_link(draft["source"], beam_id)
        try:
            json.dumps(draft, allow_nan=False, ensure_ascii=False)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError("داده غیرمتناهی یا غیرقابل ذخیره در فرم تیر وجود دارد") from exc
        project, digest = self._project(project_id)
        register = project.setdefault(REGISTER, {})
        if not isinstance(register, dict):
            raise ValueError("ساختار دفتر متره تیر معتبر نیست")
        key = _beam_key(floor_id, beam_id)
        previous = register.get(key)
        if previous and previous.get("status") == "committed":
            raise ValueError("تیر به ریزمتره منتقل شده؛ تغییر آن نیازمند فرایند اصلاح نسخه است")
        revision = previous.get("revision", 0) if previous else 0
        if expected_revision != revision:
            raise RuntimeError("تعارض نسخه متره تیر؛ اطلاعات را دوباره بارگذاری کنید")
        source = draft.get("source", {})
        if previous and previous["data"].get("source") != source:
            if any(x["status"] in {"confirmed", "not_applicable"} for x in draft["bars"].values()):
                raise ValueError("منبع نقشه تغییر کرده؛ ابتدا تأیید اقلام میلگرد را بازنشانی کنید")
        if source and source.get("source_id"):
            sid = source["source_id"]
            for other_key, other in register.items():
                if other_key != key and other.get("data", {}).get("source", {}).get("source_id") == sid:
                    raise ValueError("منبع برداشت تیر تکراری است")
            if any(str(row.get("source_id", "")) == sid for row in project.get("takeoffs", [])):
                raise ValueError("این منبع برداشت قبلاً در ریزمتره ثبت شده است")
        payload = deepcopy(draft)
        entry = {"status": "draft", "revision": revision + 1, "data": payload,
                 "updated_at": datetime.now(timezone.utc).isoformat()}
        register[key] = entry
        self.store.save(project_id, project, expected_digest=digest)
        return deepcopy(entry)

    def preview(self, project_id: str, floor_id: str, beam_id: str) -> dict[str, Any]:
        entry = self.get(project_id, floor_id, beam_id)
        if entry is None:
            raise KeyError(beam_id)
        result = preview_beam(entry["data"], self.engine)
        result["revision"] = entry["revision"]
        result["committed"] = entry["status"] == "committed"
        return result

    def commit(self, project_id: str, floor_id: str, beam_id: str, *, expected_revision: int) -> dict[str, Any]:
        project, digest = self._project(project_id)
        key = _beam_key(_text(floor_id, "طبقه"), _text(beam_id, "شناسه تیر"))
        entry = (project.get(REGISTER) or {}).get(key)
        if not entry:
            raise KeyError(beam_id)
        if entry["status"] == "committed":
            raise ValueError("این تیر قبلاً به ریزمتره منتقل شده است")
        if entry["revision"] != expected_revision:
            raise RuntimeError("تعارض نسخه متره تیر؛ ثبت نهایی رد شد")
        report = preview_beam(entry["data"], self.engine)
        if not report["ready"]:
            raise ValueError("متره ناقص است؛ انتقال به ریزمتره ممنوع: " + "؛ ".join(report["blockers"]))
        data = entry["data"]
        source = data["source"]
        prior = project.get("takeoffs", [])
        existing_ids = {str(x.get("source_id", "")) for x in prior}
        new_ids = {x["source_id"] for x in report["rows"]}
        if existing_ids.intersection(new_ids) or source["source_id"] in existing_ids:
            raise ValueError("متره تکراری است؛ انتقال دوباره متوقف شد")
        new_takeoffs = deepcopy(prior)
        for row in report["rows"]:
            new_takeoffs.append({
                "id": f"beam-detail:{key}:{row['code']}:{row['source_id'].rsplit(':', 1)[-1]}",
                "member_code": beam_id, "source_id": row["source_id"], "domain": row["domain"],
                "item": row["code"], "params": row["params"], "revision": entry["revision"],
                "description": row["description"], "system": floor_id,
                "provenance": deepcopy(source),
                "quantities": [{"code": row["code"], "title": row["description"],
                                "system": floor_id, "unit": row["unit"], "amount": row["quantity"],
                                "formula": row["formula"], "warning": "",
                                "price_code": None, "unit_price": None}],
            })
        boq_inputs = []
        for takeoff in new_takeoffs:
            for q in takeoff.get("quantities", []):
                boq_inputs.append({"source": takeoff.get("source_id", "") or "manual",
                                   "source_id": takeoff.get("source_id", ""), "source_type": "takeoff",
                                   "description": q.get("title", ""), "quantity": q.get("amount", 0),
                                   "unit": q.get("unit", ""), "item_code": q.get("code", ""),
                                   "price_code": q.get("price_code"), "unit_price": q.get("unit_price"),
                                   "category": takeoff.get("domain", "building"),
                                   "group": takeoff.get("domain", "building")})
        project["takeoffs"] = new_takeoffs
        project["boq"] = build_boq(boq_inputs)
        entry["status"] = "committed"
        entry["committed_at"] = datetime.now(timezone.utc).isoformat()
        entry["committed_source_ids"] = sorted(new_ids)
        self.store.save(project_id, project, expected_digest=digest)
        return {"status": "committed", "takeoff_rows": len(report["rows"]),
                "revision": entry["revision"], "source_ids": sorted(new_ids)}
