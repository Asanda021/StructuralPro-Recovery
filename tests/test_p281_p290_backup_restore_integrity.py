from core.platform.backup_integrity_v1 import BackupEvidence,RestoreEvidence,ProjectIntegrityEvidence,restore_allowed,canonical_fingerprint
import pytest

def fp(value): return canonical_fingerprint({"value":value})

def evidence(result="accepted"):
    backup=BackupEvidence("B-1","P-1","R-3","2026-10-03T10:00:00+00:00",fp("backup"),result)
    restore=RestoreEvidence("B-1","operator","2026-10-03T10:05:00+00:00","R-4",result)
    integrity=ProjectIntegrityEvidence("P-1",fp("qty"),fp("totals"),"R-4",True)
    return backup,restore,integrity

def test_restore_accepts_valid_evidence():
    assert restore_allowed(*evidence(),"P-1")

def test_rejected_backup_fails_closed():
    assert not restore_allowed(*evidence("rejected"),"P-1")

def test_rejected_restore_fails_closed():
    b,_,i=evidence()
    r=RestoreEvidence("B-1","operator","2026-10-03T10:05:00+00:00","R-4","rejected")
    assert not restore_allowed(b,r,i,"P-1")

def test_identity_mismatch_fails():
    b,r,i=evidence()
    assert not restore_allowed(b,r,i,"P-2")
    r2=RestoreEvidence("B-2","operator","2026-10-03T10:05:00+00:00","R-4")
    assert not restore_allowed(b,r2,i,"P-1")

def test_integrity_failure_fails():
    b,r,i=evidence()
    bad=ProjectIntegrityEvidence("P-1",fp("qty"),fp("totals"),"R-4",False)
    assert not restore_allowed(b,r,bad,"P-1")

def test_revision_mismatch_fails():
    b,r,_=evidence()
    bad=ProjectIntegrityEvidence("P-1",fp("qty"),fp("totals"),"R-5",True)
    assert not restore_allowed(b,r,bad,"P-1")

def test_fingerprint_is_deterministic():
    payload={"z":2,"a":{"b":1,"x":"یونولیت"}}
    assert canonical_fingerprint(payload)==canonical_fingerprint({"a":{"x":"یونولیت","b":1},"z":2})

def test_invalid_backup_fingerprint_is_rejected():
    with pytest.raises(ValueError):
        BackupEvidence("B","P","R","2026-10-03T10:00:00+00:00","bad")
