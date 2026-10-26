from __future__ import annotations

import os
import sqlite3
import sys
from dataclasses import dataclass

import pytest

from core.platform.identity import OperatingSystemIdentity, SystemIdentityProvider
from core.projects.store import ProjectStore


@dataclass
class SwitchingIdentityProvider:
    identity: OperatingSystemIdentity

    def current(self) -> OperatingSystemIdentity:
        return self.identity


def identity(subject: str, name: str) -> OperatingSystemIdentity:
    return OperatingSystemIdentity(
        subject_id=subject,
        display_name=name,
        authority="test-controlled",
        platform="test",
        authenticated=True,
    )


def test_posix_identity_comes_from_kernel_uid_not_spoofable_environment(monkeypatch):
    if os.name == "nt":
        pytest.skip("POSIX identity assertion")
    monkeypatch.setenv("USER", "forged-user")
    monkeypatch.setenv("USERNAME", "forged-user")

    observed = SystemIdentityProvider().current()

    assert observed.subject_id == f"uid:{os.geteuid()}"
    assert observed.authority == "posix-euid"
    assert observed.authenticated is True
    assert observed.display_name != "forged-user"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows Native only")
def test_windows_identity_is_read_from_the_live_access_token():
    observed = SystemIdentityProvider().current()
    assert observed.authority == "windows-access-token"
    assert observed.subject_id.startswith("S-1-")
    assert observed.authenticated is True


def test_project_acl_is_bound_to_trusted_identity_and_prevents_self_escalation(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    store = ProjectStore(tmp_path / "projects.db", identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    assert store.current_principal("P1").role == "owner"

    identities.identity = identity("subject:B", "Bob")
    with pytest.raises(PermissionError, match="not authorized"):
        store.get("P1")
    with pytest.raises(PermissionError, match="not authorized"):
        store.grant_role("P1", "subject:B", "owner", reference="self-promotion")

    identities.identity = identity("subject:A", "Alice")
    store.grant_role("P1", "subject:B", "viewer", reference="acl:viewer")
    identities.identity = identity("subject:B", "Bob")
    assert store.get("P1")["name"] == "one"
    with pytest.raises(PermissionError, match="not authorized"):
        changed = {"id": "P1", "name": "forged", "boq": []}
        store.save("P1", changed)

    identities.identity = identity("subject:A", "Alice")
    store.grant_role("P1", "subject:B", "editor", reference="acl:editor")
    identities.identity = identity("subject:B", "Bob")
    changed = store.get("P1")
    changed["name"] = "edited"
    store.save("P1", changed)
    assert store.get("P1")["name"] == "edited"


def test_cross_project_access_is_denied_and_denial_is_audited(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    store = ProjectStore(tmp_path / "projects.db", identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    identities.identity = identity("subject:B", "Bob")
    store.save("P2", {"id": "P2", "name": "two", "boq": []})

    with pytest.raises(PermissionError, match="not authorized"):
        store.get("P1")

    identities.identity = identity("subject:A", "Alice")
    events = store.audit_events("P1")
    assert events[-1]["status"] == "failure"
    assert events[-1]["actor"] == "subject:B"
    assert events[-1]["action"] == "open"
    assert store.verify_audit("P1") is True


def test_editor_cannot_bypass_financial_policy_with_a_direct_legacy_save(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    store = ProjectStore(tmp_path / "projects.db", identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    store.grant_role("P1", "subject:B", "editor", reference="acl:editor")
    identities.identity = identity("subject:B", "Bob")
    project = store.get("P1")
    project["financial_documents"] = [{"id": 1, "amount": "100", "status": "paid"}]

    with pytest.raises(PermissionError, match="not authorized"):
        store.save("P1", project)

    identities.identity = identity("subject:A", "Alice")
    assert not store.get("P1").get("financial_documents")
    assert store.audit_events("P1")[-1]["status"] == "failure"

    identities.identity = identity("subject:B", "Bob")
    with pytest.raises(PermissionError, match="not authorized"):
        store.save("P1", store.get("P1"), manual_formula_command={"action": "approve"})


def test_viewer_cannot_create_database_backup(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    store = ProjectStore(tmp_path / "projects.db", identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    store.grant_role("P1", "subject:B", "viewer", reference="acl:viewer")
    identities.identity = identity("subject:B", "Bob")

    with pytest.raises(PermissionError, match="not authorized"):
        store.backup(tmp_path / "forbidden.db")
    assert not (tmp_path / "forbidden.db").exists()

    identities.identity = identity("subject:A", "Alice")
    result = store.backup(tmp_path / "allowed.db")
    assert result["path"] == str(tmp_path / "allowed.db")
    event = store.audit_events("P1")[-1]
    assert event["action"] == "export" and event["status"] == "success"
    assert len(event["after"]["backup_sha256"]) == 64


def test_domain_validation_rejection_is_a_complete_noop_and_stores_no_secret(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    store = ProjectStore(tmp_path / "projects.db", identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    project = store.get("P1")
    before_events = store.audit_events("P1")
    project["financial_records"] = [{"id": 1, "secret": "must-not-enter-audit"}]

    with pytest.raises(ValueError, match="سند مالی"):
        store.save("P1", project)

    assert store.audit_events("P1") == before_events
    assert "must-not-enter-audit" not in str(store.audit_events("P1"))


def test_audit_is_append_only_persistent_and_atomic_with_project_save(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    path = tmp_path / "projects.db"
    store = ProjectStore(path, identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    initial = store.audit_events("P1")
    assert initial[-1]["revision_after"] == 1
    assert len(initial[-1]["after"]["payload_sha256"]) == 64
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.db.execute("UPDATE security_audit SET status='failure'")
    store.db.rollback()
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.db.execute("DELETE FROM security_audit")
    store.db.rollback()

    store.db.execute("""
        CREATE TRIGGER reject_test_audit BEFORE INSERT ON security_audit
        BEGIN SELECT RAISE(ABORT, 'forced audit failure'); END
    """)
    changed = store.get("P1")
    changed["name"] = "must-not-commit"
    with pytest.raises(sqlite3.DatabaseError, match="forced audit failure"):
        store.save("P1", changed)
    store.db.execute("DROP TRIGGER reject_test_audit")
    assert store.get("P1")["name"] == "one"
    assert store.get("P1")["_meta"]["version"] == 1
    store.close()

    reopened = ProjectStore(path, identity_provider=identities)
    assert reopened.verify_audit("P1") is True
    assert reopened.audit_events("P1") == initial


def test_tampered_persistent_audit_fails_closed_when_database_reopens(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    path = tmp_path / "projects.db"
    store = ProjectStore(path, identity_provider=identities)
    store.save("P1", {"id": "P1", "name": "one", "boq": []})
    store.close()

    raw = sqlite3.connect(path)
    raw.execute("DROP TRIGGER security_audit_no_update")
    raw.execute("UPDATE security_audit SET actor='forged' WHERE sequence=1")
    raw.commit()
    raw.close()

    with pytest.raises(RuntimeError, match="audit integrity"):
        ProjectStore(path, identity_provider=identities)

