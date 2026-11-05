"""Synthetic only: pinned native 2D VERTEX API cross-reader contract."""
from __future__ import annotations

import hashlib
import re
import sys
from types import ModuleType, SimpleNamespace

import pytest
import ezdxf
from core.drawings import dwg_ac1032_native_vertex_oracle as oracle


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def setup_files(tmp_path, *, erase_bulges=False, move_vertex=False, modify_parent=False):
    original = tmp_path / 'original.dwg'
    original.write_bytes(b'AC1032' + bytes(128))
    results = []
    for filename, altered in [('reference.dxf', False), ('candidate.dxf', True)]:
        d = ezdxf.new('R2013')
        poly = d.modelspace().add_polyline2d([(0,0),(2,0),(2,2)], close=True)
        vertices = list(poly.vertices)
        vertices[0].dxf.bulge = 0.5
        vertices[1].dxf.bulge = -0.25
        block = d.blocks.new('FOOTPRINT')
        block_poly = block.add_polyline2d([(1,1),(2,1),(2,2)], close=True)
        block_vertices = list(block_poly.vertices)
        block_vertices[0].dxf.bulge = 0.75
        if altered and erase_bulges:
            for v in (*vertices,*block_vertices):
                v.dxf.bulge = 0
        if altered and move_vertex:
            vertices[0].dxf.location = (0.5,0,0)
        path = tmp_path / filename
        d.saveas(path)
        parsed = ezdxf.readfile(path)
        text = path.read_text()
        for vertex in parsed.entitydb.values():
            if vertex is not None and vertex.dxftype() == 'VERTEX':
                pattern = (rf"(\n  0\nVERTEX\n  5\n{vertex.dxf.handle}\n330\n)"
                           r"([0-9A-F]+)(\n)")
                match = re.search(pattern,text)
                assert match is not None
                text = text[:match.start(2)] + str(vertex.dxf.owner) + text[match.end(2):]
        path.write_text(text)
        if altered and modify_parent:
            parsed = ezdxf.readfile(path)
            text = path.read_text()
            pattern = (rf"(\n  0\nVERTEX\n  5\n{vertices[0].dxf.handle}\n330\n)"
                       r"([0-9A-F]+)(\n)")
            match = re.search(pattern,text)
            assert match is not None
            current = match.group(2)
            candidates = [e.dxf.handle for e in parsed.entitydb.values()
                          if e is not None and e.dxftype() == 'POLYLINE'
                          and e.dxf.handle != current]
            assert candidates
            path.write_text(text[:match.start(2)] + candidates[0] + text[match.end(2):])
        results.append(path)
    return original, *results


def native_projection_from_dxf(dxf):
    doc = ezdxf.readfile(dxf)
    poly_rows, members, vertex_rows = [], [], []
    for e in doc.entitydb.values():
        if e is None or e.dxftype() != 'POLYLINE':
            continue
        vertices = list(e.vertices)
        decoded = []
        for v in vertices:
            p = v.dxf.location
            decoded.append((float(p.x),float(p.y),float(p.z),0.0,0.0,
                            float(v.dxf.get('bulge',0)),0.0,int(v.dxf.get('flags',0))))
            vertex_rows.append((int(v.dxf.handle,16),int(v.dxf.get('flags',0)),
                                float(p.x),float(p.y),float(p.z),0.0,0.0,
                                float(v.dxf.get('bulge',0)),0.0))
        poly_rows.append((int(e.dxf.handle,16), int(e.dxf.get('flags',0)), decoded))
        members.append((int(e.dxf.handle,16),'POLYLINE_2D',
                        [int(v.dxf.handle,16) for v in vertices],[],
                        int(e.seqend.dxf.handle,16)))
    return poly_rows,members,vertex_rows


def fake_reader(monkeypatch, native_reference):
    poly,members,verts = native_projection_from_dxf(native_reference)
    native = ModuleType('ezdwg')
    raw = SimpleNamespace(detect_version=lambda p:'AC1032',
                          decode_polyline_2d_with_vertex_data=lambda p:poly,
                          decode_polyline_sequence_members=lambda p:members,
                          decode_vertex_2d_entities=lambda p:verts)
    native.raw = raw
    monkeypatch.setitem(sys.modules,'ezdwg',native)
    monkeypatch.setattr(oracle.metadata,'version',lambda n:'0.17.0')
    return poly,members,verts


