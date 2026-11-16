"""Read-only, source-bound PDF grid witnesses and beam label location checks.

Printed dimension chains establish a *paper-points/printed-unit consistency*
check only. They DO NOT establish SI units, fabrication lengths, a governing
revision, member counts or payable BOQ quantities. Axis names must be supplied
with independently reviewed PDF image crops; never infer A-E from line order.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
from statistics import median
import re


def _id(*items):
    raw = json.dumps(items, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return 'BEAM_AXIS:' + sha256(raw.encode('utf-8')).hexdigest()[:32]


def _bbox(b):
    if not isinstance(b, (list, tuple)) or len(b) != 4 or any(type(x) not in (int, float) or not isfinite(x) for x in b):
        return None
    return list(map(float, b)) if b[0] < b[2] and b[1] < b[3] else None


def extract_pdf_axis_grid_witness(page, *, document_id, page_number, source_sha256, source_name):
    """Extract the long, intersecting axis-line *candidates* in PDF points.

    Only pages explicitly classified as axis_plan by the caller are eligible.
    Exact glyphs (A-E, 1-3) are not determined by geometry and remain unverified.
    """
    if not (isinstance(document_id, str) and document_id and isinstance(source_name, str) and source_name
            and type(page_number) is int and page_number > 0
            and isinstance(source_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', source_sha256)):
        raise ValueError('Unbound PDF axis grid source identity')
    if page.rotation != 0:
        return {'status': 'BLOCKED_ROTATED_AXIS_GRID', 'document_id': document_id, 'page': page_number,
                'source_name': source_name, 'source_sha256': source_sha256, 'grid_x_pt': [], 'grid_y_pt': [],
                'financially_payable': False}
    rect = page.rect
    if rect.width <= 0 or rect.height <= 0:
        raise ValueError('Invalid source PDF rectangle')
    vertical, horizontal = [], []
    drawings = page.get_drawings()
    if len(drawings) > 10000:
        return {'status': 'BLOCKED_AXIS_DRAWING_BUDGET', 'document_id': document_id, 'page': page_number,
                'source_name': source_name, 'source_sha256': source_sha256,
                'grid_x_pt': [], 'grid_y_pt': [], 'financially_payable': False}
    count = 0
    for dindex, drawing in enumerate(drawings):
        for index, stroke in enumerate(drawing.get('items', ())):
            count += 1
            if count > 150000:
                return {'status': 'BLOCKED_AXIS_OPERATOR_BUDGET', 'document_id': document_id,
                        'page': page_number, 'source_name': source_name, 'source_sha256': source_sha256,
                        'grid_x_pt': [], 'grid_y_pt': [], 'financially_payable': False}
            if not stroke or stroke[0] != 'l':
                continue
            a, b = stroke[1:3]
            ref = f'{document_id}:p{page_number}:drawing{dindex}:stroke{index}'
            if abs(a.x - b.x) <= .15 and abs(a.y - b.y) >= .25 * rect.height:
                vertical.append((round((a.x + b.x) / 2, 3), min(a.y, b.y), max(a.y, b.y), ref))
            if abs(a.y - b.y) <= .15 and abs(a.x - b.x) >= .25 * rect.width:
                horizontal.append((round((a.y + b.y) / 2, 3), min(a.x, b.x), max(a.x, b.x), ref))
    matched_h = []
    for h in horizontal:
        joins = [v for v in vertical if h[1] - 1 <= v[0] <= h[2] + 1
                 and v[1] - 1 <= h[0] <= v[2] + 1]
        if len({v[0] for v in joins}) >= 2:
            matched_h.append((h, joins))
    xvals = sorted({v[0] for _, vs in matched_h for v in vs})
    yvals = sorted({h[0] for h, _ in matched_h})
    ok = (3 <= len(xvals) <= 12 and 2 <= len(yvals) <= 12
          and all(b - a >= 20 for a, b in zip(xvals, xvals[1:]))
          and all(b - a >= 20 for a, b in zip(yvals, yvals[1:])))
    status = 'PROPOSED_UNLABELED_AXIS_GRID' if ok else 'BLOCKED_AXIS_GRID_AMBIGUOUS'
    xs, ys = (xvals, yvals) if ok else ([], [])
    ref_v = sorted({v[3] for _, vs in matched_h for v in vs}) if ok else []
    ref_h = sorted({h[3] for h, _ in matched_h}) if ok else []
    return {'status': status, 'document_id': document_id, 'page': page_number,
            'source_name': source_name, 'source_sha256': source_sha256,
            'source_bounds_pt': [rect.x0, rect.y0, rect.x1, rect.y1],
            'grid_x_pt': xs, 'grid_y_pt': ys, 'source_operator_refs': ref_v + ref_h,
            'axis_label_witness_status': 'NOT_INFERRED_FROM_LINES',
            'printed_unit': None, 'calibrated_member_length': None,
            'physical_member_count': None, 'financially_payable': False}


def reconcile_pdf_beam_grid_labels(grid, reviewed_labels, profiles):
    """Crosscheck visually transcribed beam labels against independent axes.

    The independently reviewed label mapping and printed dimensions must have
    a source hash matching the extracted axis grid. This is a *location* review
    only; no installed beam lengths or quantities are computed.
    """
    if grid.get('status') != 'PROPOSED_UNLABELED_AXIS_GRID':
        raise ValueError('Axis grid not independently extracted')
    if (reviewed_labels.get('source_sha256') != grid.get('source_sha256')
            or reviewed_labels.get('document_id') != grid.get('document_id')
            or reviewed_labels.get('page') != grid.get('page')
            or reviewed_labels.get('source_method') != 'VISUALLY_REVIEWED_AXIS_LABELS'
            or reviewed_labels.get('financially_payable') is not False
            or reviewed_labels.get('printed_unit') is not None
            or type(reviewed_labels.get('beam_page')) is not int
            or reviewed_labels['beam_page'] == grid['page']
            or reviewed_labels['beam_page'] < 1):
        raise ValueError('Foreign or unsupported axis-name evidence')
    xs, ys = grid['grid_x_pt'], grid['grid_y_pt']
    columns = reviewed_labels.get('horizontal_letters')
    rows = reviewed_labels.get('rows_top_to_bottom')
    if (not isinstance(columns, list) or len(columns) != len(xs)
            or len(set(columns)) != len(columns)
            or any(not isinstance(x, str) or not re.fullmatch('[A-Z]', x) for x in columns)
            or not isinstance(rows, list) or len(rows) != len(ys) or len(set(rows)) != len(rows)
            or any(not isinstance(x, str) or not re.fullmatch('[1-9][0-9]{0,2}', x) for x in rows)):
        raise ValueError('Unverified axis-label count or ordering')
    dx = reviewed_labels.get('printed_horizontal_spacings')
    dy = reviewed_labels.get('printed_vertical_spacings')
    if (not isinstance(dx, list) or len(dx) != len(xs)-1 or
            not isinstance(dy, list) or len(dy) != len(ys)-1 or
            any(type(v) not in (float, int) or not isfinite(v) or v <= 0 for v in dx+dy)):
        raise ValueError('Printed dimension chain missing or invalid')
    ratios = [(b-a)/d for a,b,d in zip(xs,xs[1:],dx)] + [(b-a)/d for a,b,d in zip(ys,ys[1:],dy)]
    scale = median(ratios)
    error = max(abs(r-scale)/scale for r in ratios)
    if error > .01:
        return {'status': 'BLOCKED_PRINTED_DIMENSION_CHAIN_DISAGREEMENT',
                'grid_source_sha256': grid['source_sha256'], 'axis_page': grid['page'],
                'max_scale_disagreement_pct': round(error * 100, 4), 'profiles': [],
                'financially_payable': False}
    if not isinstance(profiles, list) or len(profiles) > 256:
        raise ValueError('Unbounded profile observations')
    output = []
    seen = set()
    for source in profiles:
        box = _bbox(source.get('bbox_pt')) if isinstance(source, dict) else None
        if (not box or source.get('source_sha256') != grid['source_sha256']
                or source.get('page') != reviewed_labels['beam_page']
                or source.get('source_visual_confidence') not in ('VISIBLE', 'REVIEW_REQUIRED')
                or any(source.get(k) is not None for k in ('verified_length_m', 'verified_cut_quantity',
                   'governing_detail_id', 'incident_profile_member_id', 'member_quantity'))
                or source.get('document') != grid['source_name']
                or source.get('source_method') != 'VISUAL_CAD_STROKES_PRIVATE_RENDER'
                or source.get('financially_payable') is not False):
            raise ValueError('Foreign or invalid beam observation')
        try:
            left, right = source['span_axes'].split('-')
            ai = columns.index(left)
            bi = columns.index(right)
            r = rows.index(source['printed_axis_row'])
        except (ValueError, KeyError, AttributeError):
            ai = bi = r = -1
        identity = (source['page'], tuple(round(v, 3) for v in box))
        if identity in seen:
            raise ValueError('Duplicate PDF beam label witness')
        seen.add(identity)
        center_x = (box[0] + box[2]) / 2
        center_y = (box[1] + box[3]) / 2
        nearest_y = min(range(len(ys)), key=lambda k: abs(ys[k]-center_y))
        max_row_gap = .25 * min(ys[k+1]-ys[k] for k in range(len(ys)-1))
        coherent = (ai >= 0 and bi == ai + 1 and r == nearest_y
                    and xs[ai] <= center_x <= xs[bi]
                    and abs(center_y - ys[r]) <= max_row_gap)
        uncertain = source.get('source_visual_confidence') != 'VISIBLE'
        status = ('BLOCKED_AXIS_POSITION_CONFLICT' if not coherent else
                  'BLOCKED_VISUAL_GLYPH_UNCERTAIN' if uncertain else
                  'PROPOSED_INDEPENDENT_AXIS_LOCATION')
        output.append({'review_id': _id(grid['source_sha256'], grid['page'], box,
                                        source.get('span_axes'), source.get('printed_axis_row')),
                       'status': status, 'source_sha256': grid['source_sha256'],
                       'axis_page': grid['page'], 'beam_page': source.get('page'),
                       'span_axes': source.get('span_axes'), 'printed_axis_row': source.get('printed_axis_row'),
                       'profile_text': source.get('profile_text_normalized'),
                       'bbox_pt': box, 'center_pt': [round(center_x, 3), round(center_y, 3)],
                       'axis_row_distance_pt': round(abs(center_y-ys[nearest_y]), 3),
                       'unit_status': 'PRINTED_DIMENSION_UNIT_NOT_VERIFIED',
                       'member_quantity': None, 'verified_installed_length': None,
                       'physical_member_verified': False, 'financially_payable': False})
    return {'status': 'PROPOSED_PAPER_GRID_CONSISTENCY_ONLY',
            'grid_source_sha256': grid['source_sha256'], 'axis_page': grid['page'],
            'pt_per_printed_unit': round(scale, 6),
            'max_scale_disagreement_pct': round(error*100, 4),
            'profiles': output,
            'axis_location_proposals': sum(x['status']=='PROPOSED_INDEPENDENT_AXIS_LOCATION' for x in output),
            'blocked_profile_observations': sum(x['status'].startswith('BLOCKED_') for x in output),
            'physical_member_verified_count': 0, 'financially_payable': False}