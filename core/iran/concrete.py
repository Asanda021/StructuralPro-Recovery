"""Iran-focused concrete building quantity takeoff.

Quantity-only layer: no structural design/checks and no hidden coefficients.
Supports common concrete members, explicit rebar schedules, 12 m stock-bar
count, and Iranian BOQ-friendly metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import ceil
from typing import Any, Iterable

ROOF_CONCRETE_COEFFICIENTS = {"تیرچه تک": 0.18, "تیرچه دوبل": 0.23}
MEMBER_CODES = {
    "پی منفرد": ("01", "m3"), "پی نواری": ("02", "m3"), "رادیه": ("03", "m3"),
    "ستون": ("04", "m3"), "تیر": ("05", "m3"), "دیوار": ("06", "m3"),
    "دال بتنی": ("07", "m3"), "تیرچه یونولیتی": ("08", "m3"),
    "تیرچه بلوک": ("09", "m3"), "تیرچه تک": ("10", "m3"),
    "تیرچه دوبل": ("11", "m3"), "وافل": ("12", "m3"), "یوبوت": ("13", "m3"),
}
STOCK_BAR_LENGTH_M = 12.0


@dataclass(frozen=True)
class RebarLine:
    diameter_mm: float
    length_m: float
    quantity: int = 1
    stock_length_m: float = STOCK_BAR_LENGTH_M
    waste_percent: float = 0.0
    splice_length_m: float = 0.0
    coupler_count: int = 0
    role: str = "main"

    def __post_init__(self):
        if self.diameter_mm <= 0 or self.length_m < 0 or self.quantity < 0:
            raise ValueError("مشخصات میلگرد نامعتبر است.")
        if self.stock_length_m <= 0 or self.waste_percent < 0 or self.splice_length_m < 0:
            raise ValueError("پارامترهای برش/پرت نامعتبر است.")
        if not self.role.strip():
            raise ValueError("نقش میلگرد الزامی است.")
        if self.coupler_count < 0:
            raise ValueError("تعداد کوپلر نامعتبر است.")

    @property
    def total_cut_length_m(self) -> float:
        return (self.length_m + self.splice_length_m) * self.quantity

    @property
    def gross_length_m(self) -> float:
        return self.total_cut_length_m * (1.0 + self.waste_percent / 100.0)

    @property
    def stock_bar_count(self) -> int:
        return ceil(self.gross_length_m / self.stock_length_m) if self.gross_length_m else 0

    @property
    def weight_kg(self) -> float:
        return self.gross_length_m * (self.diameter_mm ** 2) / 162.0

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "total_cut_length_m": self.total_cut_length_m,
            "gross_length_m": self.gross_length_m,
            "stock_bar_count": self.stock_bar_count,
            "weight_kg": self.weight_kg,
        }


def concrete_volume(member_type: str, *, length: float = 0, width: float = 0,
                    height: float = 0, area: float | None = None,
                    thickness: float | None = None,
                    roof_area: float | None = None) -> float:
    if member_type in ROOF_CONCRETE_COEFFICIENTS:
        if roof_area is None or roof_area < 0:
            raise ValueError("مساحت سقف برای سیستم تیرچه‌ای الزامی است.")
        return roof_area * ROOF_CONCRETE_COEFFICIENTS[member_type]
    if member_type not in MEMBER_CODES:
        raise ValueError(f"عضو بتنی پشتیبانی نمی‌شود: {member_type}")
    if area is not None and thickness is not None:
        if area < 0 or thickness < 0:
            raise ValueError("مساحت و ضخامت باید غیرمنفی باشند.")
        return area * thickness
    if min(length, width, height) < 0:
        raise ValueError("ابعاد باید غیرمنفی باشند.")
    return length * width * height


def rebar_summary(lines: Iterable[RebarLine | dict[str, Any]]) -> dict[str, Any]:
    normalized = []
    for line in lines:
        item = line if isinstance(line, RebarLine) else RebarLine(**line)
        normalized.append(item.to_dict())
    return {
        "lines": normalized,
        "total_weight_kg": sum(x["weight_kg"] for x in normalized),
        "total_cut_length_m": sum(x["total_cut_length_m"] for x in normalized),
        "total_gross_length_m": sum(x["gross_length_m"] for x in normalized),
        "total_stock_bar_count": sum(x["stock_bar_count"] for x in normalized),
        "total_coupler_count": sum(x["coupler_count"] for x in normalized),
    }


def concrete_member_takeoff(member_type: str, **geometry: float) -> dict[str, Any]:
    code, unit = MEMBER_CODES[member_type]
    volume = concrete_volume(member_type, **geometry)
    return {
        "item_code": f"IR-CON-{code}",
        "member_type": member_type,
        "description_fa": f"متره بتن {member_type}",
        "unit": unit,
        "quantity": volume,
        "source": "iran-concrete-takeoff",
        "quantity_only": True,
    }


def build_concrete_takeoff(member_type: str, *, geometry: dict[str, float],
                           rebar: Iterable[RebarLine | dict[str, Any]] = ()) -> dict[str, Any]:
    concrete = concrete_member_takeoff(member_type, **geometry)
    steel = rebar_summary(rebar)
    return {
        "member": concrete,
        "concrete": {"volume_m3": concrete["quantity"]},
        "rebar": steel,
        "boq_row": {
            "item_code": concrete["item_code"],
            "description": concrete["description_fa"],
            "unit": "m3",
            "quantity": concrete["quantity"],
            "category": "ساختمان بتنی ایران",
            "group": member_type,
        },
    }
