"""Entry-point contract against implicit quantities in legacy takeoff formulas.

The legacy calculators remain available for compatibility, but reviewed
application mutations may not exploit count=1, layers=1 or waste=1 defaults.
"""
from __future__ import annotations

import math
from typing import Any

_REQUIRED_COUNT = {
    "building": frozenset({
        "wall", "wall_area", "دیوار", "solid_slab_roof", "solid_slab", "flat_slab",
        "joist_block_roof", "joist_foam_roof", "hollow_core_roof",
        "waffle_roof", "وافل", "uboot_roof", "cobiax_roof",
        "slab_volume", "concrete_slab", "بتن_سقف", "tie_beam", "tie_beam_concrete",
        "شناژ", "shear_wall", "shear_wall_concrete", "دیوار_برشی",
        "stair_concrete", "stair", "پله_بتنی", "roof_area", "roof", "سقف",
        "column", "column_concrete", "بتن_ستون", "beam", "beam_concrete",
        "بتن_تیر", "formwork", "formwork_area", "قالب",
        "plaster", "plaster_area", "گچ", "گچ_کاری", "paint", "paint_area",
        "رنگ", "door", "window", "opening", "درب", "پنجره",
        "rebar", "reinforcement", "آرماتور",
    }),
    "advanced": frozenset({
        "excavation", "خاکبرداری", "demolition", "demolition_volume",
        "تخریب", "footing_concrete", "foundation_concrete", "بتن_فونداسیون",
        "footing_formwork", "قالب_فونداسیون", "steel_roof_deck_area",
        "steel_roof_deck_weight", "steel_roof_composite_deck", "kromit_roof",
        "steel_truss_roof", "steel_sandwich_roof", "steel", "steel_roof",
        "steel_weight", "اسکلت_فلزی", "screed", "کف_سازی",
        "ceiling", "false_ceiling", "سقف_کاذب",
    }),
    "mechanical": frozenset({
        "pipe", "pipe_length", "لوله", "duct", "duct_length", "کانال",
        "equipment", "equipment_count", "تجهیز", "valve", "fixture", "شیر", "اتصال",
    }),
    "electrical": frozenset({
        "cable", "wire", "کابل", "سیم", "conduit", "لوله_برق",
        "panel", "board", "تابلو", "light", "lighting", "روشنایی",
        "چراغ", "socket", "outlet", "پریز",
    }),
    "civil": frozenset({"curb", "جدول"}),
}


def require_explicit_measurement_params(domain: str, item: str, params: dict[str, Any]) -> None:
    if not isinstance(params, dict):
        raise ValueError("ورودی‌های متره باید ساختار معتبر داشته باشند")
    d=str(domain).strip().casefold()
    i=str(item).strip().casefold().replace(" ", "_")
    requirements=[]
    if i in _REQUIRED_COUNT.get(d, ()):
        requirements.append("count")
    if d == "building" and i in {"tile", "ceramic", "tile_area", "کاشی", "سرامیک"}:
        requirements.append("waste")
    if d == "building" and i in {"roof_insulation", "waterproofing", "عایق"}:
        requirements.append("layers")
    missing=[key for key in requirements if params.get(key) is None]
    if missing:
        raise ValueError("ورودی صریح لازم است؛ مقدار پیش‌فرض مجاز نیست: "+", ".join(missing))
    for key in requirements:
        value=params[key]
        if isinstance(value, bool):
            raise ValueError(f"{key}: عدد معتبر لازم است")
        try:
            number=float(value)
        except (ValueError, TypeError, OverflowError) as exc:
            raise ValueError(f"{key}: عدد معتبر لازم است") from exc
        # Zero waste is valid only when the user has explicitly entered it.
        # A missing waste field is still forbidden; it must never be guessed.
        if not math.isfinite(number) or number < 0 or (number == 0 and key != "waste"):
            raise ValueError(f"{key}: مقدار باید متناهی و برای تعداد/لایه مثبت باشد")
        if key in {"count", "layers"} and not number.is_integer():
            raise ValueError(f"{key}: تعداد صحیح لازم است")
