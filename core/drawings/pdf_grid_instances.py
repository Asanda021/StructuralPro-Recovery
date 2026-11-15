"""Evidence-only extraction of potential member locations at vector grid nodes.

A structural drawing may contain a grid whose nodes carry column symbols, but
an orthogonal table is not a building. Neither geometric intersections nor
adjacent text prove the presence/count/type of a physical structural member.
Every output therefore remains a NON-PAYABLE, UNVERIFIED location candidate.
No scale, floor replication or material quantity is inferred.
"""
from __future__ import annotations

from collections import defaultdict
from math import dist, isfinite
from typing import Iterable, Mapping

from core.drawings.pdf_type_word_witness import unrotated_page_bounds


def _merged(values: Iterable[float], eps: float = 0.9) -> list[float]:
    groups: list[list[float]] = []
    for value in sorted(set(round(float(v), 3) for v in values)):
        if not isfinite(value):
            continue
        if groups and abs(value - groups[-1][-1]) <= eps:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [sum(group) / len(group) for group in groups]


def _segment_evidence(page) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
    """Extract long stroked axis-aligned vector segments in PDF page points."""
    bounds = unrotated_page_bounds(page)
    width, height = float(bounds.width), float(bounds.height)
    if not (width > 0 and height > 0):
        return [], []
    min_vertical = max(34.0, height * 0.18)
    min_horizontal = max(32.0, width * 0.048)
    vertical, horizontal = [], []
    for path in page.get_drawings():
        # Filled glyph outlines are deliberately excluded from structural axes.
        if path.get('type') not in ('s', 'fs'):
            continue
        for segment in path.get('items') or ():
            if not segment or segment[0] != 'l':
                continue
            start, end = segment[1:3]
            x0, y0, x1, y1 = start.x, start.y, end.x, end.y
            if not all(isfinite(float(v)) for v in (x0, y0, x1, y1)):
                continue
            if abs(x0-x1) <= 0.15 and abs(y0-y1) >= min_vertical:
                vertical.append(((x0+x1)/2, min(y0, y1), max(y0, y1)))
            elif abs(y0-y1) <= 0.15 and abs(x0-x1) >= min_horizontal:
                horizontal.append(((y0+y1)/2, min(x0, x1), max(x0, x1)))
    return vertical, horizontal


