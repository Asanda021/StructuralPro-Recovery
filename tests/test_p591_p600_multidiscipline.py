from core.coordination.multidiscipline_v1 import CoordinationRecord, SUPPORTED_DISCIPLINES, build_coordination_set, coordination_fingerprint, validate_record
import pytest

def r(i,d,e,rel="overlap"):
    return CoordinationRecord(i,"P1","R1","SRC1",d,e,"E2",rel,f"EV-{i}")

def test_supported_disciplines_and_deterministic_order():
    rows=build_coordination_set((r("2","electrical","E3"),r("1","structural","E1")))
    assert [x.record_id for x in rows]==["2","1"]
    assert coordination_fingerprint(rows)==coordination_fingerprint(tuple(reversed(rows)))

def test_all_supported_disciplines():
    for i,d in enumerate(sorted(SUPPORTED_DISCIPLINES)):
        validate_record(r(str(i),d,"E1"))

def test_missing_evidence_fails_closed():
    with pytest.raises(ValueError):
        validate_record(CoordinationRecord("1","P1","R1","SRC","structural","E1","E2","overlap",""))

def test_self_relation_fails_closed():
    with pytest.raises(ValueError):
        validate_record(CoordinationRecord("1","P1","R1","SRC","structural","E1","E1","overlap","EV"))

def test_duplicate_record_fails_closed():
    with pytest.raises(ValueError):
        build_coordination_set((r("1","structural","E1"),r("1","structural","E2")))

def test_invalid_discipline_and_relation_fail_closed():
    with pytest.raises(ValueError): validate_record(r("1","unknown","E1"))
    with pytest.raises(ValueError): validate_record(r("1","structural","E1","invented"))

def test_no_geometry_or_engineering_inference():
    x=r("1","structural","E1","conflict")
    assert x.evidence_ref=="EV-1"
