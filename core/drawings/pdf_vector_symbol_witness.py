"""Conservative vector witness for compact symbols near PDF drawing grid nodes.

This detects a compact repeated *drawing mark*, not a physical member.  A
recognized column-layout title can prioritize a review candidate; it still
cannot prove a member count, type, floor, dimensions, or payable quantity.
Supports stroked fragmented SHX/PDF line symbols without OCR or network APIs.
"""
from __future__ import annotations

from collections import defaultdict
from math import hypot, isfinite
import re
import unicodedata
from typing import Any, Iterable, Mapping


_MAX_SEGMENTS = 150_000


def sheet_context_hint(text: str) -> str:
    """Report only explicit heading clues (including Arabic presentation forms)."""
    s = unicodedata.normalize('NFKC', str(text or '')).casefold()
    s = re.sub(r'[ـ\u200b\u200c\u200d\u064b-\u065f]', '', s)
    s = re.sub(r'\s+', ' ', s)
    if (('ستون' in s or re.search(r'\bcolumns?\b', s)) and
            ('پلان' in s or re.search(r'\b(plan|layout)\b', s))):
        return 'COLUMN_LAYOUT_TITLE_CANDIDATE'
    return 'SHEET_CONTEXT_UNVERIFIED'


def _compact_segments(page) -> tuple[list[tuple[float, float, float, float, float]], list]:
    """Return short orthogonal strokes and tiny rectangles, never long axes."""
    strokes = []
    rectangles = []
    for drawing in page.get_drawings():
        if drawing.get('type') not in ('s', 'fs'):
            continue
        for item in drawing.get('items') or ():
            if item[0] == 're':
                rect = item[1]
                vals = (rect.x0, rect.y0, rect.x1, rect.y1)
                if all(isfinite(v) for v in vals) and 3.0 <= rect.width <= 12.0 and 3.0 <= rect.height <= 12.0:
                    rectangles.append((float(rect.x0),float(rect.y0),float(rect.x1),float(rect.y1)))
            if item[0] != 'l':
                continue
            a, b = item[1:3]
            x0,y0,x1,y1 = float(a.x),float(a.y),float(b.x),float(b.y)
            if not all(map(isfinite, (x0,y0,x1,y1))):
                continue
            length=hypot(x1-x0,y1-y0)
            if not 2.35 <= length <= 9.0:
                continue
            if abs(y1-y0) <= 0.20:
                strokes.append((x0,y0,x1,y1,0.0))
            elif abs(x1-x0) <= 0.20:
                strokes.append((x0,y0,x1,y1,1.0))
            if len(strokes) + len(rectangles) > _MAX_SEGMENTS:
                raise ValueError('PDF vector compact symbol inventory exceeds safe limit')
    return strokes, rectangles


def _distinct_positions(values: list[float], separation: float = 1.20) -> list[float]:
    out=[]
    for value in sorted(values):
        if not out or value - out[-1] >= separation:
            out.append(value)
    return out


def compact_symbol_witness(page, nodes: Iterable[Mapping[str, Any]], *, sheet_text: str | None = None) -> dict:
    """Attach audit-only local graphic witness to existing grid positions.

    The caller must independently determine that nodes are supported by a grid.
    This function never promotes an unverified node to a confirmed member.
    """
    nodes=list(nodes)
    if not nodes:
        return {'sheet_context': sheet_context_hint(sheet_text or ''),
                'symbol_candidate_count': 0, 'column_context_candidates': 0,
                'nodes': [], 'physical_member_count': None, 'complete': False}
    context = sheet_context_hint(page.get_text('text') if sheet_text is None else sheet_text)
    strokes, rectangles = _compact_segments(page)
    results=[]
    for node in nodes:
        x,y = float(node['x_pt']),float(node['y_pt'])
        if not all(map(isfinite,(x,y))):
            raise ValueError('grid position not finite')
        # Endpoint restriction prevents long axis/grid strokes from becoming
        # local symbol evidence merely because they cross the node.
        local=[s for s in strokes if max(abs(s[0]-x),abs(s[1]-y),abs(s[2]-x),abs(s[3]-y)) <= 8.0]
        horizontal=[s for s in local if s[4]==0.0]
        vertical=[s for s in local if s[4]==1.0]
        hx = _distinct_positions([s[1] for s in horizontal])
        vx = _distinct_positions([s[0] for s in vertical])
        rects=[r for r in rectangles if max(abs(r[0]-x),abs(r[1]-y),abs(r[2]-x),abs(r[3]-y))<=8.0]
        has_frame=(len(hx)>=2 and len(vx)>=2 and
                   hx[-1]-hx[0]>=2.0 and vx[-1]-vx[0]>=2.0)
        witness=bool(has_frame or rects)
        status=('COMPACT_VECTOR_SYMBOL_CANDIDATE' if witness
                else 'NO_COMPACT_SYMBOL_EVIDENCE')
        # Even a compact square on a plan can be a marker, note or table icon.
        node_copy=dict(node)
        node_copy.update({
            'symbol_status': status,
            'sheet_context': context,
            'column_context_candidate': witness and context=='COLUMN_LAYOUT_TITLE_CANDIDATE',
            'symbol_witness': {
                'horizontal_strokes': len(horizontal),
                'vertical_strokes': len(vertical),
                'explicit_compact_rectangles': len(rects),
                'short_horizontal_levels': len(hx),
                'short_vertical_positions': len(vx),
            },
            'type_verified': False,
            'physical_member_verified': False,
            'quantity_approved': False,
            'financially_payable': False,
        })
        results.append(node_copy)
    return {'sheet_context': context,
            'symbol_candidate_count': sum(n['symbol_status']=='COMPACT_VECTOR_SYMBOL_CANDIDATE' for n in results),
            'column_context_candidates': sum(n['column_context_candidate'] for n in results),
            'nodes': results, 'physical_member_count': None, 'complete': False}