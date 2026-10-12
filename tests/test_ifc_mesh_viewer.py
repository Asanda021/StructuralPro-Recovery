"""Real IFC tessellation and existing Qt viewer integration, without invented takeoff."""
import hashlib
import pytest

ifc = pytest.importorskip("ifcopenshell")
from core.bim.ifc import DeepIFCAdapter
from core.drawings.viewer_model import DrawingViewerModel


def write_model(path, *, millimetres=False, empty=False):
    model = ifc.file(schema="IFC4")
    project = model.create_entity("IfcProject", GlobalId=ifc.guid.new())
    unit = model.create_entity("IfcSIUnit", UnitType="LENGTHUNIT", Name="METRE",
                               Prefix="MILLI" if millimetres else None)
    project.UnitsInContext = model.create_entity("IfcUnitAssignment", Units=[unit])
    origin = model.create_entity("IfcCartesianPoint", Coordinates=(0., 0., 0.))
    axes = model.create_entity("IfcAxis2Placement3D", Location=origin)
    context = model.create_entity("IfcGeometricRepresentationContext", ContextType="Model",
                                  CoordinateSpaceDimension=3, Precision=1e-5, WorldCoordinateSystem=axes)
    project.RepresentationContexts = [context]
    wall = model.create_entity("IfcWall", GlobalId=ifc.guid.new(), Name="دیوار نمونه")
    if not empty:
        factor = 1000. if millimetres else 1.
        profile = model.create_entity("IfcRectangleProfileDef", ProfileType="AREA",
                                      XDim=4.*factor, YDim=.2*factor)
        direction = model.create_entity("IfcDirection", DirectionRatios=(0., 0., 1.))
        solid = model.create_entity("IfcExtrudedAreaSolid", SweptArea=profile,
                                    Position=axes, ExtrudedDirection=direction, Depth=3.*factor)
        representation = model.create_entity("IfcShapeRepresentation", ContextOfItems=context,
                                             RepresentationIdentifier="Body", RepresentationType="SweptSolid", Items=[solid])
        wall.Representation = model.create_entity("IfcProductDefinitionShape", Representations=[representation])
        location = model.create_entity("IfcCartesianPoint", Coordinates=(10.*factor, 0., 0.))
        wall.ObjectPlacement = model.create_entity("IfcLocalPlacement", RelativePlacement=
            model.create_entity("IfcAxis2Placement3D", Location=location))
    model.write(str(path))
    return model, wall


@pytest.mark.parametrize("millimetres", [False, True])
def test_real_mesh_world_placement_units_and_source_hash(tmp_path, millimetres):
    path = tmp_path / "wall.ifc"
    _, wall = write_model(path, millimetres=millimetres)
    viewer = DrawingViewerModel(path)
    doc = viewer.ifc_document
    assert viewer.kind == "ifc" and viewer.page_count == 1
    assert doc.source_sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
    mesh, = doc.meshes
    assert mesh.global_id == wall.GlobalId and mesh.name == "دیوار نمونه"
    assert len(mesh.triangles) == 12
    xs = [v[0] for v in mesh.vertices]
    zs = [v[2] for v in mesh.vertices]
    assert min(xs) == pytest.approx(8) and max(xs) == pytest.approx(12)
    assert max(zs) == pytest.approx(3)
    assert not hasattr(mesh, "quantity")


def test_failed_ifc_import_preserves_current_viewer(tmp_path):
    path = tmp_path / "good.ifc"
    write_model(path)
    viewer = DrawingViewerModel(path)
    old = viewer.ifc_document
    empty = tmp_path / "empty.ifc"
    write_model(empty, empty=True)
    with pytest.raises(ValueError, match="هندسه"):
        viewer.open(empty)
    assert viewer.path == path and viewer.ifc_document is old
    with pytest.raises(ValueError, match="ظرفیت"):
        DeepIFCAdapter().read_display_meshes(path, max_triangles=1)


def test_duplicate_ifc_identity_fails_closed(tmp_path):
    path = tmp_path / "duplicate.ifc"
    model, wall = write_model(path)
    model.create_entity("IfcWall", GlobalId=wall.GlobalId, Representation=wall.Representation)
    model.write(str(path))
    with pytest.raises(ValueError, match="تکراری"):
        DrawingViewerModel(path)


def test_missing_unit_fails_closed(tmp_path):
    path = tmp_path / "unitless.ifc"
    model, _ = write_model(path)
    model.by_type("IfcProject")[0].UnitsInContext = None
    model.write(str(path))
    with pytest.raises(ValueError, match="واحد"):
        DrawingViewerModel(path)


def test_real_qt_viewer_draws_mesh_and_blocks_projected_measurement(tmp_path, monkeypatch):
    try:
        from PySide6.QtWidgets import QApplication
        from app.graphical_takeoff import GraphicalTakeoffDialog
    except (ImportError, OSError):
        pytest.skip("Native Qt graphics libraries unavailable")
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "wall.ifc"
    write_model(path)
    dialog = GraphicalTakeoffDialog()
    dialog.open_drawing(str(path))
    assert len(dialog.canvas.scene.items()) == 12
    assert dialog.canvas.read_only_model and dialog.canvas.mode == "pan"
    assert not dialog.calibrate.isEnabled() and not dialog.finish.isEnabled()
    dialog.canvas.set_mode("length")
    assert dialog.canvas.mode == "pan"
    dialog.register_selected_region()
    dialog.calibrate_scale()
    dialog.export_takeoff_for_boq()
    dialog.commit_selected_to_boq()
    dialog.canvas.finish()
    assert dialog.session.items == [] and dialog.session.calibration is None
    assert "ایزومتریک" in dialog.status.text()
    dialog.canvas.set_mode("zoom_window")
    assert dialog.canvas.mode == "zoom_window"
    dialog.redraw_current_page()
    assert len(dialog.canvas.scene.items()) == 12
    import fitz
    pdf = tmp_path / "plan.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf)
    document.close()
    dialog.open_drawing(str(pdf))
    assert not dialog.canvas.read_only_model
    assert dialog.canvas.mode == "length" and dialog.calibrate.isEnabled()
    assert dialog.export_boq.isEnabled() and dialog.viewer.ifc_document is None
    dialog.close()
