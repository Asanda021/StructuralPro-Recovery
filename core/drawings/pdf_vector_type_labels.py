"""Bounded vector-stroke recognition of explicit C1/C2/C3 CAD labels.

This is not a general text/OCR engine. It recognizes only three independently
verifiable single-stroke glyph sequences ('C' + '1'/'2'/'3'). The *geometry* of
each glyph must match a normalized stroke-font template. Unsupported font,
rotation, missing stroke or an ambiguous physical attachment fail closed.

Reading a label does NOT establish a physical member, material, floor count,
engineering dimension or financially approved quantity.
"""
from __future__ import annotations

from math import hypot, isfinite
from typing import Any, Iterable, Mapping

_MAX_PATHS = 25_000
_MAX_LABELS = 600
_MAX_ATTACH_PT = 55.0

# Generic dimensionless stroke-lettering patterns, NOT source-drawing geometry.
# Shape matching is required; two path objects merely being close is insufficient.
_C = ((1, .833), (.75, 1), (.25, 1), (0, .833), (0, .167),
      (.25, 0), (.75, 0), (1, .167))
_ONE = ((0, .167), (1, 0), (1, 1))
_TWO = ((0, .167), (.25, 0), (.75, 0), (1, .167), (1, .34),
        (.75, .5), (.25, .5), (0, .667), (0, 1), (1, 1))
_THREE_TOP = ((0, .167), (.25, 0), (.75, 0), (1, .167),
              (1, .333), (.75, .5), (.5, .5))
_THREE_BOTTOM = ((.75, .5), (1, .667), (1, .833),
                 (.75, 1), (.25, 1), (0, .833))


def _points(path: Mapping) -> tuple[tuple[float, float], ...]:
    items = path.get('items') or ()
    if not items or path.get('type') != 's' or any(i[0] != 'l' for i in items):
        return ()
    points = [(float(items[0][1].x), float(items[0][1].y))]
    for item in items:
        start, end = item[1:3]
        if not all(isfinite(float(v)) for v in (start.x, start.y, end.x, end.y)):
            return ()
        if hypot(points[-1][0] - start.x, points[-1][1] - start.y) > .3:
            return ()
        points.append((float(end.x), float(end.y)))
    return tuple(points)


def _shape(path: Mapping, expected: tuple[tuple[float, float], ...],
           *, tolerance: float = .105) -> bool:
    points = _points(path)
    if len(points) != len(expected):
        return False
    r = path['rect']
    w, h = float(r.width), float(r.height)
    if not (w > .7 and h >= 3.5 and all(isfinite(v) for v in (w, h))):
        return False
    normalized = [((x-r.x0)/w, (y-r.y0)/h) for x, y in points]
    errors = []
    for given in (normalized, normalized[::-1]):
        errors.append(max(hypot(x-a, y-b) for (x, y), (a, b) in zip(given, expected)))
    return min(errors) < tolerance


def _same_line_bbox(a, b, *, horizontal=0.50, vertical=0.55) -> bool:
    return (abs(a.x0-b.x0) < horizontal and abs(a.x1-b.x1) < horizontal and
            abs(a.y1-b.y0) < vertical)


def _looks_like_c(path) -> bool:
    r=path['rect']
    return (5.0 <= r.width <= 10.8 and 7.0 <= r.height <= 16.0 and
            .50 <= r.width / r.height <= .86 and _shape(path, _C))


def _digit_for_c(cpath, drawn: list[Mapping]) -> tuple[str, tuple[int, ...]] | None:
    cr = cpath['rect']
    neighboring=[]
    for idx, path in enumerate(drawn):
        r=path['rect']
        if (1.0 <= r.x0-cr.x1 <= 6.2 and abs(r.y0-cr.y0) < .75 and
                0.5 <= r.width <= 10 and 3.5 <= r.height <= 16 and
                abs(r.y1-cr.y1) < .75):
            if _shape(path, _ONE) and r.width/r.height < .35:
                neighboring.append(('1', (idx,)))
            if _shape(path, _TWO) and .45 <= r.width/r.height <= .83:
                neighboring.append(('2', (idx,)))
    # A CAD stroke '3' consists of two distinct vertical half-characters.
    for top_idx, top in enumerate(drawn):
        r=top['rect']
        if not (1.0 <= r.x0-cr.x1 <= 6.2 and abs(r.y0-cr.y0)<.75 and
                0.35*cr.height < r.height < 0.7*cr.height):
            continue
        for lower_idx, bottom in enumerate(drawn):
            rb=bottom['rect']
            if (lower_idx != top_idx and
                    abs(rb.y1-cr.y1) < .75 and _same_line_bbox(r, rb) and
                    _paired_three_shapes(top, bottom, cr)):
                neighboring.append(('3', (top_idx,lower_idx)))
    # Uniqueness is a hard gate. Ambiguous patterns are never resolved by guess.
    return neighboring[0] if len(neighboring) == 1 else None


