"""Iran concrete BOQ adapters.

This module classifies quantity rows for common Iranian concrete-building
work without embedding current market prices.
"""
from __future__ import annotations

from typing import Any, Iterable

from core.iran.concrete import MEMBER_CODES, build_concrete_takeoff

REBAR_ITEM_CODES = {
    "main": "IR-REB-MAIN",
    "stirrup": "IR-REB-STIRRUP",
    "sanjaghi": "IR-REB-SANJAGHI",
    "negative": "IR-REB-NEGATIVE",
    "mesh": "IR-REB-MESH",
    "tie": "IR-REB-TIE",
}


def member_catalog() -> list[dict[str, Any]]:
    return [
        {
            "item_code": f"IR-CON-{code}",
            "member_type": member,
            "description": f"متره بتن {member}",
            "unit": unit,
            "category": "ساختمان بتنی ایران",
        }
        for member, (code, unit) in MEMBER_CODES.items()
    ]


def rebar_boq_rows(summary: dict[str, Any], member_type: str) -> list[dict[str, Any]]:
    rows = []
    for line in summary.get("lines", []):
        role = str(line.get("role") or "main")
        code = REBAR_ITEM_CODES.get(role, "IR-REB-OTHER")
        rows.append({
            "item_code": code,
            "description": f"متره میلگرد {role} - {member_type}",
            "unit": "kg",
            "quantity": line["weight_kg"],
            "group": member_type,
            "category": "میلگرد ساختمان بتنی ایران",
            "stock_bar_count_12m": line["stock_bar_count"],
            "cut_length_m": line["total_cut_length_m"],
            "gross_length_m": line["gross_length_m"],
            "coupler_count": line["coupler_count"],
            "splice_length_m": line["splice_length_m"],
        })
    return rows


def concrete_to_boq(member_type: str, geometry: dict[str, float],
                    rebar: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    result = build_concrete_takeoff(member_type, geometry=geometry, rebar=rebar)
    rows = [result["boq_row"]]
    rows.extend(rebar_boq_rows(result["rebar"], member_type))
    return rows
