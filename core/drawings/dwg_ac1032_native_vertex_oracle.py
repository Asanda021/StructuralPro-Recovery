"""Fail-closed original AC1032 DWG legacy 2D VERTEX audit against diagnostic DXFs.

Only aggregate differences may leave this module. This checks one pinned native
reader's field observations, not a certified DWG/Autodesk semantic oracle.
It NEVER authorizes payable quantities, even when fields all match.
"""
from __future__ import annotations

from collections import Counter
from importlib import metadata
import math
from pathlib import Path
from typing import Any

from core.drawings.dwg_legacy_vertex_bulge_audit import (
    _MAX_VERTICES, _raw_vertex_owner_bulge, _roster, _snapshot, _unchanged,
)

_PINNED_READER_VERSION = '0.17.0'


def _integer_handle(value: Any) -> str:
    if type(value) is not int or not 0 < value < 2**64:
        raise ValueError('Invalid independent native vertex or parent identity')
    return format(value, 'X')


def _finite_xyz(values: Any) -> tuple[float, float, float]:
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        raise ValueError('Invalid original native vertex coordinates')
    xyz = tuple(float(v) for v in values)
    if not all(math.isfinite(v) for v in xyz):
        raise ValueError('Original native vertex coordinates are nonfinite')
    return xyz


def _native_2d_vertex_roster(poly_rows, sequence_rows, vertex_rows):
    """Require agreement of three separate pinned Rust-reader projections.

    poly_rows: decode_polyline_2d_with_vertex_data, per-vertex
    (x,y,z,start_width,end_width,bulge,tangent,flags).
    sequence_rows: decode_polyline_sequence_members, vertex identities.
    vertex_rows: decode_vertex_2d_entities, per-handle geometry/bulge.
    """
    if not all(isinstance(rows, (list, tuple)) for rows in (poly_rows, sequence_rows, vertex_rows)):
        raise ValueError('Incomplete independent original-DWG native reader data')
    if not 1 <= len(poly_rows) <= _MAX_VERTICES or len(sequence_rows) > _MAX_VERTICES or len(vertex_rows) > _MAX_VERTICES:
        raise ValueError('Missing or unbounded native legacy polyline data')

    sequences = {}
    for row in sequence_rows:
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise ValueError('Malformed native POLYLINE member sequence')
        parent, kind, ids, faces, seqend = row
        if kind != 'POLYLINE_2D':
            continue
        key = _integer_handle(parent)
        if key in sequences or not isinstance(ids, (list, tuple)) or not ids:
            raise ValueError('Duplicate/empty native 2D POLYLINE member sequence')
        if faces or seqend is None:
            raise ValueError('Native 2D POLYLINE has invalid SEQEND/faces')
        _integer_handle(seqend)
        sequence = tuple(_integer_handle(h) for h in ids)
        if len(set(sequence)) != len(sequence):
            raise ValueError('Native POLYLINE repeats VERTEX identity')
        sequences[key] = sequence

    vertices = {}
    for row in vertex_rows:
        if not isinstance(row, (tuple, list)) or len(row) != 9:
            raise ValueError('Malformed independently decoded DWG VERTEX record')
        h = _integer_handle(row[0])
        flags = row[1]
        if type(flags) is not int or not 0 <= flags <= 65535:
            raise ValueError('Invalid native VERTEX flags')
        xyz = _finite_xyz(row[2:5])
        bulge = float(row[7])
        if not math.isfinite(bulge) or h in vertices:
            raise ValueError('Duplicate/invalid native VERTEX bulge')
        vertices[h] = (xyz, bulge, flags)

    result, flags_by_parent, sequence_by_parent = {}, {}, {}
    if set(sequences) != {_integer_handle(row[0]) for row in poly_rows}:
        raise ValueError('Native 2D POLYLINE roster differs from sequence index')
    for row in poly_rows:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError('Malformed independently decoded DWG POLYLINE')
        parent = _integer_handle(row[0])
        flags, decoded_vertices = row[1:]
        if type(flags) is not int or not 0 <= flags <= 65535:
            raise ValueError('Invalid native POLYLINE flags')
        if not isinstance(decoded_vertices, (tuple, list)):
            raise ValueError('Native polyline vertex list is malformed')
        # The pinned raw POLYLINE decoder can emit one duplicate closing point
        # for an explicitly closed contour even when the original VERTEX
        # handle sequence contains no extra VERTEX. The high-level ezdwg
        # reader explicitly strips this repeated closure position. Accept only
        # an exact redundant endpoint, never an arbitrary missing/extra node.
        if (len(decoded_vertices) == len(sequences[parent]) + 1 and flags & 1):
            first, last = decoded_vertices[0], decoded_vertices[-1]
            if (not isinstance(first, (list, tuple)) or not isinstance(last, (list, tuple))
                    or len(first) != 8 or len(last) != 8
                    or _finite_xyz(first[:3]) != _finite_xyz(last[:3])):
                raise ValueError('Native polyline has nonredundant extra endpoint')
            # Coincident coordinates alone are insufficient: a closing row
            # with distinct width, bulge, tangent or flags is not redundant.
            # Do not discard possible source geometry/semantics silently.
            try:
                finite_closure = all(math.isfinite(float(v)) for v in (*first[:7], *last[:7]))
            except (TypeError, ValueError, OverflowError):
                finite_closure = False
            if not finite_closure or tuple(first) != tuple(last):
                raise ValueError('Native polyline has nonredundant extra endpoint metadata')
            decoded_vertices = decoded_vertices[:-1]
        if len(decoded_vertices) != len(sequences[parent]):
            raise ValueError('Native polyline vertex list differs from source handles')
        flags_by_parent[parent] = flags
        sequence_by_parent[parent] = sequences[parent]
        for handle, decoded in zip(sequences[parent], decoded_vertices):
            if (handle in result or handle not in vertices or not isinstance(decoded, (tuple, list))
                    or len(decoded) != 8 or type(decoded[7]) is not int):
                raise ValueError('Missing/duplicated native 2D VERTEX identity')
            xyz = _finite_xyz(decoded[:3])
            bulge = float(decoded[5])
            if not math.isfinite(bulge):
                raise ValueError('Nonfinite native 2D POLYLINE bulge')
            truth = vertices[handle]
            if (truth[2] != decoded[7] or any(abs(a-b) > 1e-9 for a,b in zip(xyz,truth[0]))
                    or abs(bulge-truth[1]) > 1e-9):
                raise ValueError('Native source VERTEX and POLYLINE geometry conflict')
            result[handle] = (parent, xyz, bulge, truth[2])
            if len(result) > _MAX_VERTICES:
                raise ValueError('Unbounded native POLYLINE VERTEX inventory')
    if not result:
        raise ValueError('Native 2D vertex inventory is empty')
    return result, flags_by_parent, sequence_by_parent


