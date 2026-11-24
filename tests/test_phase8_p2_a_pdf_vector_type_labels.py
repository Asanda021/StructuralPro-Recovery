"""Source-independent stroke-template tests: no private drawings or numbers."""
from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from core.drawings.pdf_vector_type_labels import (
    vector_column_type_labels, _C, _ONE, _TWO, _THREE_TOP, _THREE_BOTTOM,
)


@dataclass
class Rect:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self):
        return self.x1 - self.x0

    @property
    def height(self):
        return self.y1 - self.y0


def path(template, x, y, width, height, *, reverse=False, kind='s'):
    pts = [(x+u*width, y+v*height) for u, v in template]
    if reverse:
        pts.reverse()
    items = [('l', SimpleNamespace(x=a[0],y=a[1]),
                 SimpleNamespace(x=b[0],y=b[1])) for a,b in zip(pts,pts[1:])]
    return {'type': kind, 'rect': Rect(min(p[0] for p in pts), min(p[1] for p in pts),
                                     max(p[0] for p in pts), max(p[1] for p in pts)),
            'items': items}


def glyph_pair(digit, x, y, *, reverse=False):
    c = path(_C,x,y,6.0,9.0,reverse=reverse)
    if digit=='1':
        return [c,path(_ONE,x+9,y,1.5,9.0,reverse=reverse)]
    if digit=='2':
        return [c,path(_TWO,x+9,y,5.7,9.0,reverse=reverse)]
    if digit=='3':
        return [c,path(_THREE_TOP,x+9,y,5.7,9.0,reverse=reverse),
                path(_THREE_BOTTOM,x+9,y,5.7,9.0,reverse=reverse)]
    raise ValueError(digit)


class Page:
    def __init__(self, paths):
        self.paths=paths
    def get_drawings(self):
        return self.paths


def node(x,y,*,context=True):
    return {'candidate_id':'PDF001:p1:r1:c1', 'document_id':'PDF001',
            'page':1,'x_pt':x,'y_pt':y,'column_context_candidate':context,
            'symbol_status':'COMPACT_VECTOR_SYMBOL_CANDIDATE',
            'suggested_type':None,'type_verified':False,
            'physical_member_verified':False,'financially_payable':False}


@pytest.mark.parametrize('digit',['1','2','3'])
def test_reads_three_explicit_single_stroke_column_types(digit):
    r=vector_column_type_labels(Page(glyph_pair(digit, 30,40)),[node(25,35)])
    assert r['attached']==1
    actual=r['nodes'][0]
    assert actual['suggested_type']=='C'+digit
    assert actual['status']=='GRID_LOCATION_VECTOR_TYPE_CANDIDATE'
    assert actual['vector_type_label_evidence']['status']=='PROPOSED_UNVERIFIED'
    assert actual['financially_payable'] is False
    assert actual['type_verified'] is False
    assert r['physical_member_count'] is None and r['complete'] is False


@pytest.mark.parametrize('digit',['1','2','3'])
def test_continuous_reversed_path_order_is_recognized(digit):
    r=vector_column_type_labels(Page(glyph_pair(digit,30,40,reverse=True)),[node(25,35)])
    assert r['nodes'][0]['suggested_type']=='C'+digit


def test_not_nearest_only_without_font_shape():
    bad=glyph_pair('2',30,40)
    bad[0]['items'][1]=('l',SimpleNamespace(x=999.,y=999.),SimpleNamespace(x=998.,y=998.))
    r=vector_column_type_labels(Page(bad),[node(25,35)])
    assert r['attached']==0


def test_requires_column_context_symbol_provenance():
    r=vector_column_type_labels(Page(glyph_pair('1',30,40)),[node(25,35,context=False)])
    assert r['attached']==0 and r['nodes'][0]['suggested_type'] is None


def test_missing_number_does_not_default_to_one():
    r=vector_column_type_labels(Page(glyph_pair('1',30,40)[:1]),[node(25,35)])
    assert r['attached']==0 and r['nodes'][0]['suggested_type'] is None


def test_missing_lower_half_does_not_guess_three():
    r=vector_column_type_labels(Page(glyph_pair('3',30,40)[:2]),[node(25,35)])
    assert r['attached']==0


def test_contested_two_labels_same_node_fail_closed():
    paths=glyph_pair('1',30,40)+glyph_pair('2',38,41)
    # Both labels attach to one node, so no unique classification.
    r=vector_column_type_labels(Page(paths),[node(25,35)])
    assert r['attached']==0
    assert r['nodes'][0]['status']=='BLOCKED_MULTIPLE_VECTOR_TYPE_LABELS'
    assert r['nodes'][0]['financially_payable'] is False


def test_ambiguous_nearest_node_does_not_attach():
    paths=glyph_pair('1',30,40)
    r=vector_column_type_labels(Page(paths),[node(26,35),node(44,35)])
    assert r['attached']==0


def test_distant_label_does_not_attach():
    r=vector_column_type_labels(Page(glyph_pair('2',100,100)),[node(20,20)])
    assert r['attached']==0


def test_no_nodes_no_members():
    r=vector_column_type_labels(Page(glyph_pair('2',30,40)),[])
    assert r['attached']==0 and r['nodes']==[]
    assert r['complete'] is False


def test_never_allows_unbounded_attachment_radius():
    with pytest.raises(ValueError):
        vector_column_type_labels(Page([]),[node(25,35)],max_attach_pt=200)


def test_duplicate_notes_cannot_fake_payable_quantities():
    r=vector_column_type_labels(Page(glyph_pair('1',30,40)),[node(25,35)])
    assert r['nodes'][0]['quantity_approved'] is False
    assert 'quantity' not in r['nodes'][0]
    assert 'boq' not in r['nodes'][0]


def test_vector_path_different_from_stroked_is_not_text():
    fake=glyph_pair('1',30,40)
    fake[0]['type']='f'
    assert vector_column_type_labels(Page(fake),[node(25,35)])['attached']==0