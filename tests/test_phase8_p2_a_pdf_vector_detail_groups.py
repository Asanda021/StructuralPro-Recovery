"""Synthetic geometry-group evidence and fail-closed tests (never BOQ)."""
import pytest

pymupdf = pytest.importorskip('pymupdf')

from core.drawings.pdf_vector_detail_groups import index_pdf_vector_path_groups
from core.drawings.pdf_sheet_detail_inventory import (
    inventory_pdf_page_regions, assemble_pdf_detail_inventory,
)
from core.drawings.pdf_detail_object_index import build_pdf_detail_object_index
from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _title(box=(0,0,90,20)):
    return {'anchor_id':'PDF001:p1:title1','document_id':'PDF001',
            'page':1,'bbox_pt':box,'title_preview':'Beam Detail B1'}


def test_independent_groups_on_one_tile_are_not_one_detail():
    d=pymupdf.open();p=d.new_page(width=600,height=400)
    p.draw_rect(pymupdf.Rect(10,50,40,80))
    p.draw_rect(pymupdf.Rect(80,50,110,80))
    p.draw_rect(pymupdf.Rect(200,100,240,140))
    inv=inventory_pdf_page_regions(p,document_id='PDF001',page_number=1,
                                   rows=2,columns=2)
    d.close()
    geo=inv['vector_geometry_grouping']
    assert geo['source_path_count']==3
    assert geo['group_count']==3
    assert sum(x['source_path_count'] for x in geo['groups'])==3
    assert geo['all_source_paths_grouped']
    assert all(x['financially_payable'] is False for x in geo['groups'])
    assert inv['region_count']==4


def test_touching_path_bboxes_merge_only_as_provisional_group():
    g=index_pdf_vector_path_groups(
        [(0,0,20,1),(20,0,40,1),(100,50,110,60)],[],
        document_id='PDF001',page=1)
    assert g['group_count']==2
    assert g['groups'][0]['source_path_indices']==[1,2]
    assert g['physical_member_count'] is None
    assert not g['detail_boundaries_verified']


def test_enclosing_sheet_frame_does_not_absorb_other_geometry():
    g=index_pdf_vector_path_groups(
        [(0,0,600,400),(40,40,60,60),(200,200,250,250)],[],
        document_id='PDF001',page=1)
    assert g['group_count']==3
    assert g['grouped_path_count']==3


def test_nearby_titles_are_only_anchors_not_approved_links():
    g=index_pdf_vector_path_groups([(30,40,100,140),(250,100,280,140)],
        [_title((30,10,100,25))],document_id='PDF001',page=1)
    assert g['groups'][0]['nearby_title_anchor_ids']==['PDF001:p1:title1']
    assert g['groups'][1]['nearby_title_anchor_ids']==[]
    assert not g['groups'][0]['detail_boundary_verified']
    assert not g['groups'][0]['quantity_approved']


def test_source_path_budgets_block_entire_grouping_without_partial_approval():
    boxes=[(i*10,0,i*10+2,10) for i in range(4)]
    report=index_pdf_vector_path_groups(boxes,[],document_id='PDF001',
                                       page=1,max_paths=2)
    assert report['status']=='BLOCKED_VECTOR_GROUP_PATH_BUDGET'
    assert report['ungrouped_path_count']==4
    assert report['groups']==[]
    assert report['all_source_paths_grouped'] is False


def test_pair_budget_blocks_dense_line_network():
    boxes=[(0,0,100,100) for _ in range(8)]
    report=index_pdf_vector_path_groups(boxes,[],document_id='PDF001',
                                       page=1,max_pair_checks=3)
    assert report['status']=='BLOCKED_VECTOR_GROUP_PAIR_BUDGET'
    assert report['ungrouped_path_count']==8
    assert not report['all_source_paths_grouped']


def test_failed_extraction_blocks_even_when_no_vectors_survive():
    report=index_pdf_vector_path_groups([],[],document_id='PDF001',
                                       page=1,source_blocked=True)
    assert report['status']=='BLOCKED_SOURCE_EVIDENCE_INCOMPLETE'
    assert not report['all_source_paths_grouped']


def test_invalid_path_geometry_and_cross_document_title_fail_closed():
    with pytest.raises(ValueError,match='bbox'):
        index_pdf_vector_path_groups([(1,2,1,4)],[],document_id='PDF001',page=1)
    title=_title();title['document_id']='PDF002'
    with pytest.raises(ValueError,match='Foreign'):
        index_pdf_vector_path_groups([(0,0,10,10)],[title],document_id='PDF001',page=1)


def test_real_two_page_pdf_evidence_graph_contains_nonpayable_groups(tmp_path):
    d=pymupdf.open()
    p=d.new_page(width=500,height=400)
    p.insert_text((20,20),'Beam Detail B1')
    p.draw_line((40,80),(80,80))
    p.draw_line((80,80),(120,80))
    p.draw_rect(pymupdf.Rect(300,220,360,300))
    q=d.new_page(width=500,height=400)
    q.draw_rect(pymupdf.Rect(50,50,120,120))
    source=tmp_path/'details.pdf'
    d.save(source);d.close()
    report=inspect_pdf_sheet_set([source])
    cov=report['sheet_detail_inventory']
    graph=report['detail_object_index']
    assert cov['vector_grouping_page_count']==2
    assert cov['all_vector_paths_grouped']
    assert graph['vector_grouping_page_count']==2
    assert graph['all_vector_paths_grouped']
    assert graph['vector_geometry_group_count']>=2
    assert graph['vector_grouping_blocked_pages']==[]
    assert all(g['financially_payable'] is False for g in graph['vector_geometry_groups'])
    assert graph['physical_member_count'] is None
    assert graph['quantity_approval_count']==0
    assert not graph['complete']


def test_blocked_page_is_not_lost_in_evidence_graph():
    d=pymupdf.open();p=d.new_page(width=500,height=400)
    p.draw_rect(pymupdf.Rect(20,20,120,120))
    inv=inventory_pdf_page_regions(p,document_id='PDF001',page_number=1,max_paths=1)
    d.close()
    assert inv['vector_geometry_grouping']['source_path_count']==1
    # Explicitly mark a failed source extraction as a negative test.
    inv['vector_geometry_grouping']['status']='BLOCKED_SOURCE_EVIDENCE_INCOMPLETE'
    inv['vector_geometry_grouping']['all_source_paths_grouped']=False
    assembled=assemble_pdf_detail_inventory(
        [inv],[{'document_id':'PDF001','page_count':1}])
    graph=build_pdf_detail_object_index(assembled)
    assert len(graph['vector_grouping_blocked_pages'])==1
    assert graph['all_vector_paths_grouped'] is False
    assert graph['quantity_approval_count']==0
