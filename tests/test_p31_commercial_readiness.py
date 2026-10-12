from core.platform.p31_commercial_readiness import REQUIRED_SURFACES, run_p31_gate

def test_p31_gate_is_green():
    result=run_p31_gate()
    assert result.valid,result.errors
    assert result.checks==REQUIRED_SURFACES

def test_p31_is_deterministic():
    a,b=run_p31_gate(),run_p31_gate()
    assert a.checks==b.checks==REQUIRED_SURFACES
    assert a.errors==b.errors==()

def test_p31_surface_inventory_is_complete():
    assert len(REQUIRED_SURFACES)==9
    assert set(REQUIRED_SURFACES)=={
        "licensing","activation","entitlements","trial_demo","versioning",
        "updates","migration","backup_restore","documentation_help",
    }

def test_p31_update_gate_rejects_downgrade():
    from core.platform.updates import validate_update
    assert "downgrade or same-version update rejected" in validate_update(
        "0.1.1",{"version":"0.1.0","channel":"stable","sha256":"0"*64,"size":0}
    )
