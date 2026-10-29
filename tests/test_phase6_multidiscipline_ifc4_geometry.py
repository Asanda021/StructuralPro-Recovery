"""Real IFC4 multi-discipline native-geometry viewer acceptance.

All geometry in these fixtures is constructed with explicit, deterministic
IFC placements and extrusions. It is NOT a real client's building, and no
quantities/prices are generated from display tessellation.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from test_phase6_p2_benchmark_ifc100 import make_ifc_floors

# IFC4 IfcElement only, with type-appropriate display examples. Geometry
# is explicit. An IfcSpace with geometry is included separately as context.
EXTRA_ELEMENT_TYPES = (
    "IfcFooting", "IfcDoor", "IfcWindow", "IfcCovering",
    "IfcStair", "IfcCurtainWall", "IfcPipeSegment", "IfcFlowTerminal",
    "IfcGeographicElement", "IfcBuildingElementProxy",
)
BASE_TYPES = ("IfcBeam", "IfcWall", "IfcSlab", "IfcDuctSegment")


def mixed_ifc(path: Path) -> dict[str, str]:
    import ifcopenshell as ifc

    make_ifc_floors(path, 1)
    model = ifc.open(str(path))
    ctx = model.by_type("IfcGeometricRepresentationContext")[0]
    floor = model.by_type("IfcBuildingStorey")[0]
    originals = {obj.is_a(): obj.GlobalId for obj in model.by_type("IfcElement")}
    assert set(originals) == set(BASE_TYPES)
    result = dict(originals)

    def axes(x=0.0, y=0.0, z=0.0):
        return model.create_entity(
            "IfcAxis2Placement3D",
            Location=model.create_entity(
                "IfcCartesianPoint", Coordinates=(float(x),float(y),float(z))
            ),
        )

    for ordinal, kind in enumerate(EXTRA_ELEMENT_TYPES + ("IfcSpace",), start=4):
        obj = model.create_entity(
            kind, GlobalId=ifc.guid.new(), Name=f"EXPLICIT QA {kind}",
            ObjectPlacement=model.create_entity(
                "IfcLocalPlacement", PlacementRelTo=floor.ObjectPlacement,
                RelativePlacement=axes(ordinal * 4.5, 0, 0),
            ),
        )
        profile = model.create_entity(
            "IfcRectangleProfileDef", ProfileType="AREA",
            XDim=1.5, YDim=0.4,
        )
        solid = model.create_entity(
            "IfcExtrudedAreaSolid",
            SweptArea=profile, Position=axes(),
            ExtrudedDirection=model.create_entity(
                "IfcDirection", DirectionRatios=(0.,0.,1.)
            ), Depth=2.0,
        )
        shape = model.create_entity(
            "IfcShapeRepresentation", ContextOfItems=ctx,
            RepresentationIdentifier="Body",
            RepresentationType="SweptSolid", Items=[solid],
        )
        obj.Representation = model.create_entity(
            "IfcProductDefinitionShape", Representations=[shape]
        )
        if kind == "IfcSpace":
            # Spatial room context has real tessellated geometry but is NOT an
            # IfcElement, and must not poison the verified-element contract.
            model.create_entity(
                "IfcRelAggregates", GlobalId=ifc.guid.new(),
                RelatingObject=floor, RelatedObjects=[obj],
            )
        else:
            model.create_entity(
                "IfcRelContainedInSpatialStructure", GlobalId=ifc.guid.new(),
                RelatingStructure=floor, RelatedElements=[obj],
            )
            result[kind] = obj.GlobalId
    model.write(str(path))
    return result


def test_actual_ifc4_mixed_element_geometry_accepts_spatial_context_without_faking_identity(tmp_path):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D

    path = tmp_path / "real-ifc4-element-and-spatial-geometry.ifc"
    expected = mixed_ifc(path)
    contract = DeepIFCAdapter().read_display_contract(path, revision="R1")
    assert contract["quantity_authority"] is False
    assert contract["omitted_ids"] == [], "No real contracted element may vanish"
    actual = {e["ifc_type"]:e["global_id"] for e in contract["elements"]}
    assert actual == expected, "Every confirmed IfcElement must be retained"
    assert "IfcSpace" not in actual, "IfcSpace is context, not an IfcElement"
    assert all(e["storey_id"] for e in contract["elements"])
    scene = VerifiedScene3D(contract)
    assert {m.global_id for m in scene.meshes} == set(expected.values())
    assert len(scene.storeys) == 1
    assert scene.quantity_authority is False
    assert scene.source_sha256 == contract["source_sha256"]
    assert scene.revision == "R1"


def test_native_qt_can_filter_and_pick_real_mixed_ifc4_without_creating_boq(tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    from app.ifc_3d_viewport import IFC3DDialog

    path = tmp_path / "real-ifc4-mixed-ui.ifc"
    expected = mixed_ifc(path)
    scene = VerifiedScene3D(
        DeepIFCAdapter().read_display_contract(path,revision="R1")
    )
    qt = QApplication.instance() or QApplication([])
    dlg = IFC3DDialog(scene)
    try:
        dlg.show()
        qt.processEvents()
        assert dlg.type_filter.count() == len(expected) + 1
        assert len({m.ifc_type for m in scene.meshes}) == len(expected)
        # Type selection physically filters renderable source-backed faces,
        # including architecture, systems, coverings and site elements.
        for kind, gid in expected.items():
            index = dlg.type_filter.findData(kind)
            assert index > 0, kind
            dlg.type_filter.setCurrentIndex(index)
            faces = dlg.canvas._faces()
            assert faces, kind
            assert {f.global_id for f in faces} == {gid}
            face = faces[len(faces)//2]
            pos = [sum(v[axis] for v in face.points) / 3 for axis in (0,1)]
            assert scene.pick(*pos,dlg.canvas.width(),dlg.canvas.height(),
                              storey_id=dlg.canvas.storey_id) == gid
            dlg.canvas.choose_member(gid)
            assert dlg.canvas.selected_id == gid
        assert scene.quantity_authority is False
        assert dlg.save_view.isEnabled() is False
        assert not hasattr(dlg, "commit_boq")
        dlg.type_filter.setCurrentIndex(0)
        assert {f.global_id for f in dlg.canvas._faces()} == set(expected.values())
        assert scene.hidden_types == set()
    finally:
        dlg.close()
        qt.processEvents()


def test_multidiscipline_ifc4_modified_or_missing_source_is_rejected_without_partial_replacement(tmp_path):
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    path = tmp_path / "multidisciplinary-revision.ifc"
    expected = mixed_ifc(path)
    adapter = DeepIFCAdapter()
    contract = adapter.read_display_contract(path,revision="R1")
    scene = VerifiedScene3D(contract)
    previous_ids = {m.global_id for m in scene.meshes}
    assert previous_ids == set(expected.values())
    altered = deepcopy(contract)
    altered["revision"] = ""
    with pytest.raises(ValueError, match="نسخه"):
        VerifiedScene3D(altered)
    altered = deepcopy(contract)
    altered["quantity_authority"] = True
    with pytest.raises(ValueError, match="متره"):
        VerifiedScene3D(altered)
    path.write_bytes(path.read_bytes() + b"\n/* changed native IFC source */")
    with pytest.raises(ValueError, match="تغییر"):
        scene.validate_source()
    assert {m.global_id for m in scene.meshes} == previous_ids
    with pytest.raises(ValueError, match="تغییر"):
        VerifiedScene3D(contract)
