"""Typed records used by the engineering reference libraries."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class EngineeringMaterial:
    code: str
    name: str
    category: str
    default_unit: str
    density_kg_m3: float | None = None
    source_id: str = "builtin-reference"
    source_version: str = "1"
    notes: str = ""

@dataclass(frozen=True)
class ConcreteGrade:
    code: str
    name: str
    characteristic_strength_mpa: float
    material_code: str = "CONCRETE"
    source_id: str = "builtin-reference"
    source_version: str = "1"
    notes: str = ""

@dataclass(frozen=True)
class RebarGrade:
    code: str
    name: str
    yield_strength_mpa: float
    tensile_strength_mpa: float | None = None
    ductility_class: str = ""
    material_code: str = "REBAR"
    source_id: str = "builtin-reference"
    source_version: str = "1"
    notes: str = ""

@dataclass(frozen=True)
class StandardReference:
    code: str
    title: str
    jurisdiction: str
    scope: str
    version: str = ""
    source_version: str = "1"
    source_id: str = "builtin-reference"
    notes: str = ""
