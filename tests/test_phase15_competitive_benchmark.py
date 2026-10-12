from pathlib import Path

MATRIX = Path("docs/PHASE15_COMPETITIVE_BENCHMARK.md")
REQUIRED_IDS = {f"B{i:02d}" for i in range(1, 46)}

def test_phase15_matrix_is_complete_and_mapped():
    text = MATRIX.read_text(encoding="utf-8")
    for case_id in REQUIRED_IDS:
        assert f"| {case_id} |" in text
    assert "## Baseline decision" in text
    assert "Phase 33" in text
    assert "Phase 35" in text

def test_phase15_has_no_orphaned_benchmark_rows():
    text = MATRIX.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| B") ]
    assert len(rows) == 45
    assert all("| roadmap |" in row or "| implemented |" in row or "| contract |" in row or "| benchmark-only |" in row for row in rows)
    assert all("| P" in row for row in rows)