def _compare_native_to_dxf(source_roster, source_flags, source_sequence, dxf_path, *, tolerance):
    """Cross-check original observations with raw DXF tags and parser view."""
    import ezdxf
    raw, raw_parent_flags = _raw_vertex_owner_bulge(dxf_path)
    dxf = ezdxf.readfile(str(dxf_path))
    parsed = _roster(dxf)
    if set(raw) != set(parsed):
        raise ValueError('DXF raw/parsed VERTEX roster mismatch')
    for h, entry in parsed.items():
        owner, bulge = raw[h]
        if entry[0] != owner or abs(entry[4]-bulge) > tolerance:
            raise ValueError('DXF parser normalization changed raw ownership or bulge')
    for parent in {entry[0] for entry in parsed.values()}:
        entity = dxf.entitydb.get(parent)
        flags = entity.dxf.get('flags', 0)
        if type(flags) is not int or parent not in raw_parent_flags or raw_parent_flags[parent] != flags:
            raise ValueError('DXF parser normalized original POLYLINE flags')

    source_ids = set(source_roster)
    target_ids = set(parsed)
    missing = source_ids - target_ids
    # Extra DXF vertices can legitimately be 3D/mesh vertices outside this
    # 2D audit; count them as unverified, never as proven source additions.
    unscoped = target_ids - source_ids
    differences = Counter()
    for h in source_ids & target_ids:
        owner, xyz, bulge, flags = source_roster[h]
        dxf_data = parsed[h]
        if owner != dxf_data[0]:
            differences['owner'] += 1
        if flags != dxf_data[5]:
            differences['flags'] += 1
        if any(abs(a-b) > tolerance for a,b in zip(xyz,dxf_data[3])):
            differences['xyz'] += 1
        if abs(bulge-dxf_data[4]) > tolerance:
            differences['bulge'] += 1
            if abs(bulge) > tolerance and abs(dxf_data[4]) <= tolerance:
                differences['lost_curvature'] += 1

    # Ordering can change geometry while all handles, coordinates and bulges match.
    target_sequences = {}
    for h,(parent,_) in raw.items():
        target_sequences.setdefault(parent, []).append(h)
    for parent, handles in source_sequence.items():
        dxf_handles = target_sequences.get(parent, [])
        if set(handles) == set(dxf_handles) and tuple(dxf_handles) != tuple(handles):
            differences['order'] += 1
        if parent not in raw_parent_flags or raw_parent_flags[parent] != source_flags[parent]:
            differences['polyline_flags'] += 1

    return {
        'native_2d_vertex_count': len(source_roster),
        'native_2d_nonzero_bulge_count': sum(abs(data[2]) > tolerance for data in source_roster.values()),
        'dxf_legacy_vertex_count': len(parsed),
        'source_vertex_id_missing_count': len(missing),
        'dxf_vertices_outside_native_2d_scope_count': len(unscoped),
        'owner_difference_count': differences['owner'],
        'vertex_flag_difference_count': differences['flags'],
        'coordinate_difference_count': differences['xyz'],
        'bulge_difference_count': differences['bulge'],
        'native_nonzero_bulge_zeroed_in_dxf_count': differences['lost_curvature'],
        'sequence_difference_count': differences['order'],
        'polyline_flag_difference_count': differences['polyline_flags'],
    }


