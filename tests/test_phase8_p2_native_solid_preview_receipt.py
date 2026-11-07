"""The actual native read-only DWG preview must expose native Z, not claim CAD-3D UI approval."""
import pytest
from core.drawings.native_dwg_preview import _native_display_geometry


def test_native_source_solid_preserves_xyz_in_readonly_preview():
    points=[(0,0,-5),(1,0,-5),(1,1,-5),(0,1,-5)]
    result=_native_display_geometry('SOLID',{'points':points,'extrusion':(0,0,1)})
    assert result['source_vertices_3d_preserved'] is True
    assert result['native_source_vertices_3d']==[list(p) for p in points]
    assert result['cad_3d_gui_render_verified'] is False
    assert result['source_preview_geometry_status']=='NATIVE_XYZ_RECEIPT_2D_VIEW_ONLY'
    assert result['financial_quantity_approved'] is False


def test_native_source_solid_rejects_unverifiable_extrusion():
    with pytest.raises(ValueError,match='Nonstandard'):
        _native_display_geometry('SOLID',{'points':[(0,0,1),(1,0,1),(1,1,1)],'extrusion':(1,0,0)})