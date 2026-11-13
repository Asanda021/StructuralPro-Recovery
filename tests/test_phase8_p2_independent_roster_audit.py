"""Public synthetic tests only. No private CAD inputs, no quantity approval."""
from types import SimpleNamespace
from pathlib import Path
import hashlib
import pytest
from tools.audit_phase8_p2_real_independent_sources import audit, classify_geometry_pair

def source(kind, **attrs):
    return SimpleNamespace(dxftype=kind,dxf=attrs)

def target(kind, **attrs):
    return SimpleNamespace(dxftype=lambda: kind,dxf=SimpleNamespace(**attrs))

def test_line_3d_exact_and_z_mismatch():
    s=source('LINE',start=(1,2,3),end=(4,5,6))
    assert not classify_geometry_pair(s,target('LINE',layer='A',start=(1,2,3),end=(4,5,6)),'A')
    assert classify_geometry_pair(s,target('LINE',layer='A',start=(1,2,0),end=(4,5,6)),'A')==['LINE_3D_COORD_CHANGED']

def test_solid_xy_same_z_was_dropped():
    verts=[(1,2,-5),(3,4,-5),(5,6,-5),(5,6,-5)]
    s=source('SOLID',points=verts)
    good=target('SOLID',layer='A',**{'vtx'+str(i):v for i,v in enumerate(verts)})
    bad=target('SOLID',layer='A',**{'vtx'+str(i):(v[0],v[1],0.0) for i,v in enumerate(verts)})
    assert classify_geometry_pair(s,good,'A')==[]
    assert classify_geometry_pair(s,bad,'A')==['SOLID_Z_CHANGED']

def test_insert_remapped_name_never_silently_equivalent():
    s=source('INSERT',name='*X15',insert=(0,0,0),rotation=0,xscale=1.7,yscale=1.7,zscale=1.7)
    t=target('INSERT',layer='X',name='*X21',insert=(0,0,0),rotation=0,xscale=1.7,yscale=1.7,zscale=1.7)
    assert classify_geometry_pair(s,t,'X')==['INSERT_BLOCK_NAME_CHANGED']

def test_arc_angle_changed():
    s=source('ARC',center=(0,0,0),radius=2,start_angle=10,end_angle=70)
    t=target('ARC',layer='X',center=(0,0,0),radius=2,start_angle=11,end_angle=70)
    assert classify_geometry_pair(s,t,'X')==['ARC_ANGLE_CHANGED']

def test_circle_layer_changed():
    s=source('CIRCLE',center=(0,0,0),radius=2)
    t=target('CIRCLE',layer='B',center=(0,0,0),radius=2)
    assert classify_geometry_pair(s,t,'A')==['LAYER_CHANGED']

def test_expected_source_sha_is_mandatory_and_correct(tmp_path):
    original=tmp_path/'x.dwg';original.write_bytes(b'AC1018_synthetic_not_a_real_dwg')
    dx=tmp_path/'x.dxf';dx.write_bytes(b'fake_dxf')
    with pytest.raises(ValueError,match='SHA mismatch'):
        audit(original,dx,'0'*64)
    with pytest.raises(ValueError,match='64-digit'):
        audit(original,dx,'BAD')

def test_missing_source_rejected(tmp_path):
    with pytest.raises(ValueError,match='unavailable'):
        audit(tmp_path/'missing.dwg',tmp_path/'missing.dxf','0'*64)

def test_solid_vertex_z_preserved_in_legacy_elevation_is_flagged_as_compatibility_risk():
    verts=[(1,2,-5),(3,4,-5),(5,6,-5),(5,6,-5)]
    original=source('SOLID',points=verts)
    legacy=target('SOLID',layer='A',elevation=-5,**{'vtx'+str(i):(v[0],v[1],0.0) for i,v in enumerate(verts)})
    assert classify_geometry_pair(original,legacy,'A') == ['SOLID_Z_RELOCATED_TO_LEGACY_ELEVATION']


def test_solid_incorrect_legacy_elevation_remains_actual_z_discrepancy():
    verts=[(1,2,-5),(3,4,-5),(5,6,-5),(5,6,-5)]
    original=source('SOLID',points=verts)
    wrong=target('SOLID',layer='A',elevation=-4,**{'vtx'+str(i):(v[0],v[1],0.0) for i,v in enumerate(verts)})
    assert classify_geometry_pair(original,wrong,'A') == ['SOLID_Z_CHANGED']

@pytest.mark.parametrize(
    ('source_owner', 'expected'),
    [(2, {}), (64, {'NATIVE_OWNER_OUTSIDE_MODELSPACE': 1}),
     (None, {'NATIVE_OWNER_UNVERIFIED': 1})],
)
def test_shared_line_geometry_does_not_mask_modelspace_ownership(
    tmp_path, monkeypatch, source_owner, expected,
):
    import sys

    import ezdxf

    from core.drawings import dwg_native_roster_crosscheck as roster

    dwg = tmp_path / 'public.dwg'
    dwg.write_bytes(b'AC1018 synthetic test')
    dxf = tmp_path / 'public.dxf'
    doc = ezdxf.new()
    line = doc.modelspace().add_line((1, 2, 3), (4, 5, 6))
    doc.saveas(dxf)
    source_line = source(
        'LINE', start=(1, 2, 3), end=(4, 5, 6),
        layer_handle=3, owner_handle=source_owner,
    )
    source_line.handle = int(line.dxf.handle, 16)
    native = SimpleNamespace(
        version='AC1018', units='unitless',
        layers=[SimpleNamespace(handle=3, name='0')],
        modelspace=lambda: SimpleNamespace(iter_entities=lambda: iter([source_line])),
        layouts=lambda: {'Model': {'block_record_handle': 2}},
    )
    monkeypatch.setitem(sys.modules, 'ezdwg', SimpleNamespace(read=lambda _: native))
    monkeypatch.setattr(roster.metadata, 'version', lambda _: roster.PINNED_NATIVE_VERSION)

    receipt = roster.audit_native_to_dxf(
        dwg, dxf, expected_dwg_sha256=hashlib.sha256(dwg.read_bytes()).hexdigest(),
        expected_dxf_sha256=hashlib.sha256(dxf.read_bytes()).hexdigest(),
    )

    assert receipt['shared_line_count'] == 1
    assert receipt['shared_line_geometry_layer_mismatch_count'] == 0
    assert receipt['shared_line_modelspace_ownership_issues'] == expected
    assert receipt['financial_geometry_approved'] is False
    assert receipt['approved_quantities'] == 0
