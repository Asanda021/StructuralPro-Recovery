"""Synthetic-only negative tests; no private drawings and no quantity approval."""
from types import SimpleNamespace
import pytest
from core.drawings.dwg_insert_solid_contract import (
    _vec_equal, verify_insert_fields, verify_block_line, classify_solid_height,
    audit_insert_solid, verify_direct_modelspace_roster,
    verify_insert_attached_attributes,
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


def test_block_line_large_coordinate_loss_exceeds_absolute_tolerance():
    original = native('LINE', start=(1_000_000_000.0, 1, 2), end=(4, 5, 6))
    changed = converted('LINE', layer='A', start=(1_000_000_000.0005, 1, 2), end=(4, 5, 6))
    assert 'BLOCK_LINE_START_CHANGED' in verify_block_line(original, changed, 'A')


def test_modelspace_solid_roster_detects_added_and_removed_dxf_entity():
    import ezdxf
    drawing = ezdxf.new("R2013")
    model = drawing.modelspace()
    a = model.add_solid([(0, 0), (2, 0), (0, 2)])
    original = {int(a.dxf.handle, 16)}
    verify_direct_modelspace_roster(original, drawing, "SOLID")
    extra = model.add_solid([(3, 0), (4, 0), (3, 1)])
    with pytest.raises(ValueError, match="extra=1"):
        verify_direct_modelspace_roster(original, drawing, "SOLID")
    model.delete_entity(extra)
    model.delete_entity(a)
    with pytest.raises(ValueError, match="missing=1"):
        verify_direct_modelspace_roster(original, drawing, "SOLID")


def test_modelspace_roster_does_not_accept_paperspace_solid():
    import ezdxf
    drawing = ezdxf.new("R2013")
    paper = drawing.layouts.get("Layout1")
    a = paper.add_solid([(0, 0), (1, 0), (0, 1)])
    # EntityDB can find this original handle, but it is not in ModelSpace.
    original = {int(a.dxf.handle, 16)}
    assert drawing.entitydb.get(a.dxf.handle) is a
    with pytest.raises(ValueError, match="missing=1"):
        verify_direct_modelspace_roster(original, drawing, "SOLID")


def test_modelspace_insert_roster_detects_added_reference():
    import ezdxf
    drawing = ezdxf.new("R2013")
    drawing.blocks.new("PUBLIC_BLOCK")
    model = drawing.modelspace()
    original_insert = model.add_blockref("PUBLIC_BLOCK", (0, 0))
    original = {int(original_insert.dxf.handle, 16)}
    verify_direct_modelspace_roster(original, drawing, "INSERT")
    model.add_blockref("PUBLIC_BLOCK", (4, 0))
    with pytest.raises(ValueError, match="extra=1"):
        verify_direct_modelspace_roster(original, drawing, "INSERT")


def test_modelspace_roster_rejects_type_or_identity_mismatch():
    import ezdxf
    drawing = ezdxf.new("R2013")
    line = drawing.modelspace().add_line((0, 0), (1, 0))
    with pytest.raises(ValueError, match="missing=1"):
        verify_direct_modelspace_roster({int(line.dxf.handle, 16)}, drawing, "SOLID")
    with pytest.raises(ValueError, match="Unsupported"):
        verify_direct_modelspace_roster(set(), drawing, "LINE")
    with pytest.raises(ValueError, match="Malformed"):
        verify_direct_modelspace_roster({0}, drawing, "INSERT")



def test_real_dxf_minsert_array_counts_and_spacings():
    """MINSERT is a native type, but ezdxf represents its array as INSERT."""
    import ezdxf
    dxf = ezdxf.new("R2013")
    dxf.blocks.new("PUBLIC_ARRAY")
    reference = dxf.modelspace().add_blockref(
        "PUBLIC_ARRAY", (1, 2, 3), dxfattribs={
            "layer": "0", "column_count": 3, "row_count": 2,
            "column_spacing": 5.0, "row_spacing": 7.0,
        },
    )
    source = native(
        "MINSERT", insert=(1, 2, 3),
        column_count=3, row_count=2,
        column_spacing=5.0, row_spacing=7.0,
    )
    assert reference.dxftype() == "INSERT"
    assert verify_insert_fields(source, reference, "0") == []


@pytest.mark.parametrize("field, value, code", [
    ("column_count", 4, "INSERT_COLUMN_COUNT_CHANGED"),
    ("row_count", 3, "INSERT_ROW_COUNT_CHANGED"),
    ("column_spacing", 6.0, "INSERT_COLUMN_SPACING_CHANGED"),
    ("row_spacing", 8.0, "INSERT_ROW_SPACING_CHANGED"),
])
def test_minsert_changed_replication_is_detected(field, value, code):
    source = native(
        "MINSERT", insert=(1, 2, 3),
        column_count=3, row_count=2,
        column_spacing=5.0, row_spacing=7.0,
    )
    attributes = dict(
        layer="0", insert=(1, 2, 3),
        column_count=3, row_count=2,
        column_spacing=5.0, row_spacing=7.0,
    )
    attributes[field] = value
    assert code in verify_insert_fields(source, converted("INSERT", **attributes), "0")


@pytest.mark.parametrize("count", [0, -1, 1000001, 2.5, True])
def test_minsert_invalid_array_count_never_matches(count):
    source = native("MINSERT", insert=(0, 0, 0), column_count=3, row_count=2)
    target = converted("INSERT", layer="0", insert=(0, 0, 0),
                       column_count=count, row_count=2)
    assert "INSERT_COLUMN_COUNT_INVALID" in verify_insert_fields(source, target, "0")


def test_minsert_replication_above_engineering_cap_is_rejected():
    source = native("MINSERT", insert=(0, 0, 0),
                    column_count=1001, row_count=1000)
    target = converted("INSERT", layer="0", insert=(0, 0, 0),
                       column_count=1001, row_count=1000)
    assert "INSERT_ARRAY_INSTANCE_LIMIT_EXCEEDED" in verify_insert_fields(source, target, "0")


def test_simple_insert_uses_safe_dxftype_defaults_for_array_fields():
    source = native("INSERT", insert=(0, 0, 0))
    target = converted("INSERT", layer="0", insert=(0, 0, 0))
    assert verify_insert_fields(source, target, "0") == []


def _attrib_test_fixture():
    """DXF is real ezdxf; native ATTRIB objects are synthetic original-DWG records."""
    import ezdxf
    d = ezdxf.new("R2013")
    block = d.blocks.new("PUBLIC_WITH_ATTRIB")
    block.add_attdef("MODEL", insert=(0, 0))
    instance = d.modelspace().add_blockref("PUBLIC_WITH_ATTRIB", (0, 0))
    a = instance.add_attrib("MODEL", "SYNTHETIC", insert=(1, 2, 0),
                            dxfattribs={"flags": 2})
    b = instance.add_attrib("UNIT", "mm", insert=(2, 3, 0))
    parent = int(instance.dxf.handle, 16)
    records = [
        SimpleNamespace(handle=int(a.dxf.handle, 16), dxf={
            "tag": "MODEL", "text": "SYNTHETIC", "insert": (1, 2, 0),
            "attribute_flags": 2,
        }),
        SimpleNamespace(handle=int(b.dxf.handle, 16), dxf={
            "tag": "UNIT", "text": "mm", "insert": (2, 3, 0),
            "attribute_flags": 0,
        }),
    ]
    return d, parent, records, (a, b), instance


def test_original_insert_attrib_identity_and_selected_fields():
    d, parent, source, _, instance = _attrib_test_fixture()
    assert verify_insert_attached_attributes({parent: source}, d, {parent}) == 2
    assert verify_insert_attached_attributes({}, d, set()) == 0
    # Exact value matching is not original-font or source-glyph certification.
    assert len(instance.attribs) == 2


@pytest.mark.parametrize("change, expected", [
    ("text", "tag/text changed"),
    ("tag", "tag/text changed"),
    ("flags", "flags changed"),
    ("insert", "position changed"),
    ("owner", "moved to another INSERT"),
    ("drop", "count changed"),
    ("extra", "count changed"),
])
def test_original_insert_attrib_mutation_is_rejected(change, expected):
    d, parent, source, attrs, instance = _attrib_test_fixture()
    if change == "text":
        attrs[0].dxf.text = "ALTERED"
    elif change == "tag":
        attrs[0].dxf.tag = "OTHER"
    elif change == "flags":
        attrs[0].dxf.flags = 1
    elif change == "insert":
        attrs[0].dxf.insert = (8, 8, 0)
    elif change == "owner":
        attrs[0].dxf.owner = "FFFF"
    elif change == "drop":
        instance.attribs.remove(attrs[0])
    elif change == "extra":
        instance.add_attrib("EXTRA", "UNDOCUMENTED", insert=(4, 4, 0))
    with pytest.raises(ValueError, match=expected):
        verify_insert_attached_attributes({parent: source}, d, {parent})


def test_dxf_attrib_hidden_in_entitydb_without_attachment_is_rejected():
    d, parent, source, attrs, instance = _attrib_test_fixture()
    instance.attribs.remove(attrs[0])
    # Keep source/target counts equal while hiding an index-owned ATTRIB.
    source = source[1:]
    with pytest.raises(ValueError, match="Detached converted ATTRIB"):
        verify_insert_attached_attributes({parent: source}, d, {parent})


def test_original_insert_attrib_duplicate_source_id_is_rejected():
    d, parent, source, _, instance = _attrib_test_fixture()
    source[1].handle = source[0].handle
    with pytest.raises(ValueError, match="Duplicate original ATTRIB"):
        verify_insert_attached_attributes({parent: source}, d, {parent})


def test_original_insert_attrib_foreign_parent_is_rejected():
    d, parent, source, _, instance = _attrib_test_fixture()
    with pytest.raises(ValueError, match="Malformed source"):
        verify_insert_attached_attributes({parent + 1: source}, d, {parent})
