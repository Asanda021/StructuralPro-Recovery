from core.platform.p35_final_signoff import REQUIRED_SURFACES, run_p35_gate

def test_p35_final_signoff_passes():
    r=run_p35_gate()
    assert r.signed_off, r.blockers
    assert r.surfaces == REQUIRED_SURFACES
    assert r.fingerprint

def test_p35_is_deterministic():
    assert run_p35_gate() == run_p35_gate()

def test_p35_contains_final_product_surface():
    assert "final_product" in run_p35_gate().surfaces
