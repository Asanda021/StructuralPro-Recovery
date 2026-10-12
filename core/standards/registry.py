"""Deterministic standards registry used by engineering and commercial modules."""
from __future__ import annotations
from dataclasses import asdict
from .models import RegulationSource, RegulationRule

class StandardsRegistry:
    def __init__(self, sources=(), rules=()):
        self._sources = {}
        self._rules = {}
        for source in sources: self.add_source(source)
        for rule in rules: self.add_rule(rule)

    def add_source(self, source: RegulationSource) -> None:
        if not isinstance(source, RegulationSource): raise TypeError("source must be RegulationSource")
        code = source.code.strip().upper()
        if not code or not source.title.strip() or not source.edition.strip():
            raise ValueError("source code, title and edition are required")
        self._sources[code] = source

    def add_rule(self, rule: RegulationRule) -> None:
        if not isinstance(rule, RegulationRule): raise TypeError("rule must be RegulationRule")
        rule.validate(self._sources)
        self._rules[rule.code] = rule

    def source(self, code): return self._sources.get(str(code).strip().upper())
    def rule(self, code): return self._rules.get(str(code).strip())
    def sources(self): return tuple(self._sources[k] for k in sorted(self._sources))
    def rules(self): return tuple(self._rules[k] for k in sorted(self._rules))

    def rules_for(self, *, domain=None, topic=None):
        domain = str(domain or "").strip().casefold()
        topic = str(topic or "").strip().casefold()
        return tuple(r for r in self.rules() if
            (not domain or domain in {d.casefold() for d in r.domains}) and
            (not topic or topic in r.topic.casefold()))

    def validate(self):
        errors=[]
        for r in self._rules.values():
            try: r.validate(self._sources)
            except ValueError as exc: errors.append(str(exc))
        return {"ok": not errors, "errors": errors, "source_count": len(self._sources), "rule_count": len(self._rules)}

    def snapshot(self):
        return {"sources":[asdict(x) for x in self.sources()], "rules":[asdict(x) for x in self.rules()]}

def default_iran_registry() -> StandardsRegistry:
    sources = [
        RegulationSource("IR-NBR-07", "مبحث هفتم مقررات ملی ساختمان — ژئوتکنیک و مهندسی پی", "دفتر مقررات ملی ساختمان", edition="1400"),
        RegulationSource("IR-NBR-08", "مبحث هشتم مقررات ملی ساختمان — ساختمان‌های با مصالح بنایی", "دفتر مقررات ملی ساختمان", edition="1398"),
        RegulationSource("IR-NBR-09", "مبحث نهم مقررات ملی ساختمان — طرح و اجرای ساختمان‌های بتن‌آرمه", "دفتر مقررات ملی ساختمان", edition="1399"),
        RegulationSource("IR-NBR-10", "مبحث دهم مقررات ملی ساختمان — طرح و اجرای ساختمان‌های فولادی", "دفتر مقررات ملی ساختمان", edition="1401"),
        RegulationSource("IR-2800", "استاندارد 2800 ایران — طراحی ساختمان‌ها در برابر زلزله", "مرکز تحقیقات راه، مسکن و شهرسازی", edition="ویرایش چهارم"),
        RegulationSource("IR-PRICE-1404", "فهرست بهای واحد پایه رشته ابنیه", "سازمان برنامه و بودجه کشور", edition="1404"),
    ]
    rules = [
        RegulationRule("N07-FOUNDATION-SOURCE", "IR-NBR-07", "foundation", "دامنه کاربرد", "مبنای ضوابط پی", "پارامترها و کنترل‌های پی باید با ویرایش فعال مبحث 7 و اطلاعات ژئوتکنیک پروژه مرتبط باشند.", ("foundations", "geotechnical")),
        RegulationRule("N08-MASONRY-SOURCE", "IR-NBR-08", "masonry", "دامنه کاربرد", "مبنای ضوابط بنایی", "مصالح و اجزای بنایی باید با مبحث 8 و ویرایش فعال پروژه تطبیق داده شوند.", ("masonry",)),
        RegulationRule("N09-CONCRETE-SOURCE", "IR-NBR-09", "concrete", "دامنه کاربرد", "مبنای ضوابط بتن‌آرمه", "اطلاعات بتن، آرماتور و جزئیات اجرایی بتن باید به منبع مبحث 9 متصل باشند.", ("concrete",)),
        RegulationRule("N10-STEEL-SOURCE", "IR-NBR-10", "steel", "دامنه کاربرد", "مبنای ضوابط فولادی", "مصالح و اجزای فولادی باید به منبع مبحث 10 و ویرایش فعال پروژه متصل باشند.", ("steel",)),
        RegulationRule("IR2800-SEISMIC-SOURCE", "IR-2800", "seismic", "مرجع پروژه", "مرجع لرزه‌ای", "هر داده لرزه‌ای مورد استفاده باید منبع و ویرایش مشخص داشته باشد.", ("concrete", "steel", "masonry", "foundations")),
        RegulationRule("PRICE-1404-SOURCE", "IR-PRICE-1404", "pricing", "کلیات", "مرجع فهرست بها", "اقلام برآورد باید منبع، سال و کد فهرست بها داشته باشند.", ("takeoff", "boq", "estimating")),
    ]
    from .catalog import IRAN_CORE_SOURCES
    known={s.code for s in sources}
    sources.extend(s for s in IRAN_CORE_SOURCES if s.code not in known)
    return StandardsRegistry(sources, rules)
