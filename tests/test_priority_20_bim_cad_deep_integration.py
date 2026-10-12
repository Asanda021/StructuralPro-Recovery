"""Regression coverage for Priority 20 — BIM/CAD deep integration."""
import pytest
from core.drawings.model_registry import ModelRegistry, ModelSource, ModelObject


def test_registry_rejects_duplicate_sources_and_objects():
    source = ModelSource("IFC-R1", "model.ifc", "ifc", revision="1")
    registry = ModelRegistry(sources=[source])
    with pytest.raises(ValueError):
        registry.register_source(source)
    obj = ModelObject("IFC-R1", "G1", "IfcWall", quantities={"Length": 5})
    registry.add_object(obj)
    with pytest.raises(ValueError):
        registry.add_object(obj)


def test_registry_inventory_mapping_and_confirmation_gate():
    registry = ModelRegistry(
        sources=[ModelSource("IFC-R1", "model.ifc", "ifc", revision="1")],
        objects=[
            ModelObject("IFC-R1", "W1", "IfcWall", name="Wall A", level="L1", quantities={"Length": 5}),
            ModelObject("IFC-R1", "D1", "IfcDoor", name="Door A", level="L1", quantities={"Count": 1}),
        ],
    )
    assert registry.source_inventory() == {
        "sources": 1, "objects": 2, "by_format": {"ifc": 1}, "by_revision": {"1": 1}
    }
    preview = registry.to_takeoff_rows(mapping={"IfcWall": "W-01"})
    assert preview["rows"][0]["price_code"] == "W-01"
    assert preview["rows"][0]["mapping_status"] == "mapped"
    assert "D1" in preview["unmapped"]
    strict = registry.to_takeoff_rows(mapping={"IfcWall": "W-01"}, require_mapping=True)
    assert len(strict["rows"]) == 1
    assert strict["rows"][0]["needs_confirmation"] is False


def test_revision_diff_reports_added_removed_changed_objects():
    registry = ModelRegistry(
        sources=[
            ModelSource("OLD", "old.ifc", "ifc", revision="1"),
            ModelSource("NEW", "new.ifc", "ifc", revision="2"),
        ],
        objects=[
            ModelObject("OLD", "A", "IfcWall", name="Old", quantities={"Length": 5}),
            ModelObject("OLD", "B", "IfcDoor", name="Removed", quantities={"Count": 1}),
            ModelObject("NEW", "A", "IfcWall", name="Changed", quantities={"Length": 7}),
            ModelObject("NEW", "C", "IfcColumn", name="Added", quantities={"Volume": 2}),
        ],
    )
    diff = registry.revision_diff("1", "2")
    assert diff["added"] == [{"object_id": "C", "object_type": "IfcColumn"}]
    assert diff["removed"] == [{"object_id": "B", "object_type": "IfcDoor"}]
    assert diff["changed"] == [{"object_id": "A", "object_type": "IfcWall"}]


def test_registry_rejects_invalid_quantities_and_unknown_source():
    with pytest.raises(ValueError):
        ModelRegistry(
            sources=[ModelSource("S1", "x.ifc", "ifc")],
            objects=[ModelObject("S1", "A", "IfcWall", quantities={"Length": -1})],
        )
    with pytest.raises(ValueError):
        ModelRegistry(objects=[ModelObject("NO", "A", "IfcWall")])


def test_application_persists_model_registry_and_preview(tmp_path):
    from core.platform.application import StructuralProApp
    app = StructuralProApp(tmp_path)
    app.create_project("مدل آزمایشی", "P20")
    app.register_model_source(
        "P20", ModelSource("IFC-R1", "model.ifc", "ifc", revision="1", discipline="architecture")
    )
    app.add_model_object(
        "P20", ModelObject("IFC-R1", "W1", "IfcWall", name="دیوار", level="طبقه ۱",
                            quantities={"Length": 12})
    )
    app.add_model_object(
        "P20", ModelObject("IFC-R1", "C1", "IfcColumn", name="ستون", level="طبقه ۱",
                            quantities={"Volume": 3})
    )
    inventory = app.project_model_inventory("P20")
    assert inventory["sources"] == 1
    assert inventory["objects"] == 2
    preview = app.project_model_takeoff_preview("P20", mapping={"IfcWall": "W-01"})
    assert preview["rows"][0]["source"] == "model:IFC-R1:W1:Length"
    assert "C1" in preview["unmapped"]
    snap = app.project_model_snapshot("P20")
    assert len(snap["sources"]) == 1
    assert len(snap["objects"]) == 2


def test_fingerprint_is_deterministic(tmp_path):
    p = tmp_path / "model.ifc"
    p.write_bytes(b"StructuralPro")
    first = ModelRegistry.fingerprint(p)
    second = ModelRegistry.fingerprint(p)
    assert first == second
    assert len(first) == 64
