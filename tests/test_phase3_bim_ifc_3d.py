"""Phase 3 BIM/IFC/3D integration regression tests."""
import json
import pytest
from core.drawings.model_registry import ModelRegistry, ModelSource, ModelObject
from core.drawings.bim_exchange import export_registry_json, export_ifc


def registry():
    return ModelRegistry(
        sources=[
            ModelSource("IFC-1", "model.ifc", "ifc", revision="1", discipline="structural", units="m"),
            ModelSource("CAD-1", "model.dxf", "dxf", revision="1", discipline="structural", units="m"),
        ],
        objects=[
            ModelObject("IFC-1", "W1", "IfcWall", name="Wall", level="L1", quantities={"Length": 5}),
            ModelObject("CAD-1", "W1", "IfcWall", name="Wall 2D", level="L1", quantities={"Length": 5}),
            ModelObject("IFC-1", "C1", "IfcColumn", name="Column", level="L2", quantities={"Volume": 3}),
        ],
    )


def test_cross_source_duplicate_detection_does_not_delete_objects():
    r = registry()
    duplicates = r.cross_source_duplicates()
    assert duplicates == [{
        "object_id": "W1",
        "object_type": "IfcWall",
        "source_id": "CAD-1",
        "duplicate_of_source": "IFC-1",
    }]
    assert len(r.objects) == 3


def test_provenance_is_revision_and_source_safe():
    r = registry()
    p = r.provenance("C1")
    assert p["source_id"] == "IFC-1"
    assert p["revision"] == "1"
    assert p["format"] == "ifc"
    assert p["discipline"] == "structural"
    assert p["units"] == "m"


def test_2d_3d_linking_is_explicit():
    linked = registry().link_2d_3d([
        {"object_id": "C1", "quantity": 3},
        {"object_id": "MISSING", "quantity": 1},
    ])
    assert linked[0]["linked"] is True
    assert linked[0]["three_d"]["object_id"] == "C1"
    assert linked[1]["linked"] is False


def test_deterministic_bim_exchange_json(tmp_path):
    r = registry()
    a = export_registry_json(r, tmp_path / "a.json")
    b = export_registry_json(r, tmp_path / "b.json")
    assert a.read_bytes() == b.read_bytes()
    data = json.loads(a.read_text(encoding="utf-8"))
    assert len(data["sources"]) == 2
    assert len(data["objects"]) == 3


def test_ifc_export_never_fakes_output_without_writer(tmp_path):
    r = registry()
    try:
        import ifcopenshell  # noqa: F401
    except ImportError:
        with pytest.raises(RuntimeError):
            export_ifc(r, tmp_path / "out.ifc")
    else:
        out = export_ifc(r, tmp_path / "out.ifc")
        assert out.exists()
        assert out.stat().st_size > 0