def run(files):
    src,ref,cand = files
    return oracle.audit_ac1032_native_2d_vertex_sources(
        src,ref,cand,original_sha256=sha(src),reference_sha256=sha(ref),candidate_sha256=sha(cand))


def test_original_reader_fields_match_but_never_approve(tmp_path,monkeypatch):
    files = setup_files(tmp_path)
    fake_reader(monkeypatch,files[1])
    r=run(files)
    assert r['native_2d_vertex_observations_verified_by_reader']==6
    assert r['status']=='NATIVE_FIELDS_MATCH_SEMANTICS_UNVERIFIED_NO_GO'
    assert r['reference_dxf']['bulge_difference_count']==0
    assert r['candidate_dxf']['bulge_difference_count']==0
    assert r['ac1032_source_geometry_certified'] is False
    assert r['financial_quantity_rows_approved']==0


def test_gnu_like_zero_bulges_exposed_against_original(tmp_path,monkeypatch):
    files = setup_files(tmp_path,erase_bulges=True)
    fake_reader(monkeypatch,files[1])
    r=run(files)
    assert r['reference_dxf']['bulge_difference_count']==0
    assert r['candidate_dxf']['native_nonzero_bulge_zeroed_in_dxf_count']==3
    assert r['candidate_dxf']['bulge_difference_count']==3
    assert r['status']=='NATIVE_SOURCE_VS_DXF_FIELD_DISCREPANCY_NO_GO'
    assert r['financial_quantity_rows_approved']==0


def test_changed_coordinate_detected(tmp_path,monkeypatch):
    files=setup_files(tmp_path,move_vertex=True)
    fake_reader(monkeypatch,files[1])
    assert run(files)['candidate_dxf']['coordinate_difference_count']==1


def test_changed_raw_owner_cannot_be_normalized_to_false_parity(tmp_path,monkeypatch):
    files=setup_files(tmp_path,modify_parent=True)
    fake_reader(monkeypatch,files[1])
    with pytest.raises(ValueError,match='normalization changed raw ownership'):
        run(files)


@pytest.mark.parametrize('bad',['duplicate_polys','missing_members','duplicate_vertex','lost_vertex',
                                'polyline_reader_conflict','bad_seqend','wrong_type','bogus_vertex_flag'])
def test_conflicting_native_fields_fail_closed(tmp_path,monkeypatch,bad):
    files=setup_files(tmp_path)
    poly,members,verts=fake_reader(monkeypatch,files[1])
    poly=list(poly);members=list(members);verts=list(verts)
    if bad=='duplicate_polys':poly.append(poly[0])
    elif bad=='missing_members':members.pop()
    elif bad=='duplicate_vertex':verts.append(verts[0])
    elif bad=='lost_vertex':verts.pop()
    elif bad=='polyline_reader_conflict':
        p,f,data=poly[0];poly[0]=(p,f,[(*data[0][:5],99.0,*data[0][6:]),*data[1:]])
    elif bad=='bad_seqend':
        p,k,ids,faces,end=members[0];members[0]=(p,k,ids,faces,None)
    elif bad=='wrong_type':
        p,k,ids,faces,end=members[0];members[0]=(p,'POLYLINE_3D',ids,faces,end)
    else:
        v=list(verts[0]);v[1]=70000;verts[0]=tuple(v)
    with pytest.raises(ValueError):
        oracle._native_2d_vertex_roster(poly,members,verts)


def test_source_sha_mismatch_blocks_before_native_decode(tmp_path,monkeypatch):
    files=setup_files(tmp_path)
    fake_reader(monkeypatch,files[1])
    src,ref,cand=files
    with pytest.raises(ValueError,match='SHA-256'):
        oracle.audit_ac1032_native_2d_vertex_sources(src,ref,cand,original_sha256='0'*64,
                            reference_sha256=sha(ref),candidate_sha256=sha(cand))


def test_wrong_pinned_reader_version_blocks(tmp_path,monkeypatch):
    files=setup_files(tmp_path)
    fake_reader(monkeypatch,files[1])
    monkeypatch.setattr(oracle.metadata,'version',lambda x:'0.19.0')
    with pytest.raises(ValueError,match='version'):
        run(files)


def test_private_hash_and_handles_not_reported(tmp_path,monkeypatch):
    files=setup_files(tmp_path)
    fake_reader(monkeypatch,files[1])
    r=run(files)
    output=repr(r)
    for path in files:
        assert str(path) not in output
        assert sha(path) not in output
    assert r['original_to_converted_financial_geometry_approved'] is False
