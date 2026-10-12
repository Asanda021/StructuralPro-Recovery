from core.estimate.price_calibration_v1 import RateEvidence, calibrate_rates, validate_rates

def row(rate=100.0):
    return RateEvidence("MAT-001","Concrete","m3",rate,"IRR","official://price-list","National Price List","1405","2026-03-20","2026-10-04T00:00:00Z")

def test_rate_calibration_is_deterministic():
    a=calibrate_rates((row(),))
    b=calibrate_rates((row(),))
    assert a==b
    assert a[0].fingerprint and len(a[0].fingerprint)==64

def test_missing_evidence_fails_closed():
    try:
        validate_rates(())
    except ValueError as exc:
        assert "evidence" in str(exc)
    else:
        raise AssertionError("missing rate evidence must fail closed")

def test_conflicting_rates_fail_closed():
    try:
        calibrate_rates((row(100),row(120)))
    except ValueError as exc:
        assert "conflicting" in str(exc)
    else:
        raise AssertionError("conflicting rates must fail closed")

def test_negative_rate_fails_closed():
    try:
        validate_rates((row(-1),))
    except ValueError as exc:
        assert "negative" in str(exc)
    else:
        raise AssertionError("negative rates must fail closed")
