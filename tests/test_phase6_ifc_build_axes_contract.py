"""IFC4 IfcBuildAxes semantic regression, not independent model acceptance.
Normative reference: buildingSMART IFC4 ADD2 IfcAxis2Placement3D/IfcBuildAxes.
A regression rejecting valid nonorthogonal RefDirection fails these tests.
"""
from decimal import Decimal
import pytest
from test_phase6_g2_axis_orthogonality import _source_with_axis_error

@pytest.mark.parametrize('ratio', [1e-9, 0.1, 5.0])
def test_ifc_refdirection_is_projected_not_rejected(tmp_path, ratio):
    from core.drawings.bim_adapter import BIMAdapter
    path, gid = _source_with_axis_error(tmp_path, ratio)
    document = BIMAdapter().read_document(path, revision='BUILD-AXES')
    row = next(x for x in document['elements'] if x['global_id'] == gid)
    matrix = row['placement_matrix_si']
    # Z=(0,0,1), approximate X=(1,0,ratio): exact derived basis is identity.
    for i in range(3):
        for j in range(3):
            assert abs(Decimal(str(matrix[i][j])) - int(i == j)) < Decimal('1e-24')
    assert document['map_conversion_supported'] is False


def test_ifc_projection_then_parent_composition_has_hand_calculated_rotation(tmp_path):
    import ifcopenshell
    from core.drawings.bim_adapter import BIMAdapter
    path, gid = _source_with_axis_error(tmp_path, 0.0)
    model = ifcopenshell.open(str(path))
    beam = model.by_guid(gid)
    beam.ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = (3., 4., 5.)
    # Identity parent makes the independent exact local basis visible in world axes.
    beam.ObjectPlacement.PlacementRelTo = None
    model.write(str(path))
    row = next(x for x in BIMAdapter().read_document(path, revision='BUILD-AXES')['elements'] if x['global_id'] == gid)
    expected = ((Decimal('.6'), Decimal('-.8'), Decimal(0)),
                (Decimal('.8'), Decimal('.6'), Decimal(0)),
                (Decimal(0), Decimal(0), Decimal(1)))
    for i in range(3):
        for j in range(3):
            assert abs(Decimal(str(row['placement_matrix_si'][i][j])) - expected[i][j]) < Decimal('1e-24')

@pytest.mark.parametrize('x', [(0.,0.,0.), (0.,0.,1.), (0.,0.,-1.), (1e-14,0.,1.)])
def test_ifc_undefined_or_ill_conditioned_reference_direction_is_rejected(tmp_path, x):
    import ifcopenshell
    from core.drawings.bim_adapter import BIMAdapter
    path, gid = _source_with_axis_error(tmp_path, 0.0)
    model = ifcopenshell.open(str(path))
    model.by_guid(gid).ObjectPlacement.RelativePlacement.RefDirection.DirectionRatios = x
    model.write(str(path))
    with pytest.raises(ValueError):
        BIMAdapter().read_document(path, revision='UNDEFINED-AXES')
