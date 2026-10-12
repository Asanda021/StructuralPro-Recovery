"""P90/P91/P92 — evidence-first takeoff → price → benchmark gate."""
from __future__ import annotations
from dataclasses import dataclass
from core.estimate.pricebook_integration_v1 import map_and_price
from core.validation.iranian_project_benchmark_v2 import BenchmarkRow, compare

@dataclass(frozen=True)
class E2EResult:
    priced_rows: int
    total_amount: float
    year: int
    discipline: str

def run_e2e(takeoff_rows, normalized_rows, year, discipline):
    result=map_and_price(takeoff_rows,normalized_rows,year,discipline)
    total=sum(float(x["total"]) for x in result.accepted)
    return E2EResult(len(result.accepted),total,year,discipline)

def benchmark_gate(reference_rows, system_rows):
    if len(reference_rows)!=len(system_rows) or not reference_rows:
        raise ValueError("benchmark/reference row counts must match and be non-empty")
    rows=[BenchmarkRow(str(i),float(a),float(b)) for i,(a,b) in enumerate(zip(reference_rows,system_rows))]
    report=compare(rows)
    if not report["green2"]:
        raise ValueError("real-project benchmark gate failed")
    return report
