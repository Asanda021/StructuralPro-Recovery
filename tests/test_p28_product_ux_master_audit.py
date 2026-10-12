"""P28 — Product UX Master Audit acceptance tests."""
from core.ui.product_ux_audit import assert_product_ux_audit, run_product_ux_audit


def test_p28_product_ux_master_audit_passes():
    report = assert_product_ux_audit()
    assert report.passed
    assert len(report.checks) >= 8


def test_p28_audit_is_deterministic():
    first = run_product_ux_audit().as_dict()
    second = run_product_ux_audit().as_dict()
    assert first == second


def test_p28_audit_fails_closed_for_missing_evidence(monkeypatch):
    import core.ui.product_ux_audit as audit

    original = audit._text

    def missing(path: str) -> str:
        if path == "app/theme.py":
            return ""
        return original(path)

    monkeypatch.setattr(audit, "_text", missing)
    report = audit.run_product_ux_audit()
    assert not report.passed
    assert any(check.key == "visual_tokens" and not check.passed for check in report.checks)
