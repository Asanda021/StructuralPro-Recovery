from core.drawing.cad_validation_v1 import CadEvidence, validate_cad, validate_evidence

def rows():
    return (
        CadEvidence("sample.dxf","dxf","A-WALL","LINE",1,"","W1",3.5,"2026-10-04T00:00:00Z"),
        CadEvidence("sample.dxf","dxf","A-DOOR","INSERT",0,"D-01","",None,"2026-10-04T00:00:00Z"),
        CadEvidence("sample.dxf","dxf","A-DIMS","DIMENSION",0,"","",4.2,"2026-10-04T00:00:00Z"),
    )

def test_cad_validation_collects_layers_blocks_dimensions_text_and_geometry():
    result=validate_cad(rows())
    assert result.entity_count==3
    assert result.layers==("A-DIMS","A-DOOR","A-WALL")
    assert result.blocks==("D-01",)
    assert result.dimensions==(3.5,4.2)
    assert result.text_count==1
    assert result.geometry_count==1
    assert len(result.fingerprint)==64

def test_validation_is_deterministic():
    assert validate_cad(rows())==validate_cad(tuple(reversed(rows())))

def test_missing_evidence_fails_closed():
    try:
        validate_evidence(())
    except ValueError as exc:
        assert "evidence" in str(exc)
    else:
        raise AssertionError("missing CAD evidence must fail closed")

def test_mixed_sources_fail_closed():
    bad=rows()+(CadEvidence("other.dwg","dwg","A","LINE",1,"","",None,"2026-10-04T00:00:00Z"),)
    try:
        validate_cad(bad)
    except ValueError as exc:
        assert "one CAD source" in str(exc)
    else:
        raise AssertionError("mixed sources must fail closed")
