"""Rule-based drawing-to-takeoff pipeline."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class DrawingRule:
    name: str
    layer: str | None = None
    entity_type: str | None = None
    metric: str = "count"
    description: str = ""
    unit: str = "عدد"
    price_code: str | None = None
    scale: float = 1.0

class DrawingRuleEngine:
    def __init__(self, rules: list[DrawingRule] | None = None):
        self.rules = rules or []

    def apply(self, document, *, confirm_ambiguous=True):
        out = []
        for rule in self.rules:
            entities = [e for e in document.entities
                        if (rule.layer is None or e.layer == rule.layer)
                        and (rule.entity_type is None or e.entity_type == rule.entity_type)]
            if not entities:
                continue
            q = 0.0
            for e in entities:
                value = e.data.get(rule.metric, 1)
                try:
                    q += float(value) * rule.scale
                except (TypeError, ValueError):
                    continue
            out.append({
                "rule": rule.name,
                "description": rule.description or rule.name,
                "quantity": q,
                "unit": rule.unit,
                "price_code": rule.price_code,
                "source": "drawing",
                "entity_count": len(entities),
                "needs_confirmation": False,
            })
        return out

    @classmethod
    def from_layer_map(cls, layer_map: dict[str, dict[str, Any]]):
        rules = [
            DrawingRule(
                name=k, layer=k, metric=v.get("metric", "count"),
                description=v.get("description", k), unit=v.get("unit", "عدد"),
                price_code=v.get("price_code"), scale=float(v.get("scale", 1)),
            )
            for k, v in layer_map.items()
        ]
        return cls(rules)
