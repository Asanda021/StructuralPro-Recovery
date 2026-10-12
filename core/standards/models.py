"""Versioned, auditable standards records. Rules contain no anonymous coefficients."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Mapping

@dataclass(frozen=True)
class RegulationSource:
    code: str
    title: str
    publisher: str
    jurisdiction: str = "ایران"
    edition: str = ""
    effective_from: str = ""
    source_url: str = ""
    notes: str = ""

@dataclass(frozen=True)
class RegulationRule:
    code: str
    source_code: str
    topic: str
    clause: str
    title: str
    requirement: str
    domains: tuple[str, ...] = ()
    parameters: Mapping[str, float | str] = field(default_factory=dict)
    status: str = "reference"

    def validate(self, sources: Mapping[str, RegulationSource]) -> None:
        if self.source_code not in sources:
            raise ValueError(f"unknown regulation source: {self.source_code}")
        if not self.code.strip() or not self.topic.strip() or not self.clause.strip():
            raise ValueError("rule code, topic and clause are required")
        if not self.requirement.strip():
            raise ValueError("rule requirement is required")
        if self.status not in {"reference", "active", "deprecated"}:
            raise ValueError(f"invalid rule status: {self.status}")
