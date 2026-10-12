"""Canonical AEC discipline taxonomy used by takeoff, BOQ and project contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Discipline:
    key: str
    title_fa: str
    families: tuple[str, ...]


DISCIPLINES = (
    Discipline("architecture", "معماری", ("finishes", "doors_windows", "partitions", "ceilings")),
    Discipline("structural_concrete", "سازه بتنی", ("concrete", "rebar", "formwork")),
    Discipline("structural_steel", "سازه فولادی", ("steel", "connections", "deck")),
    Discipline("masonry", "بنا و دیوارچینی", ("block", "brick", "mortar", "stone")),
    Discipline("timber", "سازه چوبی", ("timber", "panels", "connections")),
    Discipline("composite", "سازه مرکب", ("composite", "deck", "steel_concrete")),
    Discipline("mechanical", "تأسیسات مکانیکی", ("hvac", "plumbing", "fire_protection")),
    Discipline("electrical", "تأسیسات برقی", ("power", "lighting", "low_voltage")),
    Discipline("renovation", "بهسازی و مرمت", ("demolition", "repair", "restoration")),
    Discipline("historic", "بناهای تاریخی", ("conservation", "historic_fabric", "restoration")),
    Discipline("site_external", "محوطه و عملیات بیرونی", ("earthwork", "landscape", "external_utilities")),
)


_TAKEOFF_DOMAINS = {
    "architecture": "building",
    "structural_concrete": "building",
    "structural_steel": "advanced",
    "masonry": "building",
    "timber": "advanced",
    "composite": "advanced",
    "mechanical": "mechanical",
    "electrical": "electrical",
    "renovation": "advanced",
    "historic": "advanced",
    "site_external": "civil",
}


def all_disciplines() -> tuple[Discipline, ...]:
    return DISCIPLINES


def get_discipline(key: str) -> Discipline:
    for item in DISCIPLINES:
        if item.key == key:
            return item
    raise KeyError(key)


def takeoff_domain(key: str) -> str:
    """Resolve a canonical AEC discipline to an existing takeoff engine domain."""
    normalized = str(key or "").strip().casefold()
    if not normalized:
        return "building"
    if normalized in {"building", "mechanical", "electrical", "civil", "advanced"}:
        return normalized
    try:
        return _TAKEOFF_DOMAINS[normalized]
    except KeyError as exc:
        raise KeyError(f"unsupported AEC discipline: {key}") from exc
