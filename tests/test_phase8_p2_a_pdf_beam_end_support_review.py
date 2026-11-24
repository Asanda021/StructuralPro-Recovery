"""Synthetic-only, nonfinancial regression tests; never bundle real private PDF."""
import copy
import pytest
import pymupdf
from core.drawings.pdf_beam_end_support_review import (
    extract_pdf_beam_end_markers, review_beam_ends_against_independent_grid,
)

SHA='a'*64
GRID = dict(document_id='PDF001', page=13, source_name='fake.pdf', source_sha256=SHA,
            grid_x_pt=[180.,253.,358.,451.,531.], grid_y_pt=[156.,297.,439.],
            status='PROPOSED_UNLABELED_AXIS_GRID')
AXES = dict(source_sha256=SHA, document_id='PDF001',page=13,beam_page=15,
            source_method='VISUALLY_REVIEWED_AXIS_LABELS', financially_payable=False,
            horizontal_letters=['A','B','C','D','E'], rows_top_to_bottom=['3','2','1'])

def _picture(*,missing=None,split=False,overlap=False):
    document = pymupdf.open()
    page = document.new_page(width=842,height=595)
    for row,y in enumerate(GRID['grid_y_pt']):
        for col,x in enumerate(GRID['grid_x_pt']):
            if (row,col)==missing: continue
            if split and (row,col)==(1,2):
                for xmin,xmax in ((x-2.88,x),(x,x+2.88)):
                    page.draw_rect((xmin,y-2.88,xmax,y+2.88),fill=(0,0,0),color=None)
            else:
                page.draw_rect((x-2.88,y-2.88,x+2.88,y+2.88),fill=(0,0,0),color=None)
                if overlap: page.draw_rect((x-2.88,y-2.88,x+2.88,y+2.88),fill=(0,0,0),color=None)
    return document

def _markers(doc,grid=GRID):
    return extract_pdf_beam_end_markers(doc[0],document_id='PDF001',page_number=15,
                                       source_name='fake.pdf',source_sha256=SHA,grid=grid)

def _profile(**update):
    item=dict(document='fake.pdf',source_sha256=SHA,page=15,
              source_method='VISUAL_CAD_STROKES_PRIVATE_RENDER',financially_payable=False,
              bbox_pt=[195,160,240,174],span_axes='A-B',printed_axis_row='3',
              profile_text_raw='2IPE16',profile_text_normalized='2IPE16',
              source_visual_confidence='VISIBLE',governing_detail_id=None,
              verified_cut_quantity=None,verified_length_m=None)
    item.update(update)
    return item

def _detail(**update):
    item=dict(document='fake.pdf',source_sha256=SHA,page=17,
              source_method='VISUAL_CAD_STROKES_PRIVATE_RENDER',financially_payable=False,
              bbox_pt=[61,167,117,186],profile_text_raw='2IPE16',
              profile_text_normalized='2IPE16',source_visual_confidence='VISIBLE',
              governing_detail_id=None,verified_length_m=None)
    item.update(update)
    return item

def test_distinct_grid_markers_and_coincident_operator_evidence():
    with _picture(overlap=True,split=True) as doc:
        result=_markers(doc)
    assert result['status']=='PROPOSED_UNVERIFIED_SQUARE_MARKERS'
    assert result['marker_count']==15
    assert result['duplicate_source_strokes'] >= 14
    assert len({(r['grid_row_index'],r['grid_column_index']) for r in result['marker_candidates']})==15
    assert all(r['status']=='PROPOSED_GRID_SQUARE_MARK' for r in result['marker_candidates'])
    assert all(r['financially_payable'] is False and r['physical_support_verified'] is False for r in result['marker_candidates'])


