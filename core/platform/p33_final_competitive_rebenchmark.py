"""P33 — Final competitive re-benchmark gate."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re

@dataclass(frozen=True)
class P33Result:
    valid: bool
    benchmark_rows: int
    mapped_rows: int
    gaps: tuple[str,...]

REQUIRED_IDS=tuple(f"B{i:02d}" for i in range(1,46))
MATRIX=Path("docs/PHASE15_COMPETITIVE_BENCHMARK.md")
EVIDENCE={
15:("docs/PHASE15_COMPETITIVE_BENCHMARK.md","tests/test_phase15_competitive_benchmark.py"),
16:("docs/PHASE16_IRANIAN_TAKEOFF_PARITY.md","tests/test_phase16_iranian_takeoff_parity.py"),
17:("docs/PHASE17_COMMERCIAL_STATEMENT_CONTROL.md","tests/test_phase17_commercial.py"),
18:("docs/PHASE18_PDF_TAKEOFF.md","tests/test_phase18_pdf_takeoff.py"),
19:("docs/PHASE19_DRAWING_INTELLIGENCE.md","tests/test_phase19_drawing_intelligence.py"),
20:("docs/PHASE20_REVISION_MANAGEMENT.md","tests/test_phase20_revision_management.py"),
21:("docs/PHASE21_DWG_DXF.md","tests/test_phase21_dwg_dxf.py"),
22:("docs/PHASE22_IFC_BIM.md","tests/test_phase22_ifc_bim.py"),
23:("tests/test_p23_ai_takeoff.py","tests/test_p24_ai_takeoff_intelligence.py"),
25:("tests/test_p25_ai_takeoff_production.py","tests/test_p26_ai_takeoff_review.py"),
27:("tests/test_p27_ai_takeoff_review_audit.py","tests/test_p28_product_ux_master_audit.py"),
29:("tests/test_p29_real_world_validation.py","tests/test_p30_production_hardening.py"),
31:("tests/test_p31_commercial_readiness.py","tests/test_p32_full_regression.py"),
}

def run_p33_gate() -> P33Result:
    errors=[]
    if not MATRIX.is_file(): errors.append("benchmark matrix missing"); return P33Result(False,0,0,tuple(errors))
    text=MATRIX.read_text(encoding="utf-8")
    rows=[x for x in text.splitlines() if re.match(r"^\| B\d{2} \|",x)]
    ids=[re.match(r"^\| (B\d{2}) \|",x).group(1) for x in rows]
    if tuple(ids)!=REQUIRED_IDS: errors.append("benchmark IDs are incomplete or reordered")
    mapped=sum("| P" in x for x in rows)
    if len(rows)!=45 or mapped!=45: errors.append("benchmark rows are not fully mapped")
    for phase,paths in EVIDENCE.items():
        for p in paths:
            if not Path(p).is_file(): errors.append(f"P{phase} evidence missing:{p}")
    # P34/P35 are intentionally not claimed complete by P33.
    if "B44" in ids and "Phase 33" not in text: errors.append("final re-benchmark mapping missing")
    return P33Result(not errors,len(rows),mapped,tuple(sorted(errors)))
