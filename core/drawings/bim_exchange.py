"""BIM exchange helpers for StructuralPro.

The core registry stays dependency-light. IFC parsing/export is delegated to
IfcOpenShell when installed; normalized registry exchange is always available.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from core.drawings.bim_adapter import BIMAdapter
from core.drawings.model_registry import ModelRegistry, ModelObject


def import_ifc(path: str | Path):
    """Import IFC objects through the optional IfcOpenShell adapter."""
    return BIMAdapter().read_ifc(path)


def registry_from_ifc(path: str | Path, *, source_id: str, revision: str = "1",
                      discipline: str = "", units: str = "") -> ModelRegistry:
    from core.drawings.model_registry import ModelSource
    objects = import_ifc(path)
    source = ModelSource(source_id, str(path), "ifc", revision=revision,
                         discipline=discipline, units=units)
    return ModelRegistry(
        sources=[source],
        objects=[
            ModelObject(
                source_id=source_id,
                object_id=o.global_id,
                object_type=o.ifc_type,
                name=o.name,
                properties=o.properties,
            )
            for o in objects
        ],
    )


def export_registry_json(registry: ModelRegistry, path: str | Path) -> Path:
    """Write a deterministic, lossless normalized BIM exchange manifest."""
    target = Path(path)
    target.write_text(
        json.dumps(registry.export_dict(), ensure_ascii=False, sort_keys=True, indent=2),
        encoding="utf-8",
    )
    return target


def export_ifc(registry: ModelRegistry, path: str | Path) -> Path:
    """Export registry objects to IFC using optional IfcOpenShell.

    No fallback silently writes a fake IFC. Callers receive an explicit error
    when the optional IFC writer is unavailable.
    """
    try:
        import ifcopenshell
        import ifcopenshell.api
    except ImportError as exc:
        raise RuntimeError(
            "Install ifcopenshell to export IFC; JSON exchange remains available without it."
        ) from exc

    target = Path(path)
    model = ifcopenshell.file(schema="IFC4")
    project = ifcopenshell.api.run("root.create_entity", model,
                                   ifc_class="IfcProject", name="StructuralPro")
    site = ifcopenshell.api.run("root.create_entity", model,
                                ifc_class="IfcSite", name="Site")
    building = ifcopenshell.api.run("root.create_entity", model,
                                    ifc_class="IfcBuilding", name="Building")
    storey_cache = {}
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=project,
                         products=[site])
    ifcopenshell.api.run("aggregate.assign_object", model, relating_object=site,
                         products=[building])

    for obj in registry.objects:
        level = obj.level or "Level 1"
        storey = storey_cache.get(level)
        if storey is None:
            storey = ifcopenshell.api.run("root.create_entity", model,
                                          ifc_class="IfcBuildingStorey", name=level)
            ifcopenshell.api.run("aggregate.assign_object", model,
                                 relating_object=building, products=[storey])
            storey_cache[level] = storey
        product = ifcopenshell.api.run(
            "root.create_entity", model,
            ifc_class="IfcBuildingElementProxy",
            name=obj.name or obj.object_type,
        )
        product.ObjectType = obj.object_type
        ifcopenshell.api.run("spatial.assign_container", model,
                             relating_structure=storey, products=[product])
    model.write(str(target))
    return target
