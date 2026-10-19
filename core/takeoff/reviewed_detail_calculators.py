"""Detail-backed physical quantities for reviewed concrete, roof, steel and timber.

No bar ratios, unit masses, member counts, void shapes, standard densities or
waste coefficients are assumed. A row can become billable ONLY after the
actual schedule and material source have been entered and approved.
"""
from __future__ import annotations

import math
from typing import Any

from core.takeoff.reviewed_components import positive, require_text, _exact_float_sum

_SCHEMAS = {
    "concrete_regions": "m3",
    "rectangle_volume": "m3",
    "net_surface": "m2",
    "steel_profile_schedule": "kg",
    "steel_plate_schedule": "kg",
    "timber_volume_schedule": "m3",
    "piece_schedule": "عدد",
}

def _series(row: dict, name: str) -> list[dict]:
    entries = row.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{name}: جدول دارای حداقل یک ردیف تأییدشده لازم است")
    seen = set()
    result = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"{name}: ردیف جزئیات نامعتبر است")
        eid = require_text(entry.get("id"), "شناسه فیزیکی جزء")
        if eid in seen:
            raise ValueError("جزء فیزیکی با شناسه تکراری در جدول آمده است")
        seen.add(eid)
        ref = require_text(entry.get("source_ref"), "مرجع دیتایل جزء")
        reviewer = require_text(entry.get("approved_by"), "تأییدکننده دیتایل جزء")
        result.append({**entry, "id": eid, "source_ref": ref, "approved_by": reviewer})
    return result


def _length(row: dict, key: str) -> float:
    return positive(row.get(key), key)

def _count(row: dict) -> int:
    return int(positive(row.get("count"), "تعداد واقعی", integer=True))

def _ratio(gross: float, deduction: float, label: str) -> float:
    value = gross - deduction
    if deduction > 0 and value == gross:
        raise ValueError(f"{label}: کسر غیرصفر در دقت محاسبات قبلی حذف می‌شود")
    return positive(value, label)


