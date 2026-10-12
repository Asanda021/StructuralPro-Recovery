"""Offline-first deterministic engineering reference library."""
from __future__ import annotations
import math
from dataclasses import asdict
from typing import Iterable
from .models import ConcreteGrade, EngineeringMaterial, RebarGrade, StandardReference

class EngineeringLibrary:
    """Versioned reference data; it is not a structural design engine."""

    def __init__(self, materials=None, concretes=None, rebars=None, standards=None):
        self._materials = {}
        self._concretes = {}
        self._rebars = {}
        self._standards = {}
        for item in materials if materials is not None else self.default_materials():
            self.add_material(item)
        for item in concretes if concretes is not None else self.default_concretes():
            self.add_concrete(item)
        for item in rebars if rebars is not None else self.default_rebars():
            self.add_rebar(item)
        for item in standards if standards is not None else self.default_standards():
            self.add_standard(item)

    @staticmethod
    def _code(value):
        code = str(value or "").strip().upper()
        if not code:
            raise ValueError("engineering library code is required")
        return code

    @staticmethod
    def _finite_nonnegative(value, field):
        number = float(value)
        if not math.isfinite(number) or number < 0:
            raise ValueError(f"{field} must be finite and non-negative")
        return number

    def add_material(self, item: EngineeringMaterial):
        if not isinstance(item, EngineeringMaterial):
            raise TypeError("item must be EngineeringMaterial")
        code = self._code(item.code)
        unit = str(item.default_unit).strip()
        if not unit:
            raise ValueError("material default unit is required")
        density = None if item.density_kg_m3 is None else self._finite_nonnegative(item.density_kg_m3, "material density")
        self._materials[code] = EngineeringMaterial(code, str(item.name).strip(), str(item.category).strip(), unit, density, str(item.source_id).strip() or "unknown", str(item.source_version).strip() or "1", str(item.notes or "").strip())

    def add_concrete(self, item: ConcreteGrade):
        if not isinstance(item, ConcreteGrade):
            raise TypeError("item must be ConcreteGrade")
        code = self._code(item.code)
        strength = self._finite_nonnegative(item.characteristic_strength_mpa, "concrete strength")
        if strength <= 0:
            raise ValueError("concrete strength must be greater than zero")
        self._concretes[code] = ConcreteGrade(code, str(item.name).strip(), strength, self._code(item.material_code), str(item.source_id).strip() or "unknown", str(item.source_version).strip() or "1", str(item.notes or "").strip())

    def add_rebar(self, item: RebarGrade):
        if not isinstance(item, RebarGrade):
            raise TypeError("item must be RebarGrade")
        code = self._code(item.code)
        fy = self._finite_nonnegative(item.yield_strength_mpa, "rebar yield strength")
        if fy <= 0:
            raise ValueError("rebar yield strength must be greater than zero")
        fu = None if item.tensile_strength_mpa is None else self._finite_nonnegative(item.tensile_strength_mpa, "rebar tensile strength")
        if fu is not None and fu < fy:
            raise ValueError("rebar tensile strength cannot be lower than yield strength")
        self._rebars[code] = RebarGrade(code, str(item.name).strip(), fy, fu, str(item.ductility_class or "").strip(), self._code(item.material_code), str(item.source_id).strip() or "unknown", str(item.source_version).strip() or "1", str(item.notes or "").strip())

    def add_standard(self, item: StandardReference):
        if not isinstance(item, StandardReference):
            raise TypeError("item must be StandardReference")
        code = self._code(item.code)
        if not str(item.title).strip():
            raise ValueError("standard title is required")
        self._standards[code] = StandardReference(code, str(item.title).strip(), str(item.jurisdiction).strip(), str(item.scope).strip(), str(item.version or "").strip(), str(item.source_version).strip() or "1", str(item.source_id).strip() or "unknown", str(item.notes or "").strip())

    def material(self, code): return self._materials.get(self._code(code))
    def concrete(self, code): return self._concretes.get(self._code(code))
    def rebar(self, code): return self._rebars.get(self._code(code))
    def standard(self, code): return self._standards.get(self._code(code))

    def materials(self): return [self._materials[k] for k in sorted(self._materials)]
    def concretes(self): return [self._concretes[k] for k in sorted(self._concretes)]
    def rebars(self): return [self._rebars[k] for k in sorted(self._rebars)]
    def standards(self): return [self._standards[k] for k in sorted(self._standards)]

    def search(self, query="", *, category=None):
        q = str(query or "").strip().casefold()
        cat = str(category or "").strip().casefold()
        rows = []
        for item in self.materials():
            hay = " ".join((item.code, item.name, item.category, item.notes)).casefold()
            if (not q or q in hay) and (not cat or cat == item.category.casefold()):
                rows.append(dict(kind="material", **asdict(item)))
        for item in self.concretes():
            hay = " ".join((item.code, item.name, item.notes)).casefold()
            if (not q or q in hay) and (not cat or cat == "concrete"):
                rows.append(dict(kind="concrete", **asdict(item)))
        for item in self.rebars():
            hay = " ".join((item.code, item.name, item.ductility_class, item.notes)).casefold()
            if (not q or q in hay) and (not cat or cat == "rebar"):
                rows.append(dict(kind="rebar", **asdict(item)))
        for item in self.standards():
            hay = " ".join((item.code, item.title, item.jurisdiction, item.scope, item.notes)).casefold()
            if (not q or q in hay) and (not cat or cat == "standard"):
                rows.append(dict(kind="standard", **asdict(item)))
        return rows

    def snapshot(self):
        return {"materials":[asdict(x) for x in self.materials()], "concretes":[asdict(x) for x in self.concretes()], "rebars":[asdict(x) for x in self.rebars()], "standards":[asdict(x) for x in self.standards()]}

    def validate(self):
        errors = []
        for name, collection in (("materials", self.materials()), ("concretes", self.concretes()), ("rebars", self.rebars()), ("standards", self.standards())):
            seen = set()
            for item in collection:
                code = self._code(item.code)
                if code in seen:
                    errors.append(f"duplicate {name} code: {code}")
                seen.add(code)
                if not item.source_id:
                    errors.append(f"missing source_id: {code}")
                if not item.source_version:
                    errors.append(f"missing source_version: {code}")
        return {"ok": not errors, "errors": errors, "counts":{"materials":len(self._materials),"concretes":len(self._concretes),"rebars":len(self._rebars),"standards":len(self._standards)}}

    @staticmethod
    def default_materials():
        return (EngineeringMaterial("CONCRETE","بتن","concrete","m3",2400.0), EngineeringMaterial("REBAR","میلگرد فولادی","rebar","kg",7850.0), EngineeringMaterial("CEMENT","سیمان","cement","kg",1440.0), EngineeringMaterial("AGGREGATE","سنگدانه","aggregate","m3",1600.0), EngineeringMaterial("EPS","یونولیت","roof_filler","m3",20.0))

    @staticmethod
    def default_concretes():
        return tuple(ConcreteGrade(f"C{x}", f"بتن رده C{x}", float(x)) for x in (20,25,30,35,40))

    @staticmethod
    def default_rebars():
        return (RebarGrade("A1","میلگرد A1",240.0,360.0,"ساده"), RebarGrade("A2","میلگرد A2",300.0,500.0,"آجدار"), RebarGrade("A3","میلگرد A3",400.0,600.0,"آجدار"), RebarGrade("A4","میلگرد A4",500.0,650.0,"آجدار"))

    @staticmethod
    def default_standards():
        return (StandardReference("IR-M9","مبحث نهم مقررات ملی ساختمان","ایران","سازه‌های بتن‌آرمه",notes="مرجع نام‌گذاری؛ مشخصات نهایی پروژه باید با ویرایش قراردادی کنترل شود."), StandardReference("IR-M10","مبحث دهم مقررات ملی ساختمان","ایران","سازه‌های فولادی",notes="مرجع نام‌گذاری؛ مشخصات نهایی پروژه باید با ویرایش قراردادی کنترل شود."), StandardReference("ACI-318","ACI 318","بین‌المللی","Concrete Building Code",notes="مرجع نام‌گذاری؛ ویرایش پروژه باید صریحاً تعیین شود."), StandardReference("EC2","Eurocode 2","اروپا","Design of concrete structures",notes="مرجع نام‌گذاری؛ ویرایش پروژه باید صریحاً تعیین شود."))