def _group_verticals(lines: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    # Collapsed parallel-double strokes represent one axis, not extra columns.
    groups = []
    for item in sorted(lines):
        if groups and abs(item[0]-groups[-1][-1][0]) <= 6.3 and (
                min(item[2], groups[-1][0][2]) - max(item[1], groups[-1][0][1]) > 40.0):
            groups[-1].append(item)
        else:
            groups.append([item])
    return [(sum(row[0] for row in group)/len(group),
             min(row[1] for row in group), max(row[2] for row in group))
            for group in groups]


def _matching_y(vertical: tuple[float, float, float], horizontal: list[tuple[float, float, float]],
                *, x_tolerance: float = 8.0) -> list[float]:
    x, start, end = vertical
    supported = [y for y, left, right in horizontal
                 if start-1.0 <= y <= end+1.0 and left-x_tolerance <= x <= right+x_tolerance]
    return _merged(supported, eps=6.3)


def _common_levels(seeds: list[list[float]], eps: float = 6.3) -> list[float]:
    if not seeds:
        return []
    return [val for val in seeds[0] if all(any(abs(val - other) <= eps for other in row)
                                           for row in seeds[1:])]


def _nearby_type_marks(x: float, y: float, marks: Iterable[Mapping], max_distance: float):
    seen = []
    for mark in marks:
        bbox = mark.get('bbox')
        if not bbox or len(bbox) != 4 or not mark.get('tag'):
            continue
        center = ((bbox[0]+bbox[2])/2, (bbox[1]+bbox[3])/2)
        separation = dist((x, y), center)
        if separation <= max_distance:
            seen.append((separation, str(mark['tag']), tuple(bbox)))
    seen.sort(key=lambda item: (item[0], item[1]))
    return seen


def detect_vector_grid_positions(page, *, document_id: str, page_number: int,
                                 text_type_marks: Iterable[Mapping] = (),
                                 max_nodes: int = 2000) -> dict:
    """Find repeated grid *positions*, not verified members or payable counts.

    For a conventional orthogonal grid, require >=3 long vertical axes, >=3
    independently supported horizontal levels, substantial shared span, and
    support along every axis. Excludes isolated dimensions/title boxes on the
    tested geometry; returns no grid if the evidence is not conclusive.
    """
    if type(page_number) is not int or page_number < 1 or not document_id.strip():
        raise ValueError('source document and page required')
    if type(max_nodes) is not int or max_nodes < 1:
        raise ValueError('positive bounded max_nodes required')
    vertical, horizontal = _segment_evidence(page)
    axes = _group_verticals(vertical)
    # Dense parallel strokes usually come from a hatch, bar pattern or table.
    # Do not turn those drawing ornaments into dozens of member locations.
    if axes and len(vertical) > 4 * len(axes):
        return {'status': 'BLOCKED_DENSE_VECTOR_PATTERN', 'axes_x_pt': [], 'levels_y_pt': [], 'nodes': []}
    if len(axes) < 3 or len(horizontal) < 3:
        return {'status': 'NO_GRID_EVIDENCE', 'axes_x_pt': [], 'levels_y_pt': [], 'nodes': []}
    bounds = unrotated_page_bounds(page)
    width, height = float(bounds.width), float(bounds.height)
    tol = max(6.0, min(8.5, width*0.01))
    axis_support = [(axis, _matching_y(axis, horizontal, x_tolerance=tol)) for axis in axes]
    axis_support = [(axis, ys) for axis, ys in axis_support if len(ys) >= 3]
    candidates = []
    for seed, sy in axis_support:
        selected = [(axis, ys) for axis, ys in axis_support
                    if len(_common_levels([sy, ys])) >= 3]
        if len(selected) < 3:
            continue
        shared = _common_levels([ys for _, ys in selected])
        xx = sorted(x[0] for x, _ in selected)
        yy = _merged(shared, eps=6.3)
        # Reject closely spaced hatch strokes/rebar grids masquerading as
        # column-axis intersections. Such pages remain unresolved.
        if len(xx) < 3 or len(yy) < 3:
            continue
        min_dx = min(xx[k+1]-xx[k] for k in range(len(xx)-1))
        min_dy = min(yy[k+1]-yy[k] for k in range(len(yy)-1))
        if min_dx < max(25.0, width*0.04) or min_dy < max(25.0, height*0.04):
            continue
        if (len(xx) < 3 or len(yy) < 3 or
                xx[-1]-xx[0] < max(60.0, width*0.10) or
                yy[-1]-yy[0] < max(90.0, height*0.24)):
            continue
        if len(xx) * len(yy) > max_nodes:
            continue
        score = len(xx)*len(yy)*(xx[-1]-xx[0])*(yy[-1]-yy[0])
        candidates.append((score, xx, yy))
    if not candidates:
        return {'status': 'NO_GRID_EVIDENCE', 'axes_x_pt': [], 'levels_y_pt': [], 'nodes': []}
    _, xx, yy = max(candidates, key=lambda item: item[0])
    # The area MAY be a table. A nearby textual mark is only a suggestion,
    # never a physical member instance classification.
    spacing = min(min(xx[j+1]-xx[j] for j in range(len(xx)-1)),
                  min(yy[j+1]-yy[j] for j in range(len(yy)-1)))
    radius = min(26.0, 0.35 * spacing)
    marks = list(text_type_marks)
    nodes = []
    for row, y in enumerate(yy, 1):
        for col, x in enumerate(xx, 1):
            matches = _nearby_type_marks(x, y, marks, max_distance=radius)
            unique = sorted(set(item[1] for item in matches))
            suggested = unique[0] if len(unique) == 1 else None
            status = ('GRID_LOCATION_TYPE_TEXT_CANDIDATE' if suggested else
                      'BLOCKED_MULTIPLE_NEARBY_TYPES' if unique else
                      'GRID_LOCATION_TYPE_UNKNOWN')
            nodes.append({
                'candidate_id': f'{document_id}:p{page_number}:r{row}:c{col}',
                'document_id': document_id, 'page': page_number,
                'row': row, 'column': col,
                'x_pt': round(x, 3), 'y_pt': round(y, 3),
                'status': status, 'suggested_type': suggested,
                'nearby_text_type_evidence': [{'tag': item[1], 'bbox_pt': item[2]}
                                              for item in matches],
                'type_verified': False, 'physical_member_verified': False,
                'quantity_approved': False, 'financially_payable': False,
                'source_class': 'UNCLASSIFIED_ORTHOGONAL_GRID',
            })
    return {'status': 'VECTOR_GRID_LOCATION_CANDIDATES',
            'axes_x_pt': [round(x, 3) for x in xx],
            'levels_y_pt': [round(y, 3) for y in yy],
            'nodes': nodes, 'physical_member_count': None,
            'quantity_approval_count': 0, 'complete': False}
