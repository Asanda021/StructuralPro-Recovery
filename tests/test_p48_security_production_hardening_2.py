import hashlib
import pytest
from core.security_hardening_v2 import *
def backup(project="p1", payload=b"data"): return BackupArtifact(project,"b1",hashlib.sha256(payload).hexdigest(),"2026-10-04T00:00:00Z")
def test_authorization_enforces_project_isolation():
    assert authorize(SecurityPrincipal("u1","p1","editor"),"p1",["editor"])
    with pytest.raises(SecurityHardeningError): authorize(SecurityPrincipal("u1","p2","editor"),"p1",["editor"])
def test_backup_integrity():
    assert validate_backup(backup(),b"data")
    with pytest.raises(SecurityHardeningError): validate_backup(backup(),b"tampered")
def test_audit_and_rate_limit_fail_closed():
    e=AuditEvent("p1","u1","export","2026-10-04T00:00:00Z","ticket-1")
    assert validate_audit_event(e) and enforce_rate_limit([e],"u1",2)
    assert not enforce_rate_limit([e],"u1",1)
def test_recovery_isolation():
    assert recovery_fingerprint("p1",[backup()],"restore")
    with pytest.raises(SecurityHardeningError): recovery_fingerprint("p1",[backup("p2")],"restore")
