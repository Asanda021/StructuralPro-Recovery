"""Project-wide auditable coefficient engine.

Coefficients are explicit rules, never hidden constants. The engine is domain
neutral and can be used for architecture, structural, steel, masonry, MEP,
civil and future disciplines.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Iterable, Mapping, Any
import math

@dataclass(frozen=True)
class CoefficientRule:
    key: str
    value: float
    mode: str = "rate"  # rate => 1 + value; multiplier => value
    scope: str = "project"
    discipline: str = ""
    wbs: str = ""
    item_code: str = ""
    source: str = ""
    effective_date: str = ""
    reason: str = ""
    enabled: bool = True

    def validate(self) -> "CoefficientRule":
        key = self.key.strip()
        if not key:
            raise ValueError("coefficient key is required")
        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("coefficient value must be finite")
        if self.mode not in {"rate", "multiplier"}:
            raise ValueError("coefficient mode must be rate or multiplier")
        if self.mode == "multiplier" and value < 0:
            raise ValueError("multiplier must be non-negative")
        if self.mode == "rate" and value <= -1:
            raise ValueError("rate must be greater than -1")
        return CoefficientRule(key=key, value=value, mode=self.mode,
            scope=self.scope.strip() or "project", discipline=self.discipline.strip(),
            wbs=self.wbs.strip(), item_code=self.item_code.strip(),
            source=self.source.strip(), effective_date=self.effective_date.strip(),
            reason=self.reason.strip(), enabled=bool(self.enabled))

    def multiplier(self) -> float:
        x = self.validate()
        return x.value if x.mode == "multiplier" else 1.0 + x.value

    def as_dict(self) -> dict[str, Any]:
        return asdict(self.validate())

class CoefficientEngine:
    def __init__(self, rules: Iterable[CoefficientRule] = ()):
        self._rules = [r.validate() for r in rules]

    def add(self, rule: CoefficientRule) -> None:
        self._rules.append(rule.validate())

    def rules(self) -> list[dict[str, Any]]:
        return [r.as_dict() for r in self._rules]

    def applicable(self, *, discipline: str = "", wbs: str = "",
                   item_code: str = "", scope: str = "project") -> list[CoefficientRule]:
        d, w, i, s = discipline.strip(), wbs.strip(), item_code.strip(), scope.strip() or "project"
        out = []
        for rule in self._rules:
            if not rule.enabled or rule.scope not in {"project", s}:
                continue
            if rule.discipline and rule.discipline != d:
                continue
            if rule.wbs and rule.wbs != w:
                continue
            if rule.item_code and rule.item_code != i:
                continue
            out.append(rule)
        return out

    def calculate(self, base: float, *, discipline: str = "", wbs: str = "",
                  item_code: str = "", scope: str = "project") -> dict[str, Any]:
        base = float(base)
        if not math.isfinite(base) or base < 0:
            raise ValueError("base must be finite and non-negative")
        applied = self.applicable(discipline=discipline, wbs=wbs,
                                  item_code=item_code, scope=scope)
        current = base
        audit = []
        for rule in applied:
            multiplier = rule.multiplier()
            before = current
            current = before * multiplier
            if not math.isfinite(current):
                raise ValueError("coefficient result overflow")
            audit.append({
                "key": rule.key, "value": rule.value, "mode": rule.mode,
                "multiplier": multiplier, "before": before, "after": current,
                "source": rule.source, "reason": rule.reason,
                "effective_date": rule.effective_date,
            })
        return {"base": base, "result": current, "delta": current - base,
                "applied": audit}

    def explain(self, **context: str) -> list[dict[str, Any]]:
        return [r.as_dict() for r in self.applicable(**context)]
