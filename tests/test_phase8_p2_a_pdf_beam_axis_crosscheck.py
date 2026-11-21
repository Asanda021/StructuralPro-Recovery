"""Synthetic, source-free tests: no user plan drawings in repository."""
import copy
import pymupdf
import pytest

from core.drawings.pdf_beam_axis_crosscheck import extract_pdf_axis_grid_witness, reconcile_pdf_beam_grid_labels

SHA = 'a' * 64


def make_grid(rotated=False):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    xs = [179.76, 253.44, 358.32, 451.92, 531.36]
    ys = [155.56, 297.16, 438.76]
    for x in xs:
        page.draw_line((x, ys[0]), (x, ys[2]))
    # Use split top/bottom grid-line segments, as in the source CAD.
    page.draw_line((253, ys[0]), (528, ys[0]))
    page.draw_line((179, ys[1]), (534, ys[1]))
    page.draw_line((253, ys[2]), (534, ys[2]))
    # Dimension and footer lines are not grid axes.
    page.draw_line((185, 120), (525, 120))
    page.draw_line((603, 425), (789, 425))
    if rotated:
        page.set_rotation(90)
    return doc, page


def labels():
    return {'source_sha256': SHA, 'document_id': 'PDF001', 'page': 13,
            'beam_page': 15, 'printed_unit': None,
            'source_method': 'VISUALLY_REVIEWED_AXIS_LABELS',
            'financially_payable': False,
            'horizontal_letters': list('ABCDE'), 'rows_top_to_bottom': ['3', '2', '1'],
            'printed_horizontal_spacings': [2.6, 3.7, 3.3, 2.8],
            'printed_vertical_spacings': [5, 5]}


def witness(x=216.0, y=178.5, span='A-B', row='3', confidence='VISIBLE'):
    return {'document': 'naghshe.pdf', 'source_sha256': SHA, 'page': 15,
            'bbox_pt': [x-12, y-8, x+12, y+8],
            'source_method': 'VISUAL_CAD_STROKES_PRIVATE_RENDER',
            'profile_text_normalized': '2IPE16', 'span_axes': span,
            'printed_axis_row': row, 'source_visual_confidence': confidence,
            'financially_payable': False}


def test_synthetic_axis_grid_tracks_source_line_refs_not_drawing_units():
    doc, page = make_grid()
    try:
        result = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                               source_sha256=SHA, source_name='naghshe.pdf')
        assert result['status'] == 'PROPOSED_UNLABELED_AXIS_GRID'
        assert result['grid_x_pt'] == [179.76, 253.44, 358.32, 451.92, 531.36]
        assert result['grid_y_pt'] == [155.56, 297.16, 438.76]
        assert len(result['source_operator_refs']) == 8
        assert result['printed_unit'] is None
        assert result['calibrated_member_length'] is None
        assert not result['financially_payable']
    finally:
        doc.close()


def test_axis_labels_and_printed_dimensions_allow_only_nonfinancial_location_proposal():
    doc, page = make_grid()
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
    finally:
        doc.close()
    result = reconcile_pdf_beam_grid_labels(grid, labels(), [witness(),
                                    witness(305, 270, 'B-C', '2'),
                                    witness(490, 413, 'D-E', '1'),
                                    witness(216, 450, 'A-B', '1', 'REVIEW_REQUIRED')])
    assert result['axis_location_proposals'] == 3
    assert result['blocked_profile_observations'] == 1
    assert result['status'] == 'PROPOSED_PAPER_GRID_CONSISTENCY_ONLY'
    assert result['max_scale_disagreement_pct'] < .2
    assert all(row['member_quantity'] is None and not row['financially_payable']
               and row['verified_installed_length'] is None for row in result['profiles'])


@pytest.mark.parametrize('field,value', [
    ('source_sha256', 'b'*64), ('document', 'another.pdf'), ('page', 14),
    ('financially_payable', True), ('verified_length_m', 5.1),
    ('source_visual_confidence', 'APPROVED'),
    ('source_method', 'GENERATED'), ('bbox_pt', [0, 0, 0, 0]),
])
def test_foreign_or_promoted_profile_is_rejected(field, value):
    doc, page = make_grid()
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
    finally:
        doc.close()
    visual = witness()
    visual[field] = value
    with pytest.raises(ValueError):
        reconcile_pdf_beam_grid_labels(grid, labels(), [visual])


def test_wrong_row_or_span_is_blocked_and_no_quantity_created():
    doc, page = make_grid()
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
    finally:
        doc.close()
    rows = [witness(span='B-C'), witness(row='1', x=216, y=178), witness(x=700)]
    result = reconcile_pdf_beam_grid_labels(grid, labels(), rows)
    assert result['axis_location_proposals'] == 0
    assert result['blocked_profile_observations'] == 3
    assert all(r['status'] == 'BLOCKED_AXIS_POSITION_CONFLICT' for r in result['profiles'])


def test_inconsistent_dimension_chain_and_fake_axis_labels_fail_closed():
    doc, page = make_grid()
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
    finally:
        doc.close()
    bad = labels()
    bad['printed_horizontal_spacings'][0] = 2.1
    blocked = reconcile_pdf_beam_grid_labels(grid, bad, [witness()])
    assert blocked['status'] == 'BLOCKED_PRINTED_DIMENSION_CHAIN_DISAGREEMENT'
    assert blocked['profiles'] == []
    fake = labels()
    fake['horizontal_letters'] = ['A', 'A', 'C', 'D', 'E']
    with pytest.raises(ValueError):
        reconcile_pdf_beam_grid_labels(grid, fake, [witness()])
    fake = labels()
    fake['printed_unit'] = 'm'
    with pytest.raises(ValueError):
        reconcile_pdf_beam_grid_labels(grid, fake, [witness()])


def test_duplicate_beam_observation_is_blocked():
    doc, page = make_grid()
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
    finally:
        doc.close()
    sample = witness()
    with pytest.raises(ValueError, match='Duplicate'):
        reconcile_pdf_beam_grid_labels(grid, labels(), [sample, copy.deepcopy(sample)])


def test_rotated_axis_page_is_not_silently_registered():
    doc, page = make_grid(rotated=True)
    try:
        grid = extract_pdf_axis_grid_witness(page, document_id='PDF001', page_number=13,
                                             source_sha256=SHA, source_name='naghshe.pdf')
        assert grid['status'] == 'BLOCKED_ROTATED_AXIS_GRID'
    finally:
        doc.close()
    with pytest.raises(ValueError):
        reconcile_pdf_beam_grid_labels(grid, labels(), [witness()])