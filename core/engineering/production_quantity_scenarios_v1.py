"""Deterministic concrete-building quantity scenarios for production acceptance."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from core.engineering.deep_quantity import concrete_volume, rebar_weight, bar_cut_plan

@dataclass(frozen=True)
class RebarSpec:
    diameter_mm: float
    length_m: float
    count: int
    extra_length_m: float = 0.0

def member_scenario(member_type: str, *, length: float, width: float, depth: float,
                    rebar: tuple[RebarSpec, ...] = (), stock_length_m: float = 12.0) -> dict:
    if not str(member_type).strip():
        raise ValueError("member_type is required")
    concrete = concrete_volume(length, width, depth)
    rebar_lines = []
    cuts = []
    for item in rebar:
        weight = rebar_weight(item.length_m, item.diameter_mm, item.count, item.extra_length_m)
        rebar_lines.append({"diameter_mm": float(item.diameter_mm), "length_m": float(item.length_m),
                            "count": int(item.count), "weight_kg": weight})
        cuts.extend([item.length_m + item.extra_length_m] * int(item.count))
    cut = bar_cut_plan(cuts, stock_length_m=stock_length_m) if cuts else {
        "stock_length_m": float(stock_length_m), "stock_bar_count": 0,
        "used_length_m": 0.0, "waste_length_m": 0.0, "cut_lists": []
    }
    return {"member_type": str(member_type), "concrete_m3": concrete,
            "rebar_kg": sum(x["weight_kg"] for x in rebar_lines),
            "rebar": rebar_lines, "stock_bar_count": cut["stock_bar_count"],
            "waste_length_m": cut["waste_length_m"], "cut_list": cut["cut_lists"]}

def production_scenarios() -> tuple[dict, ...]:
    return (
        member_scenario("isolated_foundation", length=2.0, width=2.0, depth=0.45,
                        rebar=(RebarSpec(16, 1.9, 18), RebarSpec(10, 1.8, 12))),
        member_scenario("strip_foundation", length=10.0, width=0.7, depth=0.45,
                        rebar=(RebarSpec(14, 9.6, 20), RebarSpec(10, 0.65, 32))),
        member_scenario("raft", length=12.0, width=10.0, depth=0.35,
                        rebar=(RebarSpec(16, 11.4, 22), RebarSpec(12, 9.4, 20))),
        member_scenario("beam", length=6.0, width=0.35, depth=0.60,
                        rebar=(RebarSpec(20, 6.7, 4), RebarSpec(16, 6.5, 4), RebarSpec(10, 0.95, 36))),
        member_scenario("column", length=0.35, width=0.35, depth=3.2,
                        rebar=(RebarSpec(18, 3.7, 8), RebarSpec(10, 0.75, 28))),
        member_scenario("wall", length=8.0, width=0.20, depth=3.0,
                        rebar=(RebarSpec(12, 7.8, 22), RebarSpec(10, 2.9, 40))),
    )
