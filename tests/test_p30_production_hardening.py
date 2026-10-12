from core.platform.p30_production_hardening import REQUIRED_SURFACES, run_p30_gate

def test_p30_gate_is_green():
    result = run_p30_gate()
    assert result.valid, result.errors
    assert result.checks == REQUIRED_SURFACES

def test_p30_gate_is_deterministic():
    a = run_p30_gate()
    b = run_p30_gate()
    assert a.checks == b.checks == REQUIRED_SURFACES
    assert a.errors == b.errors == ()

def test_p30_requires_every_master_surface():
    expected = {
        "performance","memory","large_projects_pdf_cad_bim","concurrency",
        "error_handling","crash_recovery","logging","security","data_integrity",
        "backup_restore","migration","compatibility",
    }
    assert set(REQUIRED_SURFACES) == expected
    assert len(REQUIRED_SURFACES) == len(expected)

def test_p30_fails_closed_on_bad_payload():
    from core.platform.production_hardening_gate_v1 import harden_payload
    result = harden_payload({}, required=("source_id",))
    assert not result.valid
    assert result.errors == ("missing:source_id",)

def test_p30_backup_roundtrip_preserves_data():
    from core.platform.backup import create_backup, restore_backup
    source = {"name":"P30","items":[1,2,3]}
    backup = create_backup("p30", 4, source)
    assert restore_backup(backup, expected_project_id="p30") == source
