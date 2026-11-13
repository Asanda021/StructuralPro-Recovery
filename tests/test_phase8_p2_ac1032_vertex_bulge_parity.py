"""Synthetic-only AC1032 VERTEX source-vs-dual-DXF negative tests."""
import hashlib
import re
from pathlib import Path
import pytest
import ezdxf

from core.drawings.dwg_legacy_vertex_bulge_audit import audit_ac1032_legacy_vertex_bulge_parity


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def setup_files(tmp_path, *, erase_bulges=False, move_vertex=False,
                replace_vertex=False, modify_parent=False):
    src = tmp_path / 'original.dwg'
    src.write_bytes(b'AC1032' + bytes(128))   # Synthetic signature only, never decoded as DWG.
    refs = []
    for filename, broken in [('reference.dxf', False), ('converter.dxf', True)]:
        d = ezdxf.new('R2013')
        line = d.modelspace().add_polyline2d([(0, 0), (2, 0), (2, 2)], close=True)
        verts = list(line.vertices)
        verts[0].dxf.bulge = 0.5
        verts[1].dxf.bulge = -0.25
        block = d.blocks.new('FOOTPRINT')
        block_poly = block.add_polyline2d([(1, 1), (2, 1), (2, 2)], close=True)
        block_vert = list(block_poly.vertices)
        block_vert[0].dxf.bulge = 0.75
        if broken and erase_bulges:
            for v in [*verts, *block_vert]:
                v.dxf.bulge = 0
        if broken and move_vertex:
            verts[0].dxf.location = (0.5, 0, 0)
        if broken and replace_vertex:
            d.entitydb.delete_entity(verts[0])
        p = tmp_path / filename
        d.saveas(p)
        # ezdxf's synthetic exporter may preserve provisional VERTEX 330
        # values from construction. Normalize our fixtures to the actual
        # reconstructed parent POLYLINE before making deliberate mutations.
        reloaded = ezdxf.readfile(p)
        raw = p.read_text()
        vertices = [e for e in reloaded.entitydb.values()
                    if e is not None and e.dxftype() == 'VERTEX']
        for v in vertices:
            pattern = (rf"(\n  0\nVERTEX\n  5\n{v.dxf.handle}\n330\n)"
                       r"([0-9A-F]+)(\n)")
            match = re.search(pattern, raw)
            assert match is not None
            raw = raw[:match.start(2)] + str(v.dxf.owner) + raw[match.end(2):]
        p.write_text(raw)
        if broken and modify_parent:
            reloaded = ezdxf.readfile(p)
            raw = p.read_text()
            pattern = (rf"(\n  0\nVERTEX\n  5\n{verts[0].dxf.handle}\n330\n)"
                       r"([0-9A-F]+)(\n)")
            match = re.search(pattern, raw)
            assert match is not None
            owner = match.group(2)
            others = [e.dxf.handle for e in reloaded.entitydb.values()
                      if e is not None and e.dxftype() == 'POLYLINE'
                      and e.dxf.handle != owner]
            assert others
            p.write_text(raw[:match.start(2)] + others[0] + raw[match.end(2):])
        refs.append(p)
    return src, *refs


def audit(paths, **kwargs):
    src, a, b = paths
    return audit_ac1032_legacy_vertex_bulge_parity(
        src, a, b, original_sha256=_sha(src), reference_sha256=_sha(a),
        candidate_sha256=_sha(b), **kwargs)


def test_matches_are_not_source_or_financial_approval(tmp_path):
    r = audit(setup_files(tmp_path))
    assert r['reference_legacy_vertex_count'] == 6
    assert r['reference_nonzero_bulge_by_section'] == {'BLOCKS_OR_OTHER': 1, 'ENTITIES': 2}
    assert r['status'] == 'TWO_DXF_FIELD_PARITY_OBSERVED_SOURCE_UNVERIFIED_NO_GO'
    assert r['original_dwg_vertex_field_truth_verified'] is False
    assert r['financial_quantity_rows_approved'] == 0
    assert r['parent_vertex_order_difference_count'] == 0
    assert r['parent_polyline_flags_difference_count'] == 0


def test_zeroed_legacy_bulge_is_detected_in_both_sections(tmp_path):
    r = audit(setup_files(tmp_path, erase_bulges=True))
    assert r['reference_nonzero_bulges_zeroed_in_candidate_count'] == 3
    assert r['bulge_difference_count'] == 3
    assert r['candidate_nonzero_bulge_by_section'] == {}
    assert r['status'] == 'LEGACY_VERTEX_CONVERSION_DIFFERENCES_NO_GO'


def test_changed_coordinates_are_detected(tmp_path):
    r = audit(setup_files(tmp_path, move_vertex=True))
    assert r['xyz_difference_count'] == 1
    assert not r['financial_quantity_rows_approved']


def test_changed_owner_is_detected(tmp_path):
    with pytest.raises(ValueError, match="ownership/bulge differs from raw tags"):
        audit(setup_files(tmp_path, modify_parent=True))


def test_missing_vertex_is_detected(tmp_path):
    # The deleted entity has no counterpart with the original handle.
    r = audit(setup_files(tmp_path, replace_vertex=True))
    assert r['missing_vertex_handles_count'] == 1
    assert r['status'].endswith('NO_GO')


