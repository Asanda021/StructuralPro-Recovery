from core.platform.p33_final_competitive_rebenchmark import REQUIRED_IDS,run_p33_gate

def test_p33_final_rebenchmark_is_complete():
    r=run_p33_gate()
    assert r.valid,r.gaps
    assert r.benchmark_rows==45
    assert r.mapped_rows==45

def test_p33_matrix_inventory_is_stable():
    assert REQUIRED_IDS==tuple(f"B{i:02d}" for i in range(1,46))
    a,b=run_p33_gate(),run_p33_gate()
    assert a==b
