"""Synthetic geometry acceptance. No private source files in repository."""
import pymupdf
from core.drawings.pdf_grid_instances import detect_vector_grid_positions


def _page(*, grid=True, table=True, dimension=True, doubled=False):
    doc = pymupdf.open()
    page = doc.new_page(width=842, height=595)
    if grid:
        xs = [179.76,253.44,358.32,451.92,531.36]
        ys = [155.56,297.16,438.76]
        for x in xs:
            page.draw_line((x,ys[0]),(x,ys[-1]))
            if doubled:
                page.draw_line((x+0.48,ys[0]),(x+0.48,ys[-1]))
        for y in ys:
            page.draw_line((xs[0],y),(xs[-1],y))
    if dimension:
        page.draw_line((137.28,155.56),(137.28,438.76))
        for y in (155.56,297.16,438.76):
            page.draw_line((127.2,y),(164.15,y))  # independent dimension witness
    if table:
        for x in (603.36,663.36):
            page.draw_line((x,424.12),(x,543.64))
        for y in (424.12,440.68,462.76,484.6,508.6,520.84):
            page.draw_line((603.36,y),(789.12,y))
    return doc, page


def test_grid_5_by_3_produces_fifteen_unverified_positions():
    doc,page = _page()
    result = detect_vector_grid_positions(page,document_id='PDF001',page_number=14)
    assert result['status']=='VECTOR_GRID_LOCATION_CANDIDATES'
    assert len(result['axes_x_pt'])==5 and len(result['levels_y_pt'])==3
    assert len(result['nodes'])==15
    assert result['nodes'][0]['x_pt']==179.76
    assert result['nodes'][0]['y_pt']==155.56
    assert all(not n['physical_member_verified'] and not n['financially_payable'] for n in result['nodes'])
    assert result['complete'] is False and result['physical_member_count'] is None
    doc.close()


def test_parallel_doubled_strokes_do_not_create_duplicate_nodes():
    doc,page=_page(doubled=True)
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1)
    assert len(result['nodes'])==15
    doc.close()


def test_dimension_and_title_table_are_not_counted_as_grid():
    doc,page=_page(grid=False)
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1)
    assert result['nodes']==[] and result['status']=='NO_GRID_EVIDENCE'
    doc.close()


def test_unsupported_sparse_drawing_is_not_force_fitted():
    doc,page=_page(grid=False,table=False,dimension=False)
    for x in (30,70):page.draw_line((x,100),(x,450))
    for y in (100,200,450):page.draw_line((30,y),(70,y))
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1)
    assert result['nodes']==[]
    doc.close()


def test_one_nearby_type_is_a_candidate_not_an_assigned_column():
    doc,page=_page(table=False,dimension=False)
    mark={'tag':'C1','bbox':(183,163,190,174)}
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1,text_type_marks=[mark])
    matched=[n for n in result['nodes'] if n['suggested_type']=='C1']
    assert len(matched)==1 and matched[0]['status']=='GRID_LOCATION_TYPE_TEXT_CANDIDATE'
    assert matched[0]['type_verified'] is False and matched[0]['quantity_approved'] is False
    doc.close()


def test_conflicting_nearby_types_block_type_inference():
    doc,page=_page(table=False,dimension=False)
    marks=[{'tag':'C1','bbox':(183,163,190,174)}, {'tag':'C2','bbox':(185,164,192,176)}]
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1,text_type_marks=marks)
    assert any(n['status']=='BLOCKED_MULTIPLE_NEARBY_TYPES' and n['suggested_type'] is None for n in result['nodes'])
    doc.close()


def test_max_nodes_restricts_output_without_partial_coverage():
    doc,page=_page()
    result=detect_vector_grid_positions(page,document_id='PDF001',page_number=1,max_nodes=10)
    assert result['nodes']==[]
    doc.close()


def test_bad_source_identity_rejected():
    import pytest
    doc,page=_page()
    with pytest.raises(ValueError):detect_vector_grid_positions(page,document_id='',page_number=1)
    with pytest.raises(ValueError):detect_vector_grid_positions(page,document_id='D',page_number=0)
    doc.close()