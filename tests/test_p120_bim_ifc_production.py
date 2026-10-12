from core.acceptance.p120_bim_ifc import run_p120

def test_p120_bim_ifc_production_acceptance():
    result = run_p120()
    assert result["verified"] is True
    assert result["element_count"] == 3
    assert result["takeoff_count"] == 3
    assert result["explicit_volume_m3"] == 3.7
    assert result["drawing_statuses"] == ["match", "match"]
    assert result["round_trip"] is True
    assert result["manifest_verified"] is True
    assert len(result["fingerprint"]) == 64