def calculate_reviewed_detail(kind: str, details: dict[str, Any]) -> dict[str, Any]:
    if kind not in _SCHEMAS:
        raise ValueError("روش محاسبه جزئیات معتبر نیست")
    if not isinstance(details, dict) or set(details) != {"entries"}:
        raise ValueError("فرمت دیتایل باید فقط حاوی جدول مستند entries باشد")
    entries = _series(details, kind)
    totals = []
    normalized = []
    consumed_voids: set[str] = set()
    for entry in entries:
        label = entry["id"]
        n = _count(entry) if kind != "concrete_regions" else 1
        measured = None
        evidence: dict[str, Any] = {}
        if kind == "rectangle_volume":
            if set(entry) != {"id", "source_ref", "approved_by", "count",
                              "length_m", "width_m", "thickness_m"}:
                raise ValueError("ابعاد/تعداد بتن مستطیلی ناقص یا دارای فیلد نامعتبرند")
            measured = n * _length(entry, "length_m") * _length(entry, "width_m") * _length(entry, "thickness_m")
        elif kind == "net_surface":
            if set(entry) != {"id", "source_ref", "approved_by", "count",
                              "length_m", "width_m", "openings_m2"}:
                raise ValueError("مساحت و کسورات بازشو باید صریح باشند")
            gross = n * _length(entry, "length_m") * _length(entry, "width_m")
            deduction = positive(entry["openings_m2"], "مساحت بازشو", allow_zero=True)
            measured = _ratio(gross, deduction, "مساحت خالص")
            evidence = {"gross_m2": gross, "openings_m2": deduction}
        elif kind == "steel_profile_schedule":
            if set(entry) != {"id", "source_ref", "approved_by", "count",
                              "length_m", "unit_weight_kg_m", "unit_weight_source"}:
                raise ValueError("وزن مقطع فولادی نیازمند طول، تعداد و وزن واحد مستند است")
            unit_weight = _length(entry, "unit_weight_kg_m")
            require_text(entry["unit_weight_source"], "مرجع وزن واحد مقطع")
            measured = n * _length(entry, "length_m") * unit_weight
        elif kind == "steel_plate_schedule":
            if set(entry) != {"id", "source_ref", "approved_by", "count",
                              "length_m", "width_m", "thickness_m",
                              "density_kg_m3", "density_source"}:
                raise ValueError("پلیت فولادی نیازمند ابعاد، چگالی واقعی مستند و تعداد است")
            require_text(entry["density_source"], "مرجع چگالی فولاد")
            measured = (n * _length(entry, "length_m") * _length(entry, "width_m")
                        * _length(entry, "thickness_m") * _length(entry, "density_kg_m3"))
        elif kind == "timber_volume_schedule":
            if set(entry) != {"id", "source_ref", "approved_by", "count",
                              "length_m", "width_m", "depth_m"}:
                raise ValueError("مقطع چوب نیازمند ابعاد واقعی و تعداد است")
            measured = n * _length(entry, "length_m") * _length(entry, "width_m") * _length(entry, "depth_m")
        elif kind == "piece_schedule":
            if set(entry) != {"id", "source_ref", "approved_by", "count", "spec_ref"}:
                raise ValueError("قطعات باید شناسه و مشخصات فنی تأییدشده داشته باشند")
            require_text(entry["spec_ref"], "مرجع مشخصات قطعه")
            measured = n
        elif kind == "concrete_regions":
            if set(entry) != {"id", "source_ref", "approved_by",
                              "length_m", "width_m", "thickness_m", "voids"}:
                raise ValueError("ناحیه بتن سقف باید ابعاد و فهرست حفره معتبر داشته باشد")
            gross = (_length(entry, "length_m") * _length(entry, "width_m")
                     * _length(entry, "thickness_m"))
            voids = entry["voids"]
            if not isinstance(voids, list):
                raise ValueError("مجموع حفره‌های سقف باید به‌صورت فهرست باشد")
            checked_voids = []
            for void in voids:
                if not isinstance(void, dict) or set(void) != {"id", "volume_m3", "source_ref", "approved_by"}:
                    raise ValueError("حفره فاقد حجم یا مرجع مستند است")
                vid = require_text(void["id"], "شناسه حفره")
                if vid in consumed_voids:
                    raise ValueError("حفره سقف دوبار در چند ناحیه کسر شده است")
                consumed_voids.add(vid)
                checked_voids.append({
                    "id": vid, "volume_m3": positive(void["volume_m3"], "حجم واقعی حفره"),
                    "source_ref": require_text(void["source_ref"], "مرجع حفره"),
                    "approved_by": require_text(void["approved_by"], "تأییدکننده حفره"),
                })
            volume_voids = _exact_float_sum(v["volume_m3"] for v in checked_voids)
            measured = _ratio(gross, volume_voids, "حجم خالص بتن سقف")
            evidence = {"gross_m3": gross, "voids": checked_voids, "void_volume_m3": volume_voids}
        if measured is None or not math.isfinite(measured) or measured <= 0:
            raise ValueError("نتیجه جزئیات نامعتبر یا غیرمثبت است")
        totals.append(measured)
        normalized.append({"id": label, "source_ref": entry["source_ref"],
                           "approved_by": entry["approved_by"], "input": entry,
                           "quantity": measured, **evidence})
    total = _exact_float_sum(totals)
    positive(total, "جمع واقعی جزء")
    return {"quantity": total, "unit": _SCHEMAS[kind],
            "formula": {
                "rectangle_volume": "جمع طول × عرض × ضخامت × تعداد",
                "net_surface": "جمع سطوح خالص واقعی پس از کسورات بازشو",
                "steel_profile_schedule": "جمع طول واقعی × وزن واحد مستند × تعداد",
                "steel_plate_schedule": "جمع طول × عرض × ضخامت × چگالی تأییدشده × تعداد",
                "timber_volume_schedule": "جمع طول × عرض × ارتفاع مقطع × تعداد",
                "piece_schedule": "جمع تعداد قطعات با شناسه واقعی",
                "concrete_regions": "جمع حجم بتن ناحیه‌ها منهای حفره‌های مستند غیرتکراری",
            }[kind], "details": normalized, "method": kind}
