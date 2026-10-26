from __future__ import annotations

from hashlib import sha256

import pytest

from core.platform.application import StructuralProApp
from test_phase5_p3_trusted_identity_store import SwitchingIdentityProvider, identity


def test_real_attachment_service_binds_project_hash_and_detects_tamper(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    service = StructuralProApp(tmp_path / "app", identity_provider=identities)
    service.create_project("one", "P1")
    source = tmp_path / "source.pdf"
    source.write_bytes(b"verified-pdf")

    document = service.add_project_document("P1", source)
    assert document["sha256"] == sha256(b"verified-pdf").hexdigest()
    assert service.project_documents("P1")[0]["integrity"] == "verified"

    source.write_bytes(b"tampered")
    observed = service.project_documents("P1")[0]
    assert observed["integrity"] == "hash-mismatch"
    assert observed["sha256"] == document["sha256"]


def test_attachment_symlink_and_cross_project_reuse_are_rejected(tmp_path):
    identities = SwitchingIdentityProvider(identity("subject:A", "Alice"))
    service = StructuralProApp(tmp_path / "app", identity_provider=identities)
    service.create_project("one", "P1")
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"sheet")
    link = tmp_path / "link.xlsx"
    link.symlink_to(source)
    with pytest.raises(ValueError, match="regular non-symlink"):
        service.add_project_document("P1", link)

    service.add_project_document("P1", source)
    identities.identity = identity("subject:B", "Bob")
    service.create_project("two", "P2")
    with pytest.raises(PermissionError, match="another project"):
        service.add_project_document("P2", source)