def audit_ac1032_native_2d_vertex_sources(
    original_dwg: str | Path,
    reference_dxf: str | Path,
    candidate_dxf: str | Path,
    *, original_sha256: str, reference_sha256: str, candidate_sha256: str,
    abs_tolerance: float = 1e-9,
) -> dict:
    """Compare original native DWG 2D vertex observations with both DXFs.

    This is evidence of a second reader, NOT proof of DWG truth, complete
    vertex recovery or financial certification. Never modifies source files.
    """
    if type(abs_tolerance) is not float or not 0 < abs_tolerance <= 1e-6:
        raise ValueError('Invalid independent geometry tolerance')
    digests = (original_sha256, reference_sha256, candidate_sha256)
    records = [_snapshot(p, sha) for p,sha in zip((original_dwg,reference_dxf,candidate_dxf),digests)]
    if len({(stat[0], stat[1]) for _, stat in records}) != 3:
        raise ValueError('Independent audit requires three distinct input files')
    original = records[0][0]
    with original.open('rb') as stream:
        if stream.read(6) != b'AC1032':
            raise ValueError('Only original AC1032 DWG supported by this source audit')
    if metadata.version('ezdwg') != _PINNED_READER_VERSION:
        raise ValueError('Native ezdwg reader version differs from frozen evidence')
    from ezdwg import raw
    if raw.detect_version(str(original)) != 'AC1032':
        raise ValueError('Pinned native reader did not confirm original DWG version')
    poly = raw.decode_polyline_2d_with_vertex_data(str(original))
    membership = raw.decode_polyline_sequence_members(str(original))
    vertex = raw.decode_vertex_2d_entities(str(original))
    source, flags, sequence = _native_2d_vertex_roster(poly,membership,vertex)
    reference = _compare_native_to_dxf(source,flags,sequence,records[1][0],tolerance=abs_tolerance)
    candidate = _compare_native_to_dxf(source,flags,sequence,records[2][0],tolerance=abs_tolerance)
    for (p,identity), digest in zip(records,digests):
        _unchanged(p,identity,digest)
    discrepancy_fields = ('source_vertex_id_missing_count','owner_difference_count',
                          'vertex_flag_difference_count','coordinate_difference_count',
                          'bulge_difference_count','sequence_difference_count',
                          'polyline_flag_difference_count')
    any_diff = any(item[key] for item in (reference,candidate) for key in discrepancy_fields)
    return {
        'policy': 'p8p2_native_ac1032_legacy_2d_vertex_source_vs_two_dxf_v1',
        'reader_version': 'ezdwg==0.17.0',
        'native_2d_vertex_observations_verified_by_reader': len(source),
        'reference_dxf': reference, 'candidate_dxf': candidate,
        'all_source_object_types_semantics_verified': False,
        'ac1032_source_geometry_certified': False,
        'original_to_converted_financial_geometry_approved': False,
        'financial_quantity_rows_approved': 0,
        'status': ('NATIVE_SOURCE_VS_DXF_FIELD_DISCREPANCY_NO_GO' if any_diff
                   else 'NATIVE_FIELDS_MATCH_SEMANTICS_UNVERIFIED_NO_GO'),
    }
