"""Priority 55: external provisioning evidence must be explicit."""
import pytest
from core.platform.provisioning import (
    ProvisioningEvidence, build_provisioning_manifest, release_provisioning_ready,
)

def verified(name):
    return ProvisioningEvidence(
        component=name, status="verified", version="1.0",
        sha256="a"*64, source_ref="official://source",
        license_ref="evidence://license",
    )

def test_verified_manifest_is_release_ready():
    items=[verified("official-price-list"), verified("dwg-converter")]
    manifest=build_provisioning_manifest(items)
    assert manifest["valid"] is True
    assert len(manifest["sha256"]) == 64
    assert release_provisioning_ready(items) is True

def test_required_unverified_dependency_fails_closed():
    item=ProvisioningEvidence("gguf-model", status="pending")
    result=build_provisioning_manifest([item])
    assert result["valid"] is False
    assert "required component is not verified" in result["errors"][0]
    assert release_provisioning_ready([item]) is False

def test_verified_dependency_requires_provenance_and_checksum():
    item=ProvisioningEvidence("dwg-converter", status="verified")
    errors=item.validate()
    assert "verified component requires a valid sha256" in errors
    assert "verified component requires source_ref" in errors
    assert "verified component requires license_ref" in errors

def test_duplicate_components_are_rejected():
    result=build_provisioning_manifest([verified("model"), verified("MODEL")])
    assert result["valid"] is False
    assert any("duplicate component" in e for e in result["errors"])

def test_non_required_pending_component_can_be_recorded():
    item=ProvisioningEvidence("optional-model", status="pending", required=False)
    assert item.validate() == []
    assert build_provisioning_manifest([item])["valid"] is True

def test_invalid_status_is_rejected():
    item=ProvisioningEvidence("price-list", status="unknown")
    assert "invalid status" in item.validate()
