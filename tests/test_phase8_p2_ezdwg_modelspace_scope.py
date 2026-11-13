"""Public synthetic regression for ezdwg 0.17.0 diagnostic-only DXF scope.

Never uses user drawings. The source-path conversion is not a safe substitute
for an explicitly selected ModelSpace layout: the former may flatten BLOCK
members into the DXF ModelSpace, even when modelspace_only=True.
"""
from __future__ import annotations

from importlib import metadata

import pytest

import ezdxf
import ezdwg


def _source_with_modelspace_and_block_polyline(tmp_path):
    original = tmp_path / 'PUBLIC_SYNTHETIC_AC1015.dwg'
    drawing = ezdwg.new()
    msp = drawing.modelspace()
    msp.add_polyline2d([(0, 0), (4, 0), (4, 3)], closed=True,
                       bulges=[0.0, 0.5, -0.25])
    block = drawing.blocks.new('PUBLIC_SYMBOL')
    block.add_polyline2d([(10, 10), (12, 10), (12, 12)],
                         closed=True, bulges=[0.25, 0.0, 0.0])
    msp.add_blockref('PUBLIC_SYMBOL', (100, 100))
    drawing.save(str(original))
    return original


def test_explicit_modelspace_layout_does_not_export_block_geometry(tmp_path):
    assert metadata.version('ezdwg') == '0.17.0'
    original = _source_with_modelspace_and_block_polyline(tmp_path)
    source = ezdwg.read(str(original))
    selected = list(source.modelspace().query('POLYLINE_2D'))
    assert len(selected) == 1
    output = tmp_path / 'scoped.dxf'
    result = ezdwg.to_dxf(source.modelspace(), str(output),
                          types='POLYLINE_2D', modelspace_only=True,
                          preserve_colors=False, strict=True)
    exported = list(ezdxf.readfile(str(output)).modelspace().query('LWPOLYLINE'))
    assert result.total_entities == result.written_entities == len(selected) == len(exported) == 1
    assert result.skipped_entities == 0
    assert exported[0].closed
    assert [float(v[4]) for v in exported[0].get_points('xyseb')] == pytest.approx(
        [0.0, 0.5, -0.25])
    # Successful DXF diagnostics are never evidence of DWG semantic/unit truth.


def test_plain_source_path_scope_hint_is_not_trusted(tmp_path):
    assert metadata.version('ezdwg') == '0.17.0'
    original = _source_with_modelspace_and_block_polyline(tmp_path)
    source = ezdwg.read(str(original))
    expected = len(list(source.modelspace().query('POLYLINE_2D')))
    unsafe = tmp_path / 'unsafe-raw-path.dxf'
    result = ezdwg.to_dxf(str(original), str(unsafe),
                          types='POLYLINE_2D', modelspace_only=True,
                          preserve_colors=False, strict=True)
    observed = len(list(ezdxf.readfile(str(unsafe)).modelspace().query('LWPOLYLINE')))
    # Current pinned binary returns the ModelSpace and block-definition rows.
    # A mismatch MUST be flagged, not silently treated as payable geometry.
    assert expected == 1
    assert result.total_entities == observed == 2
    assert observed != expected


def _scoped_geometry_fingerprint(doc):
    """Count, elevation, ordered XY, widths, bulges and closure; never payable."""
    return tuple(
        (str(poly.dxf.layer), bool(poly.closed),
         tuple(tuple(float(v) for v in point)
               for point in poly.get_points('xyseb')), float(poly.dxf.elevation))
        for poly in doc.modelspace().query('LWPOLYLINE')
    )


@pytest.mark.parametrize('mutation', ['x', 'precision', 'elevation', 'width', 'bulge', 'order', 'closure'])
def test_scope_count_parity_alone_does_not_prove_geometry(tmp_path, mutation):
    """A valid entity count must not hide geometric changes."""
    assert metadata.version('ezdwg') == '0.17.0'
    original = _source_with_modelspace_and_block_polyline(tmp_path)
    native = ezdwg.read(str(original))
    out = tmp_path / 'public-scoped.dxf'
    result = ezdwg.to_dxf(
        native.modelspace(), str(out), types='POLYLINE_2D',
        modelspace_only=True, preserve_colors=False, strict=True)
    doc = ezdxf.readfile(str(out))
    baseline = _scoped_geometry_fingerprint(doc)
    expected = (
        ('0', True, (
            (0.0, 0.0, 0.0, 0.0, 0.0),
            (4.0, 0.0, 0.0, 0.0, 0.5),
            (4.0, 3.0, 0.0, 0.0, -0.25),
        ), 0.0),
    )
    assert result.written_entities == 1
    assert baseline == expected
    poly = list(doc.modelspace().query('LWPOLYLINE'))[0]
    points = list(poly.get_points('xyseb'))
    if mutation == 'x':
        points[0] = (points[0][0] + 0.5, *points[0][1:])
    elif mutation == 'precision':
        points[1] = (points[1][0] - 0.0001, *points[1][1:])
    elif mutation == 'elevation':
        poly.dxf.elevation = 0.5
    elif mutation == 'width':
        points[0] = (*points[0][:2], 0.25, *points[0][3:])
    elif mutation == 'bulge':
        points[1] = (*points[1][:4], 0.0)
    elif mutation == 'order':
        points = points[1:] + points[:1]
    elif mutation == 'closure':
        poly.closed = False
    if mutation not in ('closure', 'elevation'):
        poly.set_points(points, format='xyseb')
    altered = _scoped_geometry_fingerprint(doc)
    assert len(altered) == len(baseline) == 1
    assert sum(len(poly[2]) for poly in altered) == 3
    assert altered != expected, 'Same count must not bypass geometric parity'
    # The synthetic test does not establish independent original-DWG semantics.
