"""Fail-closed, dimensionally explicit rectangular *linear* sloping-fill takeoff.

Pure geometry only: no BOQ, cost, material recipe, inferred slopes, or version migration.
The returned quantities are exact decimal strings for a future reviewed-AEC adapter.
"""
from __future__ import annotations

from decimal import Decimal

from core.commercial.exact_values import exact, number

POLICY = "linear_rectangular_slope_geometry_v1"
_FIELDS = frozenset({
    "policy", "region_id", "source_ref", "approved_by", "material_ref",
    "length_m", "width_m", "direction", "start_thickness_m",
    "end_thickness_m", "openings",
})
_OPENING_FIELDS = frozenset({
    "id", "source_ref", "x_m", "y_m", "length_m", "width_m",
    "penetration",
})


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{label}: مرجع مستند الزامی است")
    return value.strip()


def _value(value, label, *, positive=False):
    amount = number(value, label)
    if positive and amount <= 0:
        raise ValueError(f"{label}: مقدار باید مثبت باشد")
    return amount


def _wire(value: Decimal) -> str:
    """Always preserve the exact decimal, rather than a binary float."""
    return format(value, "f")


def _overlap(first, second):
    """True only for interiors intersecting, not for shared boundaries."""
    return (max(first[0], second[0]) < min(first[2], second[2])
            and max(first[1], second[1]) < min(first[3], second[3]))


@exact
def calculate_linear_slope(data: dict) -> dict:
    """Take off fill between a horizontal datum and one documented planar top.

    Coordinates are measured from the lower-left region corner.  The thickness
    varies linearly along a documented axis and is constant along the other.
    Only full-depth, axis-aligned rectangular voids are supported.  A void's
    removed volume is integrated analytically, not using a global mean depth.
    """
    if not isinstance(data, dict) or set(data) != _FIELDS:
        raise ValueError("قرارداد شیب‌بندی: فیلدهای نسخه‌دار باید دقیق باشند")
    if data["policy"] != POLICY:
        raise ValueError("نسخه قرارداد شیب‌بندی ناشناخته است")
    for key in ("region_id", "source_ref", "approved_by", "material_ref"):
        _text(data[key], key)
    L = _value(data["length_m"], "طول ناحیه", positive=True)
    W = _value(data["width_m"], "عرض ناحیه", positive=True)
    start = _value(data["start_thickness_m"], "ضخامت ابتدا")
    end = _value(data["end_thickness_m"], "ضخامت انتها")
    if start == 0 and end == 0:
        raise ValueError("ضخامت شیب‌بندی در سراسر ناحیه صفر است")
    direction = data["direction"]
    if direction not in ("x", "y"):
        raise ValueError("جهت شیب فقط x یا y و باید مستند باشد")
    openings = data["openings"]
    if not isinstance(openings, list) or len(openings) > 128:
        raise ValueError("بازشوها باید فهرست مستند و محدود باشند")
    boxes = []
    seen_ids, seen_sources = set(), set()
    deductions = []
    deducted_area = Decimal(0)
    deducted_volume = Decimal(0)
    span = L if direction == "x" else W
    delta = end - start
    for opening in openings:
        if not isinstance(opening, dict) or set(opening) != _OPENING_FIELDS:
            raise ValueError("ساختار بازشوی شیب‌بندی ناقص یا ناشناخته است")
        ident = _text(opening["id"], "شناسه بازشو")
        source = _text(opening["source_ref"], "مرجع بازشو")
        if ident in seen_ids or source in seen_sources or source == data["source_ref"]:
            raise ValueError("هویت یا منبع بازشو تکراری است")
        seen_ids.add(ident)
        seen_sources.add(source)
        if opening["penetration"] != "full_depth":
            raise ValueError("بازشوهای بخشی از ضخامت فعلاً پشتیبانی نمی‌شوند")
        x = _value(opening["x_m"], "مختصات افقی بازشو")
        y = _value(opening["y_m"], "مختصات عمودی بازشو")
        length = _value(opening["length_m"], "طول بازشو", positive=True)
        width = _value(opening["width_m"], "عرض بازشو", positive=True)
        if x + length > L or y + width > W:
            raise ValueError("بازشو از هندسه ناحیه خارج شده است")
        box = (x, y, x + length, y + width)
        if any(_overlap(box, existing) for existing in boxes):
            raise ValueError("بازشوها هم‌پوشانی مثبت دارند؛ کسر دوباره ممنوع است")
        boxes.append(box)
        opening_area = length * width
        # This is the exact integral of a linear function over the void's
        # rectangle.  Using only whole-region mean depth is incorrect.
        axis_center = x + length / 2 if direction == "x" else y + width / 2
        mean_depth_at_void = start + delta * axis_center / span
        volume = opening_area * mean_depth_at_void
        deducted_area += opening_area
        deducted_volume += volume
        deductions.append({
            "id": ident,
            "source_ref": source,
            "plan_area_m2": _wire(opening_area),
            "deducted_volume_m3": _wire(volume),
        })

    gross_area = L * W
    gross_volume = gross_area * (start + end) / 2
    net_area = gross_area - deducted_area
    net_volume = gross_volume - deducted_volume
    if net_area <= 0 or net_volume <= 0:
        raise ValueError("تمام ناحیه حذف شده یا حجم قابل محاسبه ندارد")
    return {
        "policy": POLICY,
        "region_id": data["region_id"],
        "source_ref": data["source_ref"],
        "material_ref": data["material_ref"],
        "approved_by": data["approved_by"],
        "measurement_unit": "m3",
        "direction": direction,
        "gross_area_m2": _wire(gross_area),
        "net_area_m2": _wire(net_area),
        "gross_volume_m3": _wire(gross_volume),
        "deducted_volume_m3": _wire(deducted_volume),
        "net_volume_m3": _wire(net_volume),
        "deductions": deductions,
        "payment_role": "unreviewed_geometry_only",
        "boq_ready": False,
        "purchase_quantity": None,
        "acceptance": "synthetic_geometry_only",
    }
