"""Synthetic, fail-closed symbol evidence checks; no real drawings in CI."""
import pymupdf
import pytest

from core.drawings.pdf_vector_symbol_witness import (
    compact_symbol_witness, sheet_context_hint,
)
from core.drawings.pdf_grid_instances import detect_vector_grid_positions


def _doc(*, marked=(0, 4, 8), heading='پلان تیپ بندی ستون ها', explicit_rect=False):
    doc=pymupdf.open()
    p=doc.new_page(width=842,height=595)
    x=[180,300,450]
    y=[150,300,450]
    for xx in x:p.draw_line((xx,y[0]),(xx,y[-1]))
    for yy in y:p.draw_line((x[0],yy),(x[-1],yy))
    for key in marked:
        cx,cy=x[key % 3],y[key//3]
        if explicit_rect:
            p.draw_rect(pymupdf.Rect(cx-2,cy-2,cx+2,cy+2))
        else:
            # Mimics a fragmented vector symbol instead of a single path.
            p.draw_line((cx-2,cy-2),(cx+2,cy-2))
            p.draw_line((cx-2,cy+2),(cx+2,cy+2))
            p.draw_line((cx-2,cy-2),(cx-2,cy+2))
            p.draw_line((cx+2,cy-2),(cx+2,cy+2))
    if heading:p.insert_text((30,30), heading, fontsize=9)
    return doc,p


def _nodes(page):
    return detect_vector_grid_positions(page,document_id='test',page_number=1)['nodes']


def test_explicit_layout_title_normalization_arabic_presentation_forms():
    assert sheet_context_hint('ﭘـــﻼن ﺗﯿــــﭗ ﺑﻨـــﺪي ﺳــــﺘﻮن ﻫﺎ')=='COLUMN_LAYOUT_TITLE_CANDIDATE'
    assert sheet_context_hint('COLUMN PLAN')=='COLUMN_LAYOUT_TITLE_CANDIDATE'
    assert sheet_context_hint('column details')=='SHEET_CONTEXT_UNVERIFIED'


def test_grid_not_member_without_compact_symbol():
    doc,p=_doc(marked=(),heading='Column plan')
    r=compact_symbol_witness(p,_nodes(p))
    assert len(r['nodes'])==9 and r['symbol_candidate_count']==0
    assert r['physical_member_count'] is None
    doc.close()


def test_only_marked_nodes_get_symbol_witness():
    doc,p=_doc(heading='Column plan')
    r=compact_symbol_witness(p,_nodes(p))
    assert r['symbol_candidate_count']==3
    assert r['column_context_candidates']==3
    assert sum(n['column_context_candidate'] for n in r['nodes'])==3
    assert all(not n['physical_member_verified'] and not n['financially_payable'] for n in r['nodes'])
    doc.close()


def test_explicit_rectangle_witness_stays_unverified():
    doc,p=_doc(marked=(2,),explicit_rect=True,heading='Column plan')
    r=compact_symbol_witness(p,_nodes(p))
    assert r['symbol_candidate_count']==1
    assert r['nodes'][2]['symbol_witness']['explicit_compact_rectangles']>=1
    assert all(n['type_verified'] is False for n in r['nodes'])
    doc.close()


def test_title_without_context_never_becomes_column():
    doc,p=_doc(heading='Architectural table')
    r=compact_symbol_witness(p,_nodes(p))
    assert r['symbol_candidate_count']==3
    assert r['column_context_candidates']==0
    doc.close()


def test_long_axis_only_does_not_trigger_symbol():
    doc,p=_doc(marked=(),heading='Column plan')
    r=compact_symbol_witness(p,_nodes(p))
    assert all(n['symbol_status']=='NO_COMPACT_SYMBOL_EVIDENCE' for n in r['nodes'])
    doc.close()


def test_no_nodes_does_not_claim_complete():
    doc,p=_doc(marked=())
    r=compact_symbol_witness(p,[])
    assert r['symbol_candidate_count']==0 and r['complete'] is False
    doc.close()


def test_nonfinite_node_refused_without_paying():
    doc,p=_doc(marked=())
    with pytest.raises(ValueError):compact_symbol_witness(p,[{'x_pt':float('nan'),'y_pt':12}])
    doc.close()


def test_nested_small_shape_does_not_assign_type_or_amount():
    doc,p=_doc(marked=(0,1,2,3,4,5,6,7,8),heading='Column Plan')
    r=compact_symbol_witness(p,_nodes(p))
    assert r['symbol_candidate_count']==9
    assert all(n['physical_member_verified'] is False and n['quantity_approved'] is False for n in r['nodes'])
    doc.close()