def test_same_handles_and_coordinates_but_reordered_vertices_veto(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    raw = cand.read_text()
    records = list(re.finditer(r"(?s)\n  0\nVERTEX\n.*?(?=\n  0\n)", raw))
    assert len(records) == 6
    a, b = records[3], records[4]  # The first two modelspace VERTEXs
    assert a.end() == b.start()
    cand.write_text(raw[:a.start()] + raw[b.start():b.end()] +
                    raw[a.start():a.end()] + raw[b.end():])
    result = audit((src, ref, cand))
    assert result['missing_vertex_handles_count'] == 0
    assert result['extra_vertex_handles_count'] == 0
    assert result['bulge_difference_count'] == 0
    assert result['xyz_difference_count'] == 0
    assert result['parent_vertex_order_difference_count'] == 1
    assert result['status'] == 'LEGACY_VERTEX_CONVERSION_DIFFERENCES_NO_GO'


def test_closed_polyline_flag_change_veto(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    raw = cand.read_text()
    pattern = r"(?s)(\n  0\nPOLYLINE\n.*?\n 70\n)(1)(\n  0\nVERTEX)"
    assert re.search(pattern, raw)
    cand.write_text(re.sub(pattern, lambda m: m.group(1) + '0' + m.group(3), raw, count=1))
    result = audit((src, ref, cand))
    assert result['parent_polyline_flags_difference_count'] == 1
    assert result['parent_vertex_order_difference_count'] == 0
    assert result['xyz_difference_count'] == 0
    assert result['status'] == 'LEGACY_VERTEX_CONVERSION_DIFFERENCES_NO_GO'


def test_malformed_raw_parent_flags_fail_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    raw = cand.read_text()
    pattern = r"(?s)(\n  0\nPOLYLINE\n.*?\n 70\n)1(\n  0\nVERTEX)"
    assert re.search(pattern, raw)
    cand.write_text(re.sub(pattern, lambda m: m.group(1) + 'NaN' + m.group(2), raw, count=1))
    with pytest.raises(ValueError, match='Malformed raw POLYLINE flags'):
        audit((src, ref, cand))


def test_wrong_source_hash_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    with pytest.raises(ValueError, match='SHA-256'):
        audit_ac1032_legacy_vertex_bulge_parity(src, ref, cand,
            original_sha256='0' * 64, reference_sha256=_sha(ref), candidate_sha256=_sha(cand))


def test_same_file_input_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    with pytest.raises(ValueError, match='independent'):
        audit_ac1032_legacy_vertex_bulge_parity(src, ref, ref,
            original_sha256=_sha(src), reference_sha256=_sha(ref), candidate_sha256=_sha(ref))


def test_symlink_input_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    alias = tmp_path / 'link.dxf'
    try:
        alias.symlink_to(cand)
    except (OSError, NotImplementedError):
        pytest.skip('symlinks not enabled on this platform')
    with pytest.raises(ValueError, match='non-symlink'):
        audit_ac1032_legacy_vertex_bulge_parity(src, ref, alias,
            original_sha256=_sha(src), reference_sha256=_sha(ref), candidate_sha256=_sha(cand))


def test_wrong_version_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    src.write_bytes(b'AC1018' + bytes(128))
    with pytest.raises(ValueError, match='AC1032'):
        audit((src, ref, cand))


def test_invalid_tolerance_fails_closed(tmp_path):
    files = setup_files(tmp_path)
    with pytest.raises(ValueError, match='tolerance'):
        audit(files, abs_tolerance=0.01)


def test_private_ids_and_sha_not_in_receipt(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    r = audit((src, ref, cand))
    encoded = repr(r)
    for digest in [_sha(src), _sha(ref), _sha(cand)]:
        assert digest not in encoded
    assert not any('handle' in k and not k.endswith('_count') for k in r)


def test_hardlinked_input_does_not_count_as_independent(tmp_path):
    import os
    src, ref, cand = setup_files(tmp_path)
    duplicate = tmp_path / 'alias.dxf'
    os.link(ref, duplicate)
    with pytest.raises(ValueError, match='independent'):
        audit_ac1032_legacy_vertex_bulge_parity(src, ref, duplicate,
            original_sha256=_sha(src), reference_sha256=_sha(ref),
            candidate_sha256=_sha(ref))


def test_duplicate_raw_bulge_tag_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    raw = cand.read_text()
    assert '\n 42\n0.5\n' in raw
    cand.write_text(raw.replace('\n 42\n0.5\n',
                                '\n 42\n0.5\n 42\n0.25\n', 1))
    with pytest.raises(ValueError, match='Duplicated raw DXF VERTEX tag'):
        audit((src, ref, cand))


def test_invalid_raw_numeric_bulge_fails_closed(tmp_path):
    src, ref, cand = setup_files(tmp_path)
    raw = cand.read_text()
    assert '\n 42\n0.5\n' in raw
    cand.write_text(raw.replace('\n 42\n0.5\n',
                                '\n 42\nnan\n', 1))
    with pytest.raises(ValueError, match='Nonfinite raw DXF VERTEX bulge'):
        audit((src, ref, cand))
