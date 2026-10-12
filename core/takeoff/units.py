"""Canonical construction units and deterministic unit conversion."""
from __future__ import annotations
import math

_ALIASES = {
    "m": "m", "meter": "m", "metre": "m", "متر": "m",
    "cm": "cm", "سانت": "cm", "سانتیمتر": "cm",
    "mm": "mm", "میلیمتر": "mm",
    "m2": "m2", "m²": "m2", "مترمربع": "m2", "متر مربع": "m2",
    "cm2": "cm2", "cm²": "cm2", "سانتیمترمربع": "cm2",
    "mm2": "mm2", "mm²": "mm2",
    "m3": "m3", "m³": "m3", "مترمکعب": "m3", "متر مکعب": "m3",
    "cm3": "cm3", "cm³": "cm3",
    "mm3": "mm3", "mm³": "mm3",
    "kg": "kg", "کیلوگرم": "kg",
    "ton": "ton", "t": "ton", "تن": "ton",
    "count": "عدد", "عدد": "عدد", "pcs": "عدد",
}

_DIMENSION = {
    "m": "length", "cm": "length", "mm": "length",
    "m2": "area", "cm2": "area", "mm2": "area",
    "m3": "volume", "cm3": "volume", "mm3": "volume",
    "kg": "mass", "ton": "mass", "عدد": "count",
}

_TO_BASE = {
    "m": 1.0, "cm": 0.01, "mm": 0.001,
    "m2": 1.0, "cm2": 0.0001, "mm2": 0.000001,
    "m3": 1.0, "cm3": 0.000001, "mm3": 0.000000001,
    "kg": 1.0, "ton": 1000.0, "عدد": 1.0,
}

def normalize_unit(unit: str) -> str:
    key = " ".join(str(unit or "").strip().casefold().split())
    if key not in _ALIASES:
        raise ValueError(f"واحد نامعتبر: {unit}")
    return _ALIASES[key]

def dimension(unit: str) -> str:
    return _DIMENSION[normalize_unit(unit)]

def are_compatible(first: str, second: str) -> bool:
    return dimension(first) == dimension(second)

def convert(value: float, from_unit: str, to_unit: str) -> float:
    source, target = normalize_unit(from_unit), normalize_unit(to_unit)
    if _DIMENSION[source] != _DIMENSION[target]:
        raise ValueError(f"تبدیل واحد ناسازگار: {from_unit} به {to_unit}")
    if isinstance(value, bool):
        raise ValueError("مقدار تبدیل واحد باید عددی باشد")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("مقدار تبدیل واحد باید عددی باشد") from exc
    if not math.isfinite(value):
        raise ValueError("مقدار باید عدد متناهی باشد")
    # Compute the finite scale ratio first to avoid a spurious overflow
    # when both the source and destination base units are large.
    result = value * (_TO_BASE[source] / _TO_BASE[target])
    if not math.isfinite(result) or (value != 0 and result == 0):
        raise ValueError("تبدیل واحد باعث سرریز یا صفر شدن ناخواسته مقدار شده است")
    return result

def canonical_quantity(value: float, unit: str, target_unit: str | None = None) -> tuple[float, str]:
    source = normalize_unit(unit)
    target = normalize_unit(target_unit) if target_unit else source
    return convert(value, source, target), target
