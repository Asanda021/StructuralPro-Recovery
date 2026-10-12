import pytest
from core.integration.integration_ecosystem_v1 import IntegrationEnvelope, fingerprint, validate_envelope


def envelope(fmt="json", status="draft"):
    return IntegrationEnvelope("e1", "project-1", "source-1", "r1", fmt, "hash", status)


def test_validation_preserves_revision():
    assert validate_envelope(envelope()).revision == "r1"


def test_unsupported_format_fails_closed():
    with pytest.raises(ValueError):
        validate_envelope(envelope("dwg"))


def test_invalid_status_fails_closed():
    with pytest.raises(ValueError):
        validate_envelope(envelope(status="unknown"))


def test_fingerprint_deterministic():
    assert fingerprint(envelope()) == fingerprint(envelope())
