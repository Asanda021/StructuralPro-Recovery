"""Source-backed bounded IFC selection for P6 G2, with a complete ledger.

This test constructs explicit IFC4 geometry: not a customer model and not
proof of full-model 3D capacity. No quantity, price or SQLite changes.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

import pytest

from test_phase6_p2_benchmark_ifc100 import make_ifc_floors


def _fixture(tmp_path, *, add_unrepresented=False):
    import ifcopenshell
    path = tmp_path / "source-selection.ifc"
    make_ifc_floors(path, 5)
    if add_unrepresented:
        model = ifcopenshell.open(str(path))
        obj = model.create_entity(
            "IfcBuildingElementProxy", GlobalId=ifcopenshell.guid.new(),
            Name="UNREPRESENTED SOURCE ELEMENT",
        )
        assert obj.Representation is None
        model.write(str(path))
    m = ifcopenshell.open(str(path))
    represented = sorted(e.GlobalId for e in m.by_type("IfcElement")
                         if getattr(e, "Representation", None))
    unrepresented = sorted(e.GlobalId for e in m.by_type("IfcElement")
                           if getattr(e, "Representation", None) is None)
    return path, represented, unrepresented


def _contract(path, ids, *, cap=40_000):
    from core.bim.ifc import DeepIFCAdapter
    return DeepIFCAdapter().read_display_contract(
        path, revision="R-VERIFIED", selected_global_ids=ids,
        max_triangles=cap,
    )


def test_bounded_selection_keeps_all_unloaded_identities_and_real_geometry(tmp_path):
    from core.drawings.source_mesh3d import VerifiedScene3D
    path, ids, missing = _fixture(tmp_path)
    assert not missing and len(ids) == 20
    contract = _contract(path, ids[:3])
    cat = contract["display_catalog"]
    assert cat["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert cat["revision"] == "R-VERIFIED"
    assert cat["source_member_count"] == 20
    assert cat["counts"] == {
        "displayed": 3, "not_loaded": 17, "without_geometry": 0,
    }
    assert cat["complete_model_displayed"] is False
    assert len(cat["members"]) == 20
    assert {r["global_id"] for r in cat["members"]} == set(ids)
    assert {r["global_id"] for r in contract["elements"]} == set(ids[:3])
    assert contract["quantity_authority"] is False
    scene = VerifiedScene3D(contract)
    assert {m.global_id for m in scene.meshes} == set(ids[:3])
    assert scene.quantity_authority is False
    assert len(scene.visible_faces(1000, 700)) == 36


def test_source_without_geometry_is_explicit_and_never_fabricated(tmp_path):
    from core.drawings.source_mesh3d import VerifiedScene3D
    path, ids, missing = _fixture(tmp_path, add_unrepresented=True)
    assert len(missing) == 1
    contract = _contract(path, ids[:2] + missing)
    cat = contract["display_catalog"]
    assert cat["counts"] == {
        "displayed": 2, "not_loaded": 18, "without_geometry": 1,
    }
    assert next(r["status"] for r in cat["members"]
                if r["global_id"] == missing[0]) == "without_geometry"
    assert missing[0] not in {r["global_id"] for r in contract["elements"]}
    scene = VerifiedScene3D(contract)
    assert len(scene.meshes) == 2
    assert missing[0] not in {mesh.global_id for mesh in scene.meshes}


def test_selection_unknown_duplicates_or_oversized_requests_fail_closed(tmp_path):
    path, ids, _ = _fixture(tmp_path)
    for chosen in ([], [ids[0], ids[0]], ["NOT_A_SOURCE_ID"], [" "]):
        with pytest.raises(ValueError):
            _contract(path, chosen)
    with pytest.raises(ValueError, match="ظرفیت"):
        _contract(path, ids[:2], cap=40_001)
    with pytest.raises(ValueError, match="ظرفیت"):
        _contract(path, ids[:1], cap=11)


def test_partial_contract_tampering_and_changed_ifc_are_rejected(tmp_path):
    from core.drawings.source_mesh3d import VerifiedScene3D
    path, ids, _ = _fixture(tmp_path)
    contract = _contract(path, ids[:2])
    altered = deepcopy(contract)
    altered["display_catalog"]["counts"]["not_loaded"] = 0
    with pytest.raises(ValueError, match="وضعیت"):
        VerifiedScene3D(altered)
    altered = deepcopy(contract)
    altered["display_catalog"]["members"][0]["status"] = "without_geometry"
    with pytest.raises(ValueError, match="وضعیت"):
        VerifiedScene3D(altered)
    altered = deepcopy(contract)
    altered["display_catalog"]["revision"] = "R-OTHER"
    with pytest.raises(ValueError, match="نسخه"):
        VerifiedScene3D(altered)
    scene = VerifiedScene3D(contract)
    path.write_bytes(path.read_bytes() + b"\n/* change after checked display */")
    with pytest.raises(ValueError, match="تغییر"):
        scene.validate_source()


def test_native_qt_provenance_shows_not_loaded_and_without_geometry(tmp_path):
    from PySide6.QtWidgets import QApplication, QLabel
    from app.ifc_3d_viewport import IFC3DDialog
    from core.drawings.source_mesh3d import VerifiedScene3D
    path, ids, missing = _fixture(tmp_path, add_unrepresented=True)
    app = QApplication.instance() or QApplication([])
    dialog = IFC3DDialog(VerifiedScene3D(_contract(path, ids[:2] + missing)))
    try:
        dialog.show()
        app.processEvents()
        status = dialog.findChild(QLabel, "IFC3DProvenance")
        assert status is not None
        assert "کل اعضای منبع: 21" in status.text()
        assert "بارگذاری‌نشده: 18" in status.text()
        assert "فاقد هندسه در منبع: 1" in status.text()
        assert len(dialog.canvas._faces()) == 24
        with pytest.raises(ValueError, match="موجود نیست"):
            dialog.canvas.choose_member(missing[0])
        assert dialog.canvas.selected_id is None
    finally:
        dialog.close()
        app.processEvents()
