"""Fail-closed PDF sheet-title scope and cross-sheet structural-axis registration.

Proves that two vector grids correspond geometrically on the printed pages;
never proves a floor repetition, physical column, member dimensions, scale,
source revision precedence, or a billable amount. No third-party OCR is used.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite
import unicodedata
from typing import Iterable, Mapping


def _title_key(raw: str) -> str:
    """Normalize Persian text and PDF Arabic presentation forms for *title* checks."""
    text = unicodedata.normalize('NFKC', str(raw or ''))
    text = text.replace('ـ', '').replace('\u200c', '')
    text = text.translate(str.maketrans({'ي': 'ی', 'ى': 'ی', 'ك': 'ک', 'ة': 'ه', 'ۀ': 'ه'}))
    return ''.join(char for char in text.casefold() if char.isalnum())


def classify_sheet_title(raw: str) -> dict:
    """Classify explicit sheet titles, not quantities or floor count.

    False / multi-class matches become unknown/ambiguous rather than guessed.
    Floor plan titles are *not* evidence that column marks recur on each floor.
    """
    key = _title_key(raw)
    known = []
    if 'پلان' in key or 'plan' in key:
        if 'آکسبندی' in key or 'اکسبندی' in key or 'axisplan' in key:
            known.append('axis_plan')
        if ('ستون' in key and ('تیپ' in key or 'تیپبندی' in key)) or 'columntypeplan' in key:
            known.append('column_type_plan')
        if 'فنداسیون' in key or 'پی سازی' in str(raw) or 'پیسازی' in key or 'foundationplan' in key:
            known.append('foundation_plan')
        if 'قالببندی' in key or 'formworkplan' in key:
            known.append('formwork_plan')
        if 'تیرریزی' in key or 'beamlayoutplan' in key:
            known.append('beam_layout_plan')
        if 'پیلوت' in key or 'pilotfloorplan' in key:
            known.append('pilot_floor_plan')
        if 'طبقههمکف' in key or 'groundfloorplan' in key:
            known.append('ground_floor_plan')
        if ('طبقه' in key and 'اول' in key) or 'firstfloorplan' in key:
            known.append('first_floor_plan')
        if 'آبروبام' in key or 'roofdrainageplan' in key:
            known.append('roof_drainage_plan')
    if ('جزئیات' in key or 'جزییات' in key or 'details' in key) and 'ستون' in key:
        known.append('column_detail')
    distinct = sorted(set(known))
    if len(distinct) == 1:
        status, kind = 'EXPLICIT_SHEET_TITLE', distinct[0]
    elif distinct:
        status, kind = 'BLOCKED_MULTIPLE_TITLE_CLASSES', None
    else:
        status, kind = 'UNKNOWN_TITLE', None
    return {'status': status, 'sheet_kind': kind, 'title_classes': distinct,
            'floor_instance_repetition_verified': False,
            'floor_instance_multiplier': None,
            'financially_payable': False}


def _points(grid: Mapping) -> tuple[list[float], list[float]] | None:
    """Return one coherent monotonic 3x3+ grid or None."""
    xx, yy = grid.get('axes_x_pt'), grid.get('levels_y_pt')
    if not isinstance(xx, (list, tuple)) or not isinstance(yy, (list, tuple)):
        return None
    if not (3 <= len(xx) <= 60 and 3 <= len(yy) <= 60):
        return None
    if any(type(v) not in (float, int) or not isfinite(v) for v in [*xx,*yy]):
        return None
    xs, ys = list(map(float, xx)), list(map(float, yy))
    if any(b-a < 25.0 for a,b in zip(xs,xs[1:])) or any(b-a < 25.0 for a,b in zip(ys,ys[1:])):
        return None
    return xs, ys


def _alignment(column_grid: Mapping, axis_grid: Mapping, *, tolerance_pt: float = 3.0) -> dict | None:
    """Strict orientation-preserving, translation-only correspondence.

    No scale, shear, mirroring, rotation or nearest-subgrid guess is allowed.
    """
    c, a = _points(column_grid), _points(axis_grid)
    if c is None or a is None or len(c[0]) != len(a[0]) or len(c[1]) != len(a[1]):
        return None
    if not (0 <= tolerance_pt <= 5):
        raise ValueError('bounded page-points tolerance required')
    cx, cy = c; ax, ay = a
    dx = sum(x-y for x,y in zip(cx,ax)) / len(cx)
    dy = sum(x-y for x,y in zip(cy,ay)) / len(cy)
    errors = [abs((x-y)-dx) for x,y in zip(cx,ax)] + [abs((x-y)-dy) for x,y in zip(cy,ay)]
    worst = max(errors)
    if worst > tolerance_pt:
        return None
    return {'translation_pt': (round(dx,3),round(dy,3)),
            'max_residual_pt': round(worst,3),
            'grid_shape': [len(cx),len(cy)]}


def register_column_grid_against_axes(
    grids: Iterable[Mapping], sheet_summaries: Iterable[Mapping], *, tolerance_pt: float = 3.0,
) -> dict:
    """Corroborate column plan grid with independently titled axis plan.

    Matches are always non-payable. An ambiguous choice between multiple axis
    sheets is blocked even if geometry is identical. Mixed document IDs are
    not automatically equated because their revisions are unknown.
    """
    views = {(s.get('document_id'), s.get('page')):s for s in sheet_summaries}
    structural = [g for g in grids if g.get('status') == 'VECTOR_GRID_LOCATION_CANDIDATES'
                  and _points(g)]
    axes = [g for g in structural if views.get((g.get('document_id'), g.get('page')),{}).get('sheet_kind') == 'axis_plan'
            and views[(g['document_id'],g['page'])].get('status')=='EXPLICIT_SHEET_TITLE']
    columns = [g for g in structural if views.get((g.get('document_id'), g.get('page')),{}).get('sheet_kind') == 'column_type_plan'
               and views[(g['document_id'],g['page'])].get('status')=='EXPLICIT_SHEET_TITLE']
    results=[]
    for col in sorted(columns,key=lambda v:(str(v.get('document_id')),int(v.get('page')))):
        options=[]
        for axis in axes:
            if (axis['document_id'] != col['document_id'] or axis['page']==col['page']):
                continue
            fit=_alignment(col,axis,tolerance_pt=tolerance_pt)
            if fit is not None:
                options.append((axis,fit))
        if len(options)==1:
            axis,fit=options[0]
            result={'status':'PROPOSED_INDEPENDENT_GRID_REGISTRATION',
                    'column_plan':{'document_id':col['document_id'],'page':col['page']},
                    'axis_plan':{'document_id':axis['document_id'],'page':axis['page']},
                    'grid_shape':fit['grid_shape'],
                    'translation_pt':fit['translation_pt'],
                    'max_residual_pt':fit['max_residual_pt'],
                    'supported_positions':fit['grid_shape'][0]*fit['grid_shape'][1],
                    'verified_physical_member_count':None,
                    'floor_repetitions_verified':False,
                    'approved':False,'financially_payable':False}
        else:
            status='BLOCKED_MULTIPLE_AXES_PLANS' if options else 'BLOCKED_MISSING_MATCHED_AXIS_PLAN'
            result={'status':status,'column_plan':{'document_id':col['document_id'],'page':col['page']},
                    'matching_axis_plan_pages':[x['page'] for x,_ in options],
                    'supported_positions':0,'verified_physical_member_count':None,
                    'floor_repetitions_verified':False,
                    'approved':False,'financially_payable':False}
        results.append(result)
    return {'column_plan_registrations':results,
            'registered_grid_positions':sum(x.get('supported_positions',0) for x in results),
            'accepted_physical_member_count':None,
            'financially_payable':False,
            'complete':False}