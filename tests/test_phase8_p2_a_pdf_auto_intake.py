"""Synthetic PDF automatic-intake checks. Never contain private project drawings."""
from pathlib import Path

import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _pdf(tmp_path, name='a.pdf', *, members=(('C-1', 'L= 10.70 m'),), count=1,
         vector_only=False, rotate=0):
    import pymupdf
    d = pymupdf.open()
    for page_no in range(count):
        page = d.new_page(width=600, height=500)
        if vector_only:
            page.draw_rect(pymupdf.Rect(10, 10, 80, 40))
        else:
            for j, (tag, dim) in enumerate(members):
                y = 50 + j * 75
                page.insert_text((100, y), tag, fontsize=13, rotate=rotate)
                page.insert_text((115, y), dim, fontsize=9, rotate=rotate)
    path = tmp_path / name
    d.save(path)
    d.close()
    return path


def test_single_explicit_member_type_is_not_counted_or_payable(tmp_path):
    result = inspect_pdf_sheet_set([_pdf(tmp_path)])
    assert len(result['member_type_candidates']) == 1
    c = result['member_type_candidates'][0]
    assert c['tag'] == 'C1' and c['dimension_m'] == '10.70'
    assert c['dimension_kind'] == 'length' and c['status'] == 'TYPE_DIMENSION_CANDIDATE'
    assert not c['financially_payable'] and not c['physical_instances_verified']
    assert result['physical_member_count'] is None and result['complete'] is False


def test_three_distinct_type_dimensions_extracted_without_grid_count(tmp_path):
    p = _pdf(tmp_path, members=(('C-1', 'L=10.70 m'), ('C-2', 'L=14.00 m'), ('C-3', 'L=12.00 m')))
    result = inspect_pdf_sheet_set([p])
    assert [(x['tag'], x['dimension_m']) for x in result['member_type_candidates']] == [
        ('C1', '10.70'), ('C2', '14.00'), ('C3', '12.00')]
    assert result['quantity_approval_count'] == 0


def test_rotated_member_and_dimension_match(tmp_path):
    p = _pdf(tmp_path, rotate=90)
    result = inspect_pdf_sheet_set([p])
    assert result['member_type_candidates'][0]['dimension_m'] == '10.70'


def test_cross_sheet_conflict_creates_user_question_with_unapproved_suggestion(tmp_path):
    a = _pdf(tmp_path, 'one.pdf', members=(('C-1', 'L=10.70 m'),))
    b = _pdf(tmp_path, 'two.pdf', members=(('C-1', 'L=14.00 m'),))
    report = inspect_pdf_sheet_set([a, b])
    assert len(report['questions']) == 1
    assert report['questions'][0]['tag'] == 'C1'
    assert report['questions'][0]['suggestion']['status'] == 'PROPOSED_UNVERIFIED'
    assert all(v['status'] == 'BLOCKED_CROSS_SHEET_CONFLICT' for v in report['member_type_candidates'])


def test_two_identical_type_marks_not_double_counted(tmp_path):
    a = _pdf(tmp_path, 'one.pdf', members=(('C-1', 'L=10.70 m'),))
    b = _pdf(tmp_path, 'two.pdf', members=(('C-1', 'L=10.70 m'),))
    result = inspect_pdf_sheet_set([a, b])
    assert len(result['member_type_candidates']) == 2
    assert not result['questions'] and result['physical_member_count'] is None


def test_vector_only_page_reports_unknown_semantic_coverage(tmp_path):
    report = inspect_pdf_sheet_set([_pdf(tmp_path, vector_only=True)])
    assert len(report['unresolved_pages']) == 1
    assert report['unresolved_pages'][0]['status'] == 'BLOCKED_SEMANTIC_COVERAGE_UNKNOWN'
    assert report['member_type_candidates'] == []


def test_missing_length_cannot_be_invented(tmp_path):
    result = inspect_pdf_sheet_set([_pdf(tmp_path, members=(('C-9', 'typical section'),))])
    assert result['member_type_candidates'][0]['status'] == 'BLOCKED_MISSING_DIMENSION'
    assert result['member_type_candidates'][0]['dimension_m'] is None


def test_non_member_label_not_a_member(tmp_path):
    report = inspect_pdf_sheet_set([_pdf(tmp_path, members=(('NOTE-7', 'L=10 m'),))])
    assert not report['member_type_candidates']


def test_invalid_path_and_duplicate_source_blocked(tmp_path):
    p = _pdf(tmp_path)
    with pytest.raises(ValueError, match='Duplicate'):
        inspect_pdf_sheet_set([p, p])
    with pytest.raises(ValueError, match='PDF'):
        inspect_pdf_sheet_set([tmp_path / 'missing.pdf'])


def test_page_and_file_limits(tmp_path):
    a = _pdf(tmp_path, 'a.pdf', count=2)
    b = _pdf(tmp_path, 'b.pdf')
    with pytest.raises(ValueError, match='page-count'):
        inspect_pdf_sheet_set([a,b], max_pages=2)
    with pytest.raises(ValueError, match='bounded'):
        inspect_pdf_sheet_set([a,b], max_documents=1)


def test_source_sha_matches_bytes_but_not_published_as_quantity(tmp_path):
    from hashlib import sha256
    p = _pdf(tmp_path)
    report = inspect_pdf_sheet_set([p])
    assert report['documents'][0]['sha256'] == sha256(p.read_bytes()).hexdigest()
    assert report['quantity_approval_count'] == 0


def test_cross_view_type_reference_without_physical_instance_inference(tmp_path):
    detail = _pdf(tmp_path, 'detail.pdf', members=(('C-1', 'L=10.70 m'),))
    plan = _pdf(tmp_path, 'plan.pdf', members=(('C-1', 'grid position'),))
    result = inspect_pdf_sheet_set([detail, plan])
    linked = [v for v in result['member_type_candidates'] if v['document_id'] == 'PDF002'][0]
    assert linked['status'] == 'CROSS_VIEW_TYPE_REFERENCE_CANDIDATE'
    assert linked['type_reference']['dimension_m'] == '10.70'
    assert linked['type_reference']['status'] == 'PROPOSED_UNVERIFIED'
    assert linked['physical_instances_verified'] is False
    assert result['physical_member_count'] is None and result['quantity_approval_count'] == 0


def test_batch_pdf_intake_preserves_grid_evidence_without_member_count(tmp_path):
    import pymupdf
    doc=pymupdf.open()
    page=doc.new_page(width=842,height=595)
    xs=[180,253,358,452,531];ys=[156,297,439]
    for x in xs:page.draw_line((x,ys[0]),(x,ys[-1]))
    for y in ys:page.draw_line((xs[0],y),(xs[-1],y))
    # One explicit tag, otherwise geometry cannot infer member type/count.
    page.insert_text((187,171),'C1',fontsize=9)
    f=tmp_path/'gridded_plan.pdf';doc.save(f);doc.close()
    report=inspect_pdf_sheet_set([f])
    assert len(report['grid_location_candidates'])==15
    assert report['physical_member_count'] is None
    assert report['quantity_approval_count']==0
    assert report['complete'] is False
    assert len(report['vector_grid_summaries'])==1
    assert sum(x['suggested_type']=='C1' for x in report['grid_location_candidates'])==1
    assert all(not x['financially_payable'] for x in report['grid_location_candidates'])