from __future__ import annotations

import hashlib

import pytest

from core.projects.audit import AuditTrail
from core.security_hardening_v2 import (
    SecurityHardeningError,
    SecurityPrincipal,
    require_authorized,
    validate_project_file,
)


def principal(role: str = "editor", project_id: str = "P1") -> SecurityPrincipal:
    return SecurityPrincipal("user-1", project_id, role)


def test_explicit_authorization_gate_fails_closed_for_wrong_role_and_project():
    assert require_authorized(principal(), "P1", ("editor",)) is True
    with pytest.raises(PermissionError, match="not authorized"):
        require_authorized(principal("viewer"), "P1", ("editor",))
    with pytest.raises(SecurityHardeningError, match="project identity mismatch"):
        require_authorized(principal(project_id="P2"), "P1", ("editor",))


def test_project_file_is_regular_inside_its_project_root_and_hash_bound(tmp_path):
    root = tmp_path / "P1"
    root.mkdir()
    document = root / "source.pdf"
    document.write_bytes(b"verified-pdf-evidence")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()

    assert validate_project_file(principal(), "P1", root, document, digest) == document.resolve()

    other = tmp_path / "P2"
    other.mkdir()
    foreign = other / "source.pdf"
    foreign.write_bytes(document.read_bytes())
    with pytest.raises(SecurityHardeningError, match="project file isolation"):
        validate_project_file(principal(), "P1", root, foreign, digest)
    with pytest.raises(SecurityHardeningError, match="integrity mismatch"):
        validate_project_file(principal(), "P1", root, document, "0" * 64)

    link = root / "linked.pdf"
    link.symlink_to(foreign)
    with pytest.raises(SecurityHardeningError, match="regular non-symlink"):
        validate_project_file(principal(), "P1", root, link, digest)


def test_controlled_audit_event_records_identity_role_revisions_and_result():
    trail = AuditTrail()
    event = trail.record_controlled(
        action="update",
        entity="boq",
        entity_id="BOQ-7",
        principal=principal(),
        project_id="P1",
        required_roles=("editor",),
        revision_before=8,
        revision_after=9,
        reference="change-request:CR-17",
        status="success",
        timestamp="2026-10-26T10:00:00+00:00",
    )

    assert event["actor"] == "user-1"
    assert event["actor_role"] == "editor"
    assert event["revision_before"] == 8 and event["revision_after"] == 9
    assert event["status"] == "success"
    assert trail.verify()


def test_controlled_audit_denial_is_recorded_without_authorizing_mutation():
    trail = AuditTrail()
    with pytest.raises(PermissionError, match="not authorized"):
        trail.record_controlled(
            action="update",
            entity="approved_boq",
            entity_id="BOQ-7",
            principal=principal("viewer"),
            project_id="P1",
            required_roles=("owner", "admin"),
            revision_before=9,
            revision_after=None,
            reference="attempt:17",
            status="success",
            timestamp="2026-10-26T10:01:00+00:00",
        )
    events = trail.list()
    assert len(events) == 1
    assert events[0]["status"] == "failure"
    assert events[0]["revision_after"] is None
    assert trail.verify()


def test_audit_chain_detects_event_tampering_and_rejects_invalid_revision_transition():
    trail = AuditTrail()
    trail.record_controlled(
        action="create",
        entity="project",
        entity_id="P1",
        principal=principal("owner"),
        project_id="P1",
        required_roles=("owner",),
        revision_before=None,
        revision_after=1,
        reference="new-project:P1",
        status="success",
        timestamp="2026-10-26T10:02:00+00:00",
    )
    tampered = trail.list()
    tampered[0]["entity_id"] = "P2"
    assert AuditTrail(tampered).verify() is False

    with pytest.raises(ValueError, match="revision transition"):
        trail.record_controlled(
            action="update",
            entity="project",
            entity_id="P1",
            principal=principal(),
            project_id="P1",
            required_roles=("editor",),
            revision_before=1,
            revision_after=3,
            reference="attempt:skip",
            status="success",
        )
