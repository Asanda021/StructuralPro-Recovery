from core.platform.release import LicenseRecord, LicenseVerifier
from core.platform.release_security import find_embedded_secret_candidates

def test_license_rejects_wrong_product_missing_issuer_and_signature():
    verifier = LicenseVerifier(lambda payload, sig: True)
    base = LicenseRecord("StructuralPro", "LIC-1", "Customer", issuer="issuer")
    assert verifier.verify(base, "sig")
    assert not verifier.verify(LicenseRecord("Other", "LIC-1", "Customer", issuer="issuer"), "sig")
    assert not verifier.verify(LicenseRecord("StructuralPro", "LIC-1", "Customer"), "sig")
    assert not verifier.verify(base, "")

def test_license_verifier_fails_closed_when_injected_verifier_raises():
    verifier = LicenseVerifier(lambda payload, sig: (_ for _ in ()).throw(RuntimeError("bad verifier")))
    record = LicenseRecord("StructuralPro", "LIC-1", "Customer", issuer="issuer")
    assert verifier.verify(record, "sig") is False

def test_no_embedded_secret_candidates_in_release_surfaces():
    assert find_embedded_secret_candidates() == []
