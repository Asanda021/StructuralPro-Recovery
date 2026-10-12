"""Canonical multi-discipline taxonomy for the whole-building platform."""
from __future__ import annotations
from typing import Final

DISCIPLINES: Final[tuple[str, ...]] = (
    "architecture", "structural", "concrete", "steel", "masonry",
    "mechanical", "electrical", "civil", "other",
)
TAKEOFF_TYPES: Final[tuple[str, ...]] = (
    "length", "area", "volume", "count", "perimeter", "weight",
    "depth", "radius", "angle", "arc",
)

ALIASES = {
    "architectural": "architecture", "معماری": "architecture",
    "سازه": "structural", "سازه‌ای": "structural",
    "بتن": "concrete", "بتن_آرمه": "concrete",
    "فولاد": "steel", "steelwork": "steel",
    "بنایی": "masonry", "masonrywork": "masonry",
    "مکانیک": "mechanical", "مکانیکی": "mechanical", "mep_mechanical": "mechanical",
    "برق": "electrical", "برقی": "electrical", "mep_electrical": "electrical",
    "عمران": "civil",
}

def normalize_discipline(value: str) -> str:
    key = str(value or "").strip().casefold()
    key = ALIASES.get(key, key)
    if key not in DISCIPLINES:
        raise ValueError(f"unsupported discipline: {value}")
    return key

def is_supported_takeoff_type(value: str) -> bool:
    return str(value or "").strip().casefold() in TAKEOFF_TYPES
