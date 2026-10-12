import hashlib
from core.platform.provisioning import ProvisioningEvidence
from core.platform.update_release_trust_v1 import build_release_manifest
from core.platform.production_readiness_attestation_v1 import attest_production_readiness

def verified(name):
    return ProvisioningEvidence(name,"verified","1.0","a"*64,"official://source","evidence://license")

def test_complete_attestation_is_ready_and_fingerprinted():
    data=b"release"
    manifest=build_release_manifest("2.1.0","stable",data)
    result=attest_production_readiness("2.0.0",manifest,[verified("price-list")],[("runtime",lambda:True)],artifact=data)
    assert result.ready
    assert len(result.fingerprint)==64
    assert result.errors==()

def test_unverified_provisioning_blocks_release():
    data=b"release"
    manifest=build_release_manifest("2.1.0","stable",data)
    result=attest_production_readiness("2.0.0",manifest,[ProvisioningEvidence("dwg-converter")],[("runtime",lambda:True)],artifact=data)
    assert not result.ready
    assert any("provisioning:" in e for e in result.errors)

def test_failed_runtime_check_blocks_release():
    data=b"release"
    manifest=build_release_manifest("2.1.0","stable",data)
    result=attest_production_readiness("2.0.0",manifest,[verified("price-list")],[("runtime",lambda:False)],artifact=data)
    assert not result.ready
    assert any("readiness: runtime" in e for e in result.errors)

def test_bad_artifact_blocks_release():
    data=b"release"
    manifest=build_release_manifest("2.1.0","stable",data)
    result=attest_production_readiness("2.0.0",manifest,[verified("price-list")],[("runtime",lambda:True)],artifact=b"tampered")
    assert not result.ready
    assert any("artifact bytes" in e for e in result.errors)
