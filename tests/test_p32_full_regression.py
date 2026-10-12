from core.platform.p32_full_regression import REQUIRED_SURFACES,run_p32_gate

def test_p32_full_regression_is_green():
    r=run_p32_gate()
    assert r.valid,r.errors
    assert r.checks==REQUIRED_SURFACES

def test_p32_is_deterministic():
    a,b=run_p32_gate(),run_p32_gate()
    assert a.valid and b.valid and a.checks==b.checks==REQUIRED_SURFACES and a.errors==b.errors==()

def test_p32_surface_inventory_is_complete():
    assert set(REQUIRED_SURFACES)=={"core_functionality","domain_outputs","ui_surfaces","data_integrity","release_artifacts","production_boundary","release_health"}
