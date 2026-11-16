"""Nonfinancial source-bound review of printed beam end markers and detail type names.

A filled PDF square is a plan symbol, NOT proof of a structural support,
connection, construction level, section, fabrication length or physical member.
All outputs are review-only. No DB, BOQ, price or member quantity is produced.
"""
from __future__ import annotations

from hashlib import sha256
import json
from math import isfinite
import re


def load_pdf_beam_connection_detail_witnesses(path):
    """Load a bounded local, visual, nonfinancial connection-detail review JSON."""
    from pathlib import Path
    source = Path(path)
    if source.stat().st_size > 65536:
        raise ValueError('Beam connection detail JSON exceeds review budget')
    records = json.loads(source.read_text(encoding='utf-8-sig'))
    if not isinstance(records, list) or len(records) > 128:
        raise ValueError('Beam connection detail JSON must be a bounded array')
    return records


def _id(*items):
    return 'BEAM_END_REVIEW:' + sha256(json.dumps(items, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf8')).hexdigest()[:32]


def _rect(b):
    if not isinstance(b, (tuple, list)) or len(b) != 4 or any(type(v) not in (int, float) or not isfinite(v) for v in b):
        return None
    return tuple(map(float, b)) if b[0] < b[2] and b[1] < b[3] else None


def _source_ok(source):
    return isinstance(source, dict) and (isinstance(source.get('source_name'), str)
            and bool(source['source_name']) and isinstance(source.get('document_id'), str)
            and bool(source['document_id']) and type(source.get('page')) is int and source['page'] > 0
            and isinstance(source.get('source_sha256'), str)
            and bool(re.fullmatch('[a-f0-9]{64}', source['source_sha256'])))


def extract_pdf_beam_end_markers(page, *, document_id, page_number, source_name, source_sha256,
                                 grid=None, max_drawings=10000):
    """Inventory independently drawn, black filled square candidates on beam-layout grid.

    Exact coincident filled glyph operators are evidence alternatives, not
    separate supports. Missing or ambiguous grid fails closed. Only PDF points.
    """
    source = dict(document_id=document_id, page=page_number, source_name=source_name,
                  source_sha256=source_sha256)
    if not _source_ok(source):
        raise ValueError('Unbound source for filled-square marker inspection')
    result = {**source, 'status': 'BLOCKED_NO_INDEPENDENT_GRID', 'marker_candidates': [],
              'source_drawings_examined': 0, 'coordinate_space': 'unrotated_pdf_points',
              'physical_support_count': None, 'beam_count': None,
              'financially_payable': False}
    if page.rotation != 0:
        result['status'] = 'BLOCKED_ROTATED_BEAM_PLAN'
        return result
    if (not isinstance(grid, dict) or grid.get('status') != 'PROPOSED_UNLABELED_AXIS_GRID'
            or any(source[k] != grid.get(k) for k in ('document_id', 'source_name', 'source_sha256'))):
        return result
    xx, yy = grid.get('grid_x_pt'), grid.get('grid_y_pt')
    if (not isinstance(xx, list) or not isinstance(yy, list)
            or not 3 <= len(xx) <= 12 or not 2 <= len(yy) <= 12
            or any(type(v) not in (int, float) or not isfinite(v) for v in [*xx, *yy])
            or any(b-a < 20 for axis in (xx, yy) for a, b in zip(axis, axis[1:]))):
        raise ValueError('Invalid independent axis grid')
    drawings = page.get_drawings()
    if len(drawings) > max_drawings:
        result['status'] = 'BLOCKED_MARKER_DRAWING_BUDGET'
        return result
    result['source_drawings_examined'] = len(drawings)
    collected = {}
    for dindex, drawing in enumerate(drawings):
        if drawing.get('fill') is None or drawing.get('type') not in ('f', 'fs'):
            continue
        fill = drawing['fill']
        if len(fill) != 3 or max(abs(float(c)) for c in fill) > .1:
            continue
        rect = drawing.get('rect')
        if rect is None:
            continue
        box = _rect([rect.x0, rect.y0, rect.x1, rect.y1])
        if box is None:
            continue
        w, h = box[2] - box[0], box[3] - box[1]
        # Filled CAD square glyphs can be 2 coincident outlines or split into
        # two filled half-squares at a crossing. Exact candidate area is the
        # union of fragments, NEVER the number of fill operators.
        if not (1 <= w <= 8 and 1 <= h <= 8):
            continue
        cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
        columns = [i for i, x in enumerate(xx) if abs(x-cx) <= 4]
        rows = [i for i, y in enumerate(yy) if abs(y-cy) <= 4]
        if len(columns) != 1 or len(rows) != 1:
            continue
        col, row = columns[0], rows[0]
        if not (xx[col]-7 <= box[0] <= box[2] <= xx[col]+7 and
                yy[row]-7 <= box[1] <= box[3] <= yy[row]+7):
            continue
        key = (row, col)
        collected.setdefault(key, []).append((box, f'{document_id}:p{page_number}:drawing{dindex}'))
    for (row, col), members in sorted(collected.items()):
        box = (min(v[0][0] for v in members), min(v[0][1] for v in members),
               max(v[0][2] for v in members), max(v[0][3] for v in members))
        w, h = box[2]-box[0], box[3]-box[1]
        coherent = (4 <= w <= 8 and 4 <= h <= 8 and abs(w-h) <= 1.25
                    and abs((box[0]+box[2])/2-xx[col]) <= 3.2
                    and abs((box[1]+box[3])/2-yy[row]) <= 3.2)
        refs = sorted({ref for _, ref in members})
        candidate = {**source, 'candidate_id': _id(source_sha256, page_number, row, col, refs),
                     'source_refs': refs, 'source_operator_count': len(refs),
                     'bbox_pt': list(box), 'grid_row_index': row, 'grid_column_index': col,
                     'status': 'PROPOSED_GRID_SQUARE_MARK' if coherent else 'BLOCKED_COMPETING_SQUARE_MARKS',
                     'symbol_kind': 'BLACK_FILLED_SQUARE', 'physical_support_verified': False,
                     'connection_detail_verified': False, 'financially_payable': False}
        result['marker_candidates'].append(candidate)
    result['status'] = 'PROPOSED_UNVERIFIED_SQUARE_MARKERS'
    result['marker_count'] = len(result['marker_candidates'])
    result['duplicate_source_strokes'] = sum(max(0,c['source_operator_count']-1) for c in result['marker_candidates'])
    return result


def review_beam_ends_against_independent_grid(markers, grid, axis_labels, profile_witnesses,
                                              detail_profile_witnesses=(), *, detail_page=None):
    """Witness BOTH axis-end squares per profile and optionally a matching type in a detail.

    A matching label in a generic connection detail is never a span-specific
    callout. All returned decisions retain unproven supports, detail, level and
    installed lengths. Does not infer construction quantities.
    """
    if (not isinstance(markers, dict) or markers.get('status') != 'PROPOSED_UNVERIFIED_SQUARE_MARKERS'
            or grid.get('status') != 'PROPOSED_UNLABELED_AXIS_GRID'
            or any(markers.get(k) != grid.get(k) for k in ('source_sha256','source_name','document_id'))
            or axis_labels.get('source_sha256') != grid.get('source_sha256')
            or axis_labels.get('document_id') != grid.get('document_id')
            or axis_labels.get('page') != grid.get('page')
            or axis_labels.get('beam_page') != markers.get('page')
            or axis_labels.get('source_method') != 'VISUALLY_REVIEWED_AXIS_LABELS'
            or axis_labels.get('financially_payable') is not False):
        raise ValueError('Missing original axis or beam-plan provenance')
    letters = axis_labels.get('horizontal_letters')
    rows = axis_labels.get('rows_top_to_bottom')
    if (not isinstance(letters, list) or not isinstance(rows, list) or
            len(letters) != len(grid['grid_x_pt']) or len(rows) != len(grid['grid_y_pt']) or
            len(set(letters)) != len(letters) or len(set(rows)) != len(rows) or
            any(not isinstance(v, str) or not re.fullmatch('[A-Z]',v) for v in letters) or
            any(not isinstance(v, str) or not re.fullmatch('[1-9][0-9]{0,2}',v) for v in rows)):
        raise ValueError('Invalid independently reviewed axis names')
    if (not isinstance(profile_witnesses, list) or len(profile_witnesses) > 256 or
            not isinstance(detail_profile_witnesses, (list, tuple)) or len(detail_profile_witnesses) > 128):
        raise ValueError('Unbounded beam observation set')
    by_grid = {}
    for mark in markers['marker_candidates']:
        key = (mark['grid_row_index'], mark['grid_column_index'])
        by_grid.setdefault(key, []).append(mark)
    if detail_profile_witnesses:
        pages = {w.get('page') for w in detail_profile_witnesses if isinstance(w,dict)}
        if len(pages) != 1 or any(type(p) is not int or p < 1 for p in pages):
            raise ValueError('Ambiguous detail-page source identity')
        unique_page = next(iter(pages))
        if detail_page is None:
            detail_page = unique_page
        elif detail_page != unique_page:
            raise ValueError('Detailed PDF page identity mismatch')
    details = {}
    for witness in detail_profile_witnesses:
        if not isinstance(witness, dict) or witness.get('source_sha256') != grid['source_sha256'] or (
                witness.get('document') != grid['source_name'] or witness.get('page') != detail_page or
                witness.get('source_method') != 'VISUAL_CAD_STROKES_PRIVATE_RENDER' or
                witness.get('financially_payable') is not False or witness.get('source_visual_confidence') not in ('VISIBLE','REVIEW_REQUIRED') or
                _rect(witness.get('bbox_pt')) is None or
                witness.get('governing_detail_id') is not None or witness.get('verified_length_m') is not None):
            raise ValueError('Foreign, unsupported or payable connection detail visual witness')
        label = witness.get('profile_text_normalized')
        raw = witness.get('profile_text_raw')
        if (not isinstance(raw,str) or not isinstance(label,str) or
                re.sub(r'\s+','',raw.upper()) != label or not re.fullmatch('[1-4]?C?IPE[0-9]{1,3}',label)):
            raise ValueError('Unverified rendered connection profile string')
        details.setdefault(label,[]).append(witness)
    results = []
    observed = set()
    for witness in profile_witnesses:
        if (not isinstance(witness, dict) or witness.get('source_sha256') != grid['source_sha256'] or
                witness.get('document') != grid['source_name'] or witness.get('page') != markers['page'] or
                witness.get('source_method') != 'VISUAL_CAD_STROKES_PRIVATE_RENDER' or
                witness.get('financially_payable') is not False or witness.get('source_visual_confidence') not in ('VISIBLE','REVIEW_REQUIRED') or
                _rect(witness.get('bbox_pt')) is None or witness.get('verified_length_m') is not None or
                witness.get('governing_detail_id') is not None or witness.get('verified_cut_quantity') is not None):
            raise ValueError('Unbound beam profile source')
        axes, row_name, token = witness.get('span_axes'), witness.get('printed_axis_row'), witness.get('profile_text_normalized')
        box = _rect(witness['bbox_pt'])
        raw_token = witness.get('profile_text_raw')
        if (not isinstance(raw_token,str) or not isinstance(token,str)
                or re.sub(r'\s+','',raw_token.upper()) != token
                or not re.fullmatch('[1-4]?C?IPE[0-9]{1,3}',token)):
            raise ValueError('Invalid source-bound beam profile glyph transcription')
        identity = (box,axes,row_name)
        if identity in observed:
            raise ValueError('Duplicate beam end review source')
        observed.add(identity)
        try:
            left_name, right_name = axes.split('-')
            i, j, k = letters.index(left_name), letters.index(right_name), rows.index(row_name)
        except (ValueError, AttributeError):
            i=j=k=-1
        axis_consistent = i >= 0 and j == i+1 and k >= 0
        ends = [by_grid.get((k,i), []),by_grid.get((k,j), [])] if axis_consistent else [[],[]]
        unique = axis_consistent and len(ends[0])==1 and len(ends[1])==1
        mark_ok = unique and all(x[0]['status']=='PROPOSED_GRID_SQUARE_MARK' for x in ends)
        dx = grid['grid_x_pt']
        cy = (box[1]+box[3])/2
        cx = (box[0]+box[2])/2
        center_consistent = bool(axis_consistent and dx[i] <= cx <= dx[j] and
                                 abs(cy-grid['grid_y_pt'][k]) < .25 * min(
                                     b-a for a,b in zip(grid['grid_y_pt'],grid['grid_y_pt'][1:])))
        detail_options = details.get(token,[]) if isinstance(token,str) else []
        if not center_consistent:
            status='BLOCKED_PROFILE_GRID_POSITION'
        elif not unique:
            status='BLOCKED_MISSING_OR_AMBIGUOUS_ENDPOINT_SYMBOL'
        elif not mark_ok:
            status='BLOCKED_COMPETING_ENDPOINT_SYMBOL'
        elif witness['source_visual_confidence']!='VISIBLE':
            status='BLOCKED_PROFILE_GLYPH_UNCERTAIN'
        else:
            status='PROPOSED_BOTH_END_GRID_SYMBOLS'
        if not detail_options:
            detail_status='NO_SAME_TYPE_CONNECTION_DETAIL_WITNESS'
        elif len(detail_options)>1:
            detail_status='MULTIPLE_SAME_TYPE_CONNECTION_DETAIL_WITNESSES'
        else:
            detail_status='PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC'
        result={
            'review_id':_id(grid['source_sha256'],markers['page'],identity),
            'source_sha256':grid['source_sha256'],'document_id':markers['document_id'],
            'beam_page':markers['page'],'axis_page':grid['page'],'detail_page':detail_page,
            'span_axes':axes,'printed_axis_row':row_name,'profile_text':token,
            'status':status,'detail_status':detail_status,'candidate_detail_count':len(detail_options),
            'endpoint_symbol_candidates':[len(ends[0]),len(ends[1])],
            'endpoint_marker_ids':[end[0]['candidate_id'] if len(end)==1 else None for end in ends],
            'plan_profile_bbox_pt':list(box),'detail_bbox_candidates_pt':[list(_rect(d['bbox_pt'])) for d in detail_options],
            'missing_evidence':['PROVEN_SUPPORT_MEMBER_AND_CONNECTION','EXPLICIT_DETAIL_CALLOUT_FOR_THIS_SPAN',
                                'GOVERNING_REVISION','INSTALLATION_LEVEL','CUT_LENGTH','MEASUREMENT_UNIT'],
            'physical_member_verified':False,'support_verified':False,'detail_link_verified':False,
            'member_quantity':None,'verified_installed_length':None,'financially_payable':False,
        }
        results.append(result)
    return {'status':'REVIEW_REQUIRED_NONFINANCIAL','source_sha256':grid['source_sha256'],
            'beam_page':markers['page'],'axis_page':grid['page'],'detail_page':detail_page,
            'marker_candidates':len(markers['marker_candidates']),
            'both_end_marker_proposals':sum(r['status']=='PROPOSED_BOTH_END_GRID_SYMBOLS' for r in results),
            'blocked':sum(r['status'].startswith('BLOCKED') for r in results),
            'profiles':results,'physical_member_verified_count':0,'financially_payable':False}