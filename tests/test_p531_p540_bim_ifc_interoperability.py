import pytest
from core.bim.ifc_interoperability_v1 import InterchangeRecord, record_fingerprint, round_trip_verify

def rec(version="IFC4X3"):
    return InterchangeRecord("project-1","r2","source:A1","structural",version,"GUID-1","IfcBeam",(("Name","B1"),),(('Length',6.0),))

def test_deterministic_identity():
    assert record_fingerprint(rec()) == record_fingerprint(rec())

def test_round_trip_preserves_evidence():
    assert round_trip_verify(rec(), rec()) is True

def test_unsupported_version_fails_closed():
    with pytest.raises(ValueError):
        record_fingerprint(rec("IFC2X3"))

def test_external_identity_mismatch_fails_closed():
    returned=InterchangeRecord("project-1","r2","source:A1","structural","IFC4X3","GUID-2","IfcBeam",(("Name","B1"),),(('Length',6.0),))
    with pytest.raises(ValueError):
        round_trip_verify(rec(), returned)
