from datetime import date
from core.platform.release import LicenseRecord, LicenseVerifier

def _signed_payload(payload: bytes, signature: str) -> bool:
    return signature == "valid" and bool(payload)

def test_license_payload_and_fingerprint_are_deterministic():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "2099-12-31", ("boq", "finance"), "StructuralPro Licensing")
    assert record.canonical_bytes() == record.canonical_bytes()
    assert len(record.fingerprint()) == 64
    assert record.has_feature("boq")
    assert not record.has_feature("missing")

def test_verifier_accepts_valid_unexpired_license():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "2099-12-31", ("boq",), "Issuer")
    verifier = LicenseVerifier(_signed_payload, today=lambda: date(2026, 10, 2))
    assert verifier.verify(record, "valid")

def test_verifier_rejects_expired_license():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "2026-10-01", ("boq",), "Issuer")
    verifier = LicenseVerifier(_signed_payload, today=lambda: date(2026, 10, 2))
    assert not verifier.verify(record, "valid")

def test_verifier_rejects_malformed_expiry():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "not-a-date", ("boq",), "Issuer")
    verifier = LicenseVerifier(_signed_payload)
    assert not verifier.verify(record, "valid")

def test_verifier_rejects_revoked_license():
    record = LicenseRecord("StructuralPro", "LIC-REVOKED", "Customer", "", ("boq",), "Issuer")
    verifier = LicenseVerifier(_signed_payload, revoked_license_ids={"LIC-REVOKED"})
    assert not verifier.verify(record, "valid")

def test_verifier_rejects_duplicate_features():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "", ("boq", "boq"), "Issuer")
    verifier = LicenseVerifier(_signed_payload)
    assert not verifier.verify(record, "valid")

def test_verifier_fails_closed_for_invalid_identity_and_signature():
    verifier = LicenseVerifier(_signed_payload)
    bad_product = LicenseRecord("Other", "LIC-001", "Customer", "", (), "Issuer")
    bad_customer = LicenseRecord("StructuralPro", "LIC-001", " ", "", (), "Issuer")
    bad_issuer = LicenseRecord("StructuralPro", "LIC-001", "Customer", "", (), "")
    assert not verifier.verify(bad_product, "valid")
    assert not verifier.verify(bad_customer, "valid")
    assert not verifier.verify(bad_issuer, "valid")
    assert not verifier.verify(LicenseRecord("StructuralPro", "LIC-001", "Customer", "", (), "Issuer"), "")

def test_verifier_contains_no_signing_secret_requirement():
    record = LicenseRecord("StructuralPro", "LIC-001", "Customer", "", (), "Issuer")
    verifier = LicenseVerifier(lambda payload, signature: signature == "valid")
    assert verifier.verify(record, "valid")
