import pytest
from core.platform.production_hardening_gate_v1 import harden_payload, validate_no_unknown, tamper_fingerprint

def test_required_fields_fail_closed():
    result = harden_payload({"project_id": "P1"}, required=("project_id", "revision"))
    assert not result.valid and "missing:revision" in result.errors

def test_valid_payload_is_deterministic():
    a = harden_payload({"b": 2, "a": 1}); b = harden_payload({"a": 1, "b": 2})
    assert a == b and a.valid

def test_unknown_fields_fail_closed():
    result = validate_no_unknown({"project_id": "P1", "debug": True}, ("project_id",))
    assert not result.valid and result.errors == ("unknown:debug",)

def test_non_object_rejected():
    with pytest.raises(ValueError): harden_payload([])  # type: ignore[arg-type]

def test_fingerprint_changes_after_mutation():
    payload = {"project_id": "P1", "revision": "R1"}; before = tamper_fingerprint(payload)
    payload["revision"] = "R2"
    assert before != tamper_fingerprint(payload)
