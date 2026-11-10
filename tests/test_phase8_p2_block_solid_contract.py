"""Synthetic-only negative tests; no private drawings and no quantity approval."""
from types import SimpleNamespace
import pytest
from core.drawings.dwg_insert_solid_contract import (
    _vec_equal, verify_insert_fields, verify_block_line, classify_solid_height,
    audit_insert_solid,
)


def native(kind,**data):
    return SimpleNamespace(dxftype=kind,dxf=data)


def converted(kind,**data):
    dxf=SimpleNamespace(**data)
    dxf.get=lambda key,default=None: data.get(key,default)
    return SimpleNamespace(dxftype=lambda: kind,dxf=dxf)


def test_insert_transform_and_layer_pass():
    a=native('INSERT',insert=(1,2,3),xscale=1.3,yscale=2,zscale=3,rotation=13,extrusion=(0,0,1))
    b=converted('INSERT',layer='L',insert=(1,2,3),xscale=1.3,yscale=2,zscale=3,rotation=13)
    assert verify_insert_fields(a,b,'L')==[]


@pytest.mark.parametrize('change, expected',[
    ({'layer':'OTHER'},'INSERT_LAYER_CHANGED'),
    ({'insert':(1,2,4)},'INSERT_POSITION_CHANGED'),
    ({'rotation':17},'INSERT_ROTATION_CHANGED'),
    ({'xscale':3},'INSERT_XSCALE_CHANGED'),
    ({'yscale':4},'INSERT_YSCALE_CHANGED'),
    ({'zscale':5},'INSERT_ZSCALE_CHANGED'),
    ({'extrusion':(0,1,0)},'INSERT_EXTRUSION_CHANGED'),
    ({'invisible':True},'INSERT_VISIBILITY_CHANGED'),
])
def test_insert_sensitive_changes(change,expected):
    a=native('INSERT',insert=(1,2,3),xscale=1.3,yscale=2,zscale=3,rotation=13)
    d=dict(layer='L',insert=(1,2,3),xscale=1.3,yscale=2,zscale=3,rotation=13)
    d.update(change)
    assert expected in verify_insert_fields(a,converted('INSERT',**d),'L')


def test_block_line_exact_match():
    a=native('LINE',start=(0,1,2),end=(4,5,6))
    b=converted('LINE',start=(0,1,2),end=(4,5,6),layer='A')
    assert verify_block_line(a,b,'A')==[]


@pytest.mark.parametrize('change, expected',[
    ({'start':(0,1,3)},'BLOCK_LINE_START_CHANGED'),
    ({'end':(4,5,0)},'BLOCK_LINE_END_CHANGED'),
    ({'layer':'B'},'BLOCK_LINE_LAYER_CHANGED'),
    ({'invisible':True},'BLOCK_LINE_VISIBILITY_CHANGED'),
])
def test_block_line_fail_closed(change,expected):
    a=native('LINE',start=(0,1,2),end=(4,5,6))
    d=dict(start=(0,1,2),end=(4,5,6),layer='A');d.update(change)
    assert expected in verify_block_line(a,converted('LINE',**d),'A')


def test_classify_solid_legacy_z_not_auto_approved():
    a=[(0,0,-5),(2,0,-5),(0,2,-5),(0,2,-5)]
    b=[(x,y,0) for x,y,z in a]
    assert classify_solid_height(a,b,-5,(0,0,1))=='SOLID_Z_IN_LEGACY_ELEVATION_VIEWER_UNVERIFIED'


@pytest.mark.parametrize('elevation, extrusion, expected',[
    (None,(0,0,1),'SOLID_Z_MISMATCH_NO_LEGACY_ELEVATION'),
    (-4,(0,0,1),'SOLID_Z_MISMATCH'),
    (-5,(0,1,0),'SOLID_NONSTANDARD_EXTRUSION_UNVERIFIED'),
])
def test_solid_unsafe_cases(elevation,extrusion,expected):
    a=[(0,0,-5),(2,0,-5),(0,2,-5),(0,2,-5)]
    b=[(x,y,0) for x,y,z in a]
    assert classify_solid_height(a,b,elevation,extrusion)==expected


def test_solid_3d_vertex_match_and_xy_mismatch():
    a=[(0,0,-5),(2,0,-5),(0,2,-5),(0,2,-5)]
    assert classify_solid_height(a,a,None,(0,0,1))=='SOLID_3D_VERTEX_MATCH'
    b=list(a);b[0]=(3,0,-5)
    assert classify_solid_height(a,b,None,(0,0,1))=='SOLID_XY_CHANGED'


def test_invalid_nonfinite_and_topology():
    assert not _vec_equal((1,2,float('nan')),(1,2,3))
    assert classify_solid_height([],[],None,(0,0,1))=='SOLID_TOPOLOGY_UNVERIFIED'


def test_wrong_sha_fails_before_decoder_access(tmp_path):
    dwg=tmp_path/'test.dwg';dxf=tmp_path/'test.dxf'
    dwg.write_bytes(b'AC1018'+b'fake'*50)
    dxf.write_bytes(b'0\nSECTION\n'*30)
    with pytest.raises(ValueError,match='mismatch'):
        audit_insert_solid(dwg,dxf,'0'*64,'0'*64)

def test_solid_changed_dxf_extrusion_is_never_a_vertex_match():
    vertices = [(0, 0, -5), (2, 0, -5), (0, 2, -5), (0, 2, -5)]
    assert classify_solid_height(
        vertices, vertices, None, (0, 0, 1), target_extrusion=(0, 0, 1)
    ) == 'SOLID_3D_VERTEX_MATCH'
    assert classify_solid_height(
        vertices, vertices, None, (0, 0, 1), target_extrusion=(0, 1, 0)
    ) == 'SOLID_EXTRUSION_CHANGED'


def test_solid_unreadable_target_extrusion_does_not_pass():
    vertices = [(0, 0, 0), (2, 0, 0), (0, 2, 0), (0, 2, 0)]
    assert classify_solid_height(
        vertices, vertices, None, (0, 0, 1), target_extrusion=None
    ) == 'SOLID_EXTRUSION_CHANGED'