def _paired_three_shapes(top, bottom, c_rect) -> bool:
    """Test a two-path glyph as one normalized '3' of the C glyph height."""
    a,b=_points(top),_points(bottom)
    if len(a)!=len(_THREE_TOP) or len(b)!=len(_THREE_BOTTOM):
        return False
    ra=top['rect'];rb=bottom['rect']
    w=ra.width; h=c_rect.height
    if not (.48 <= w/h <= .82 and 7.0 <= h <= 16.0):
        return False
    def err(pts, expected):
        n=[((x-ra.x0)/w,(y-ra.y0)/h) for x,y in pts]
        return min(max(hypot(x-a,y-b) for (x,y),(a,b) in zip(q,expected))
                   for q in (n,n[::-1]))
    return err(a,_THREE_TOP)<.105 and err(b,_THREE_BOTTOM)<.105


def vector_column_type_labels(page, nodes: Iterable[Mapping[str, Any]], *,
                              max_attach_pt: float=_MAX_ATTACH_PT) -> dict:
    """Read glyph shape, then attach only uniquely nearest labeled grid node.

    All node coordinates are PDF page points. Candidate attachments do not
    approve a member, and no output is a payable takeoff quantity.
    """
    nodes=list(nodes)
    if not (0 < max_attach_pt <= _MAX_ATTACH_PT):
        raise ValueError('attachment radius exceeds validated bound')
    if not nodes:
        return {'nodes': [], 'labels': [], 'attached': 0,
                'physical_member_count': None, 'complete': False}
    if len(nodes) > 2000:
        raise ValueError('unbounded grid node list')
    if not any(n.get('column_context_candidate') for n in nodes):
        return {'nodes': [dict(n) for n in nodes], 'labels': [], 'attached': 0,
                'physical_member_count': None, 'complete': False}
    drawn=page.get_drawings()
    if len(drawn)>_MAX_PATHS:
        raise ValueError('vector path budget exceeded')
    labels=[]
    for idx,path in enumerate(drawn):
        if not _looks_like_c(path):
            continue
        recognized=_digit_for_c(path,drawn)
        if recognized is None:
            continue
        digit, indices=recognized
        cr=path['rect']; final=drawn[indices[0]]['rect']
        tag='C'+digit
        labels.append({'tag':tag,'bbox_pt':tuple(round(float(x),3) for x in
                        (cr.x0,cr.y0,drawn[indices[-1]]['rect'].x1,
                         max(cr.y1,drawn[indices[-1]]['rect'].y1))),
                       'path_indices':(idx,)+indices,
                       'source_class':'VECTOR_STROKE_LABEL',
                       'status':'PROPOSED_UNVERIFIED'})
        if len(labels)>_MAX_LABELS:
            raise ValueError('vector label budget exceeded')
    # Exclusivity: one glyph label cannot be the evidence for several nodes.
    assignments={}
    for li,label in enumerate(labels):
        x0,y0,x1,y1=label['bbox_pt']; lx=(x0+x1)/2; ly=(y0+y1)/2
        distances=[]
        for ni,node in enumerate(nodes):
            if not node.get('column_context_candidate'):
                continue
            dx=lx-float(node['x_pt']);dy=ly-float(node['y_pt'])
            if all(isfinite(v) for v in (dx,dy)):
                distances.append((hypot(dx,dy),ni))
        distances.sort()
        if not distances or distances[0][0]>max_attach_pt:
            continue
        if len(distances)>1 and distances[1][0]-distances[0][0]<12.0:
            continue
        ni=distances[0][1]
        assignments.setdefault(ni,[]).append((li,distances[0][0]))
    result=[]; valid=0
    for ni,node in enumerate(nodes):
        copy=dict(node)
        selected=assignments.get(ni,[])
        tags={labels[li]['tag'] for li,_ in selected}
        if len(selected)==1:
            li,distance=selected[0]
            copy.update({'suggested_type':labels[li]['tag'],
                         'status':'GRID_LOCATION_VECTOR_TYPE_CANDIDATE',
                         'vector_type_label_evidence':{**labels[li],
                                                      'distance_pt':round(distance,3)}})
            valid+=1
        elif selected:
            copy.update({'suggested_type':None,
                         'status':'BLOCKED_MULTIPLE_VECTOR_TYPE_LABELS',
                         'vector_type_label_evidence':[labels[li] for li,_ in selected]})
        copy.update({'type_verified':False,'physical_member_verified':False,
                     'quantity_approved':False,'financially_payable':False})
        result.append(copy)
    return {'nodes':result, 'labels':labels,'attached':valid,
            'physical_member_count':None, 'complete':False}