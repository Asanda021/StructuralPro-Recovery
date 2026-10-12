"""Deterministic golden-project acceptance benchmarks."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Any

@dataclass(frozen=True)
class GoldenCase:
    case_id: str
    description: str
    expected_keys: tuple[str, ...]

@dataclass(frozen=True)
class GoldenResult:
    case_id: str
    passed: bool
    missing_keys: tuple[str, ...] = ()
    error: str = ""

def default_cases() -> tuple[GoldenCase, ...]:
    return (
        GoldenCase("takeoff-basic", "basic takeoff quantity flow", ("takeoffs",)),
        GoldenCase("project-recovery", "project export/import round-trip", ("id", "name")),
        GoldenCase("estimate-report", "estimate/report data remains serializable", ("boq",)),
    )

def run_case(case: GoldenCase, factory: Callable[[GoldenCase], dict[str, Any]]) -> GoldenResult:
    try:
        payload = factory(case)
        missing = tuple(k for k in case.expected_keys if k not in payload)
        return GoldenResult(case.case_id, not missing, missing)
    except Exception as exc:
        return GoldenResult(case.case_id, False, (), f"{type(exc).__name__}: {exc}")

def acceptance_summary(results: list[GoldenResult]) -> dict[str, Any]:
    total=len(results); passed=sum(r.passed for r in results)
    return {"total":total,"passed":passed,"failed":total-passed,"ready":total>0 and passed==total,
            "failed_cases":[r.case_id for r in results if not r.passed]}