def test_both_end_marks_still_do_not_verify_member_or_span_specific_detail():
    with _picture(split=True) as doc:
        evidence=_markers(doc)
    row,=review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile()],[_detail()])['profiles']
    assert row['status']=='PROPOSED_BOTH_END_GRID_SYMBOLS'
    assert row['endpoint_symbol_candidates']==[1,1]
    assert row['detail_status']=='PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC'
    assert row['candidate_detail_count']==1
    assert row['physical_member_verified'] is False and row['support_verified'] is False
    assert row['detail_link_verified'] is False and row['member_quantity'] is None
    assert row['verified_installed_length'] is None and row['financially_payable'] is False


def test_one_missing_end_prevents_support_proposal():
    with _picture(missing=(0,1)) as doc:
        evidence=_markers(doc)
    row,=review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile()])['profiles']
    assert row['status']=='BLOCKED_MISSING_OR_AMBIGUOUS_ENDPOINT_SYMBOL'
    assert row['endpoint_symbol_candidates']==[1,0]


def test_uncertain_profile_is_blocked_even_with_both_ends():
    with _picture() as doc:
        evidence=_markers(doc)
    row,=review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile(source_visual_confidence='REVIEW_REQUIRED')])['profiles']
    assert row['status']=='BLOCKED_PROFILE_GLYPH_UNCERTAIN'


def test_absent_or_repeated_detail_not_a_specific_connection():
    with _picture() as doc:
        evidence=_markers(doc)
    rows=review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile()],[])['profiles']
    assert rows[0]['detail_status']=='NO_SAME_TYPE_CONNECTION_DETAIL_WITNESS'
    rows=review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile()],[_detail(),_detail(bbox_pt=[200,200,244,222])])['profiles']
    assert rows[0]['detail_status']=='MULTIPLE_SAME_TYPE_CONNECTION_DETAIL_WITNESSES'
    assert rows[0]['detail_link_verified'] is False


@pytest.mark.parametrize('change',[
    dict(source_sha256='b'*64),dict(page=14),dict(financially_payable=True),
    dict(verified_length_m=12.4),dict(verified_cut_quantity=1),
    dict(source_method='OCR_GUESS'), dict(bbox_pt=[1,1,1,5]),
])
def test_unbound_unsafe_beam_input_rejected(change):
    with _picture() as doc:evidence=_markers(doc)
    with pytest.raises(ValueError):review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile(**change)])


def test_visual_detail_source_mismatch_rejected():
    with _picture() as doc:evidence=_markers(doc)
    with pytest.raises(ValueError):review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile()],[_detail(source_sha256='b'*64)])


def test_duplicate_beam_visual_label_is_not_two_members():
    with _picture() as doc:evidence=_markers(doc)
    with pytest.raises(ValueError,match='Duplicate'):
        review_beam_ends_against_independent_grid(evidence,GRID,AXES,[_profile(),copy.deepcopy(_profile())])


def test_missing_or_rotated_source_fails_closed():
    with _picture() as doc:
        assert _markers(doc,None)['status']=='BLOCKED_NO_INDEPENDENT_GRID'
        doc[0].set_rotation(90)
        assert _markers(doc)['status']=='BLOCKED_ROTATED_BEAM_PLAN'

def test_same_type_multiple_spans_still_have_no_span_specific_connection():
    # Two beams can have the same printed profile but different supports.
    # One generic detail type name cannot prove it governs either span.
    with _picture() as doc:
        markers = _markers(doc)
    different_span = _profile(span_axes='B-C', bbox_pt=[265, 160, 330, 174])
    result = review_beam_ends_against_independent_grid(
        markers, GRID, AXES, [_profile(), different_span], [_detail()])
    assert len(result['profiles']) == 2
    assert all(row['status'] == 'PROPOSED_BOTH_END_GRID_SYMBOLS'
               for row in result['profiles'])
    assert all(row['detail_status'] == 'PROPOSED_TYPE_ONLY_NOT_SPAN_SPECIFIC'
               for row in result['profiles'])
    assert all(row['detail_link_verified'] is False and row['member_quantity'] is None
               and row['financially_payable'] is False for row in result['profiles'])
