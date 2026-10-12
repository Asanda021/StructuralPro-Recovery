"""Production acceptance for roadmap P110-P114.

P110 revision intelligence
P111 quantity -> estimate bridge
P112 reusable assembly/cost build-up
P113 estimate workspace/finalization
P114 BOQ + quantity scenarios

The acceptance layer composes existing production modules; it does not invent
quantities or prices and fails closed on unresolved/duplicate evidence.
"""
from __future__ import annotations

from decimal import Decimal

from core.revision.intelligence_v2 import (
    RevisionElement, compare_revision_elements, summarize_revision,
)
from core.takeoff.assemblies import AssemblyLibrary
from core.takeoff.estimating import build_professional_estimate
from core.takeoff.estimate import compare_estimates
from core.engineering.production_quantity_scenarios_v1 import production_scenarios


def run_p110() -> dict:
    before = (
        RevisionElement(
            "P110", "R1", "B1", "structural", "beam", "Beam",
            "sheet:R1", Decimal("10"), "m3",
            dimensions=(("length", Decimal("5")),),
            rebar_weight_kg=Decimal("100"), boq_quantity=Decimal("10"),
        ),
    )
    after = (
        RevisionElement(
            "P110", "R2", "B1", "structural", "beam", "Beam",
            "sheet:R2", Decimal("12"), "m3",
            dimensions=(("length", Decimal("6")),),
            rebar_weight_kg=Decimal("110"), boq_quantity=Decimal("12"),
        ),
    )
    changes = compare_revision_elements(
        before, after, project_id="P110",
        before_revision="R1", after_revision="R2",
    )
    summary = summarize_revision(changes)
    return {
        "verified": len(changes) == 1 and changes[0].review_required,
        "quantity_delta": summary["quantity_delta"],
        "rebar_delta_kg": summary["rebar_delta_kg"],
        "boq_delta": summary["boq_delta"],
        "review_required": summary["review_required"],
    }


def run_p111() -> dict:
    rows = [{
        "source": "takeoff:B1", "source_type": "drawing",
        "price_code": "B-001", "description": "بتن",
        "quantity": 10, "unit": "m3", "unit_price": 100,
    }]
    result = build_professional_estimate(
        rows, factors={"overhead": 0.10}, strict_prices=False,
    )
    return {
        "verified": result["validation"]["valid"],
        "boq_lines": len(result["boq"]),
        "base": result["cost"]["base"],
        "grand_total": result["cost"]["grand_total"],
        "finalizable": result["finalizable"],
    }


def run_p112() -> dict:
    library = AssemblyLibrary()
    assembly = library.get("SLAB-CON")
    expanded = assembly.expand(10)
    return {
        "verified": len(expanded) == 3,
        "assembly_code": assembly.code,
        "components": [x["code"] for x in expanded],
        "quantities": [x["quantity"] for x in expanded],
    }


def run_p113() -> dict:
    old = {"boq": [{"price_code": "B-001", "quantity": 10, "unit_price": 100}],
           "cost": {"grand_total": 1000}}
    new = {"boq": [{"price_code": "B-001", "quantity": 12, "unit_price": 100}],
           "cost": {"grand_total": 1200}}
    delta = compare_estimates(old, new)
    return {
        "verified": delta["delta"] == 200 and len(delta["line_changes"]) == 1,
        "delta": delta["delta"],
        "delta_percent": delta["delta_percent"],
        "line_changes": delta["line_changes"],
    }


def run_p114() -> dict:
    scenarios = production_scenarios()
    valid = (
        len(scenarios) >= 5
        and all(x["concrete_m3"] >= 0 for x in scenarios)
        and all(x["rebar_kg"] >= 0 for x in scenarios)
        and all(x["stock_bar_count"] >= 0 for x in scenarios)
    )
    return {
        "verified": valid,
        "scenario_count": len(scenarios),
        "member_types": [x["member_type"] for x in scenarios],
        "total_concrete_m3": sum(x["concrete_m3"] for x in scenarios),
        "total_rebar_kg": sum(x["rebar_kg"] for x in scenarios),
    }


def run_all() -> dict:
    return {
        "P110": run_p110(),
        "P111": run_p111(),
        "P112": run_p112(),
        "P113": run_p113(),
        "P114": run_p114(),
    }
