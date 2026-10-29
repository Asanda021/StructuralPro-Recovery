"""G2 fail-closed boundaries between spatial context and verified BIM members."""
from __future__ import annotations
import hashlib
import pytest
from core.drawings.site_context import SiteTerrainScene, verified_site_context
from core.drawings.existing_building_reference import (
    ExistingBuildingReferenceScene, verified_existing_reference)


def _surface(path):
    path.write_bytes(b"original IFC source fixture marker")
    sha=hashlib.sha256(path.read_bytes()).hexdigest()
    vertices=((0.0,0.0,0.0),(1.0,0.0,0.0),(0.0,1.0,0.0))
    return sha,vertices,((0,1,2),)


def test_site_context_has_no_member_identity_pick_or_quantity_and_source_is_revoked(tmp_path):
    source=tmp_path/"context.ifc"
    sha,vertices,faces=_surface(source)
    scene=SiteTerrainScene(source_path=str(source),source_sha256=sha,revision="R1",
        site_global_id=None,site_identity_canonical=False,vertices=vertices,triangles=faces)
    assert scene.quantity_authority is False
    assert scene.element_global_ids == frozenset()
    assert scene.site_identity_not_for_member_linking
    assert scene.site_global_id is None
    assert not hasattr(scene,"pick") and not hasattr(scene,"meshes")
    assert scene.projected_triangles(600,450)
    scene.orbit(0.1,0.2)
    scene.pan(10,-5)
    scene.set_zoom(1.1)
    assert scene.projected_triangles(600,450)
    scene.validate_source()
    source.write_bytes(b"modified")
    with pytest.raises(ValueError,match="تغییر"):
        scene.validate_source()


def test_existing_building_reference_does_not_enable_boq_or_retrofit_authority(tmp_path):
    source=tmp_path/"existing.ifc"
    sha,v,f=_surface(source)
    scene=ExistingBuildingReferenceScene(source_path=str(source),source_sha256=sha,
       revision="G2-REAL",vertices=v,triangles=f,source_member_count=245,
       source_with_geometry_count=220,
       displayed_source_global_id="real-ifc2x3-source-member",
       displayed_ifc_type="IfcWall")
    assert scene.source_member_count==245
    assert scene.source_with_geometry_count==220
    assert scene.member_identity_linkable is False
    assert scene.renovation_phases_verified is False
    assert scene.quantity_authority is False and scene.explicit_quantity_authority is False
    assert scene.element_global_ids==frozenset()
    assert not hasattr(scene,"pick")
    scene.validate_source()
    source.unlink()
    with pytest.raises(OSError):
        scene.validate_source()


def test_spatial_only_ifc_rejects_member_bearing_ifc4_without_reclassifying_members(tmp_path):
    from test_phase6_p2_benchmark_ifc100 import make_ifc_floors
    source=tmp_path/"has-real-members.ifc"
    make_ifc_floors(source,1)
    sha=hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError,match="IfcElement"):
        verified_site_context(source,revision="R1",expected_sha256=sha)
    with pytest.raises(ValueError,match="IFC2X3"):
        verified_existing_reference(source,revision="R1",expected_sha256=sha)


def test_spatial_only_ifc_fails_closed_on_fake_sha_and_missing_revision(tmp_path):
    source=tmp_path/"file.ifc"
    source.write_bytes(b"not a valid file")
    with pytest.raises(ValueError,match="هش"):
        verified_site_context(source,revision="R1",expected_sha256="0"*64)
    with pytest.raises(ValueError,match="نسخه"):
        verified_site_context(source,revision="")
    with pytest.raises(ValueError,match="SHA"):
        verified_existing_reference(source,revision="R1",expected_sha256="0"*64)
