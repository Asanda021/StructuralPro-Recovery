import pytest
from core.collaboration.enterprise_integrity_v1 import (
    TenantIdentity,SessionEvidence,NotificationEvidence,ProviderBoundary,
    RecoveryEvidence,authorize,canonical_fingerprint,
)

def tenant(role="editor"): return TenantIdentity("t1","p1","u1",role)

def test_tenant_identity_and_authorization():
    assert authorize(tenant(),{"editor","admin"})
    with pytest.raises(PermissionError): authorize(tenant("viewer"),{"editor"})

def test_invalid_tenant_fails_closed():
    with pytest.raises(ValueError): TenantIdentity("","","u1","editor").validate()
    with pytest.raises(ValueError): tenant("superuser").validate()

def test_session_is_revision_bound():
    assert SessionEvidence("s1","t1","u1",True,4).validate()
    with pytest.raises(ValueError): SessionEvidence("s1","t1","u1",True,-1).validate()

def test_notification_is_evidenced():
    assert NotificationEvidence("n1","t1","updated","u2","a"*64).validate()
    with pytest.raises(ValueError): NotificationEvidence("n1","t1","updated","u2","x").validate()

def test_provider_never_assumes_verified_credentials():
    with pytest.raises(ValueError): ProviderBoundary("cloud-x","prod",True,False).validate()
    assert ProviderBoundary("local","offline",False,False).validate()

def test_recovery_requires_test_evidence():
    with pytest.raises(ValueError): RecoveryEvidence("snap","t1","a"*64,True,False).validate()
    assert RecoveryEvidence("snap","t1","a"*64,True,True).validate()

def test_fingerprint_is_deterministic():
    a=tenant(); b=SessionEvidence("s1","t1","u1",False,2)
    assert canonical_fingerprint(a,b)==canonical_fingerprint(a,b)
