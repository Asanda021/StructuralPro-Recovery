"""Executable standards selection and provenance engine for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from .registry import StandardsRegistry
from .models import RegulationRule

@dataclass(frozen=True)
class RuleDecision:
    rule_code: str
    source_code: str
    source_title: str
    edition: str
    clause: str
    topic: str
    domain: str
    requirement: str
    parameters: dict

class StandardsEngine:
    def __init__(self, registry: StandardsRegistry): self.registry=registry

    def resolve(self, *, domain: str, topic: str = "", rule_code: str | None = None) -> tuple[RuleDecision, ...]:
        rules = (self.registry.rule(rule_code),) if rule_code else self.registry.rules_for(domain=domain, topic=topic)
        out=[]
        for rule in rules:
            if rule is None or rule.status == "deprecated": continue
            source=self.registry.source(rule.source_code)
            if source is None: raise ValueError(f"rule has no source: {rule.code}")
            out.append(RuleDecision(rule.code,source.code,source.title,source.edition,rule.clause,rule.topic,domain,rule.requirement,dict(rule.parameters)))
        return tuple(out)

    def require(self, *, domain: str, topic: str = "", rule_code: str | None = None) -> RuleDecision:
        rows=self.resolve(domain=domain,topic=topic,rule_code=rule_code)
        if not rows: raise LookupError(f"no active standard rule for domain={domain!r}, topic={topic!r}")
        return rows[0]

    def provenance(self, decision: RuleDecision) -> dict: return asdict(decision)

    def validate(self):
        result=self.registry.validate()
        errors=list(result["errors"])
        for rule in self.registry.rules():
            if rule.status == "active":
                try: self.require(domain=rule.domains[0] if rule.domains else "", rule_code=rule.code)
                except (LookupError, ValueError) as exc: errors.append(str(exc))
        result["errors"]=errors; result["ok"]=not errors
        return result
