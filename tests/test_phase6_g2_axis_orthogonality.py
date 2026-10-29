"""Phase-6 G2: bounded IFC4 placement-roundoff acceptance, not a geo fix.

Geometry is generated in this test as a synthetic IFC4 file; the independent
RWTH published IFC is checked separately by the source-pinned diagnostic.
The declared map conversion remains unsupported. No QTO rights are granted.
"""
from __future__ import annotations

from decimal import Decimal
from hashlib import sha256

import pytest

from test_phase6_p2_benchmark_ifc100 import make_ifc_floors


def _source_with_axis_error(tmp_path, ratio: float):
    import ifcopenshell

    path = tmp_path / ("axis-%s.ifc" % str(ratio).replace("-", "n"))
    make_ifc_floors(path, 1)
    model = ifcopenshell.open(str(path))
    beam = model.by_type("IfcBeam")[0]
    relative = beam.ObjectPlacement.RelativePlacement
    relative.Axis = model.create_entity(
        "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
    )
    relative.RefDirection = model.create_entity(
        "IfcDirection", DirectionRatios=(1.0, 0.0, float(ratio))
    )
    model.write(str(path))
    return path, beam.GlobalId


@pytest.mark.parametrize("ratio", [0.0, 1e-25, 1e-13])
def test_ifc_placement_accepts_only_bounded_axis_roundoff_and_orthogonalizes(tmp_path, ratio):
    from core.drawings.bim_adapter import BIMAdapter
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D

    path, gid = _source_with_axis_error(tmp_path, ratio)
    document = BIMAdapter().read_document(path, revision="P6-G2-AXIS")
    assert document["source_sha256"] == sha256(path.read_bytes()).hexdigest()
    assert document["map_conversion_supported"] is False
    element = next(row for row in document["elements"] if row["global_id"] == gid)
    matrix = [[Decimal(str(v)) for v in row] for row in element["placement_matrix_si"]]
    for col in range(3):
        norm = sum(matrix[row][col] ** 2 for row in range(3))
        assert abs(norm - 1) < Decimal("1e-24")
        for other in range(col + 1, 3):
            dot = sum(matrix[row][col] * matrix[row][other] for row in range(3))
            assert abs(dot) < Decimal("1e-24")
    contract = DeepIFCAdapter().read_display_contract(path, revision="P6-G2-AXIS")
    assert contract["quantity_authority"] is False
    assert contract["source_sha256"] == sha256(path.read_bytes()).hexdigest()
    scene = VerifiedScene3D(contract)
    assert gid in {mesh.global_id for mesh in scene.meshes}
    assert scene.omitted_ids == ()


@pytest.mark.parametrize("ratio", [1e-9, 0.1])
def test_ifc_placement_rejects_material_skew_instead_of_guessing_transform(tmp_path, ratio):
    from core.drawings.bim_adapter import BIMAdapter
    from core.bim.ifc import DeepIFCAdapter

    path, _ = _source_with_axis_error(tmp_path, ratio)
    with pytest.raises(ValueError, match="متعامد"):
        BIMAdapter().read_document(path, revision="P6-G2-SKEW")
    with pytest.raises(ValueError, match="متعامد"):
        DeepIFCAdapter().read_display_contract(path, revision="P6-G2-SKEW")


def test_ifc_placement_rejects_collinear_axes_and_preserves_display_capacity_guard(tmp_path):
    from core.drawings.bim_adapter import BIMAdapter
    from core.bim.ifc import DeepIFCAdapter

    path, _ = _source_with_axis_error(tmp_path, 0.0)
    import ifcopenshell
    model = ifcopenshell.open(str(path))
    beam = model.by_type("IfcBeam")[0]
    beam.ObjectPlacement.RelativePlacement.RefDirection = model.create_entity(
        "IfcDirection", DirectionRatios=(0.0, 0.0, 1.0)
    )
    model.write(str(path))
    with pytest.raises(ValueError, match="متعامد"):
        BIMAdapter().read_document(path, revision="P6-G2-COLLINEAR")
    good, _ = _source_with_axis_error(tmp_path, 1e-13)
    with pytest.raises(ValueError, match="ظرفیت"):
        DeepIFCAdapter().read_display_contract(
            good, revision="P6-G2-CAPACITY", max_triangles=11
        )
