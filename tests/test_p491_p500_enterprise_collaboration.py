import pytest
from core.collaboration.enterprise_collaboration_v1 import CollaborationChange, fingerprint, transition


def change(role="editor", status="draft"):
    return CollaborationChange("c1", "project-1", "user-1", role, "r1", ("drawing:A1",), "payload-hash", status)


def test_change_keeps_revision_and_evidence():
    c = change()
    assert c.revision == "r1"
    assert c.source_ids == ("drawing:A1",)


def test_invalid_role_fails_closed():
    with pytest.raises(ValueError):
        transition(change("unknown"), "review")


def test_approval_requires_approver():
    with pytest.raises(ValueError):
        transition(change("editor"), "approved")


def test_approver_can_approve():
    assert transition(change("approver"), "approved").status == "approved"


def test_missing_evidence_fails_closed():
    c = CollaborationChange("c1", "project-1", "user-1", "editor", "r1", (), "hash")
    with pytest.raises(ValueError):
        fingerprint(c)


def test_fingerprint_is_deterministic():
    c = change()
    assert fingerprint(c) == fingerprint(c)
