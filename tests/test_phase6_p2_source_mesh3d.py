"""First vertical slice of Phase 6 P2: no fake 3D and no quantity authority."""
import copy
import hashlib
from pathlib import Path

import pytest

from core.drawings.source_mesh3d import VerifiedScene3D


def real_contract(tmp_path):
    source = tmp_path / "model.ifc"
    source.write_bytes(b"IFC display fixture with source provenance; no fictional geometry")
    sha = hashlib.sha256(source.read_bytes()).hexdigest()
    return {"policy": "ifc_display_geometry_v1", "source_path": str(source),
            "source_sha256": sha, "revision": "R1",
            "coordinate_system": "IFC world coordinates in metres",
            "quantity_authority": False, "omitted_ids": [],
            "elements": [
                {"global_id": "IFC-WALL-01", "ifc_type": "IfcWall", "storey_id": "Level-01",
                 "vertices_m": [[0.0, 0.0, 0.0], [2.0, 0.0, 0.0],
                                [0.0, 0.0, 3.0]],
                 "triangles": [[0, 1, 2]]},
                {"global_id": "IFC-DUCT-02", "ifc_type": "IfcDuctSegment", "storey_id": "Level-02",
                 "vertices_m": [[0.0, 1.0, 3.0], [1.0, 1.0, 3.0],
                                [0.0, 1.0, 4.0]],
                 "triangles": [[0, 1, 2]]},
            ]}


def test_real_coordinates_orbit_zoom_floors_and_member_picking(tmp_path):
    contract = real_contract(tmp_path)
    frozen = copy.deepcopy(contract)
    scene = VerifiedScene3D(contract)
    assert scene.quantity_authority is False
    assert scene.source_sha256 == contract["source_sha256"]
    assert scene.storeys == ("Level-01", "Level-02")
    original = scene.visible_faces(800, 600)
    assert len(original) == 2
    assert {x.ifc_type for x in original} == {"IfcWall", "IfcDuctSegment"}
    center = tuple(sum(p[i] for p in original[0].points)/3 for i in (0, 1))
    assert scene.pick(*center, 800, 600) in ("IFC-WALL-01", "IFC-DUCT-02")
    floor = scene.visible_faces(800, 600, storey_id="Level-02")
    assert len(floor) == 1 and floor[0].global_id == "IFC-DUCT-02"
    selected = scene.visible_faces(800, 600, selected_id="IFC-WALL-01")
    assert len(selected) == 1 and selected[0].global_id == "IFC-WALL-01"
    scene.orbit(0.4, -0.2)
    rotated = scene.visible_faces(800, 600)
    assert rotated != original
    scene.set_zoom(1.5)
    assert scene.visible_faces(800, 600) != rotated
    scene.pan(25, -5)
    assert scene.visible_faces(800, 600) != rotated
    scene.reset_view()
    assert scene.visible_faces(800, 600) == original
    assert contract == frozen  # project/BOQ never mutated


@pytest.mark.parametrize("field,value", [
    ("policy", "unknown"), ("quantity_authority", True),
    ("coordinate_system", "unknown"), ("revision", ""),
    ("source_sha256", "not-a-hash")])
def test_invalid_provenance_fails_closed(tmp_path, field, value):
    contract = real_contract(tmp_path)
    contract[field] = value
    with pytest.raises(ValueError):
        VerifiedScene3D(contract)


def test_source_replacement_not_opened(tmp_path):
    contract = real_contract(tmp_path)
    Path(contract["source_path"]).write_bytes(b"later revision")
    with pytest.raises(ValueError, match="تغییر"):
        VerifiedScene3D(contract)


@pytest.mark.parametrize("operation", ["duplicate", "invalid_vertex", "nan", "invalid_triangle",
                                       "unknown_floor", "no_geometry", "capacity"])
def test_invalid_geometry_or_selection_never_fabricates_model(tmp_path, operation):
    contract = real_contract(tmp_path)
    if operation == "duplicate":
        contract["elements"][1]["global_id"] = "IFC-WALL-01"
    elif operation == "invalid_vertex":
        contract["elements"][0]["vertices_m"][0] = [0, 1]
    elif operation == "nan":
        contract["elements"][0]["vertices_m"][0][0] = float("nan")
    elif operation == "invalid_triangle":
        contract["elements"][0]["triangles"] = [[0, 1, 5]]
    elif operation == "no_geometry":
        contract["elements"][0]["vertices_m"] = []
    elif operation == "capacity":
        contract["elements"][0]["triangles"] *= 3
    if operation == "unknown_floor":
        scene = VerifiedScene3D(contract)
        with pytest.raises(ValueError):
            scene.visible_faces(800, 600, storey_id="Imaginary")
    else:
        with pytest.raises(ValueError):
            VerifiedScene3D(contract, max_triangles=2)


def test_unknown_id_and_bad_camera_fail_closed(tmp_path):
    scene = VerifiedScene3D(real_contract(tmp_path))
    with pytest.raises(ValueError):
        scene.visible_faces(800, 600, selected_id="missing")
    with pytest.raises(ValueError):
        scene.set_zoom(-1)
    with pytest.raises(ValueError):
        scene.orbit(float("nan"), 0)
    with pytest.raises(ValueError):
        scene.visible_faces(0, 800)


def test_ifc_types_not_restricted_to_structure(tmp_path):
    scene = VerifiedScene3D(real_contract(tmp_path))
    assert any(m.ifc_type == "IfcDuctSegment" for m in scene.meshes)
    assert scene.source_sha256 and scene.quantity_authority is False
