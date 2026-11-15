"""Safe, synthetic tests for all-sheet PDF detail coverage inventory."""
from copy import deepcopy
import pytest
pymupdf=pytest.importorskip('pymupdf')
from core.drawings.pdf_sheet_detail_inventory import (inventory_pdf_page_regions,
                                                      assemble_pdf_detail_inventory)


def _page(kind='vector', *, widths=(600,500)):
    d=pymupdf.open()
    p=d.new_page(width=widths[0],height=widths[1])
    if kind in ('vector','many','detail','separate'):
        p.draw_rect(pymupdf.Rect(30,30,250,240))
    if kind=='many':
        for x in range(20):p.draw_line((x*6+280,60),(x*6+300,330))
    if kind=='detail':
        p.insert_text((20,25),'Connection Detail B1',fontsize=12)
        p.insert_text((320,250),'Column Detail C-2',fontsize=12)
        p.draw_line((330,255),(510,420))
    if kind=='text':p.insert_text((40,60),'C-1 L=10.7m',fontsize=12)
    if kind=='separate':p.insert_text((40,60),'Detailed Beam B1',fontsize=12)
    return d,p


def _inspect(page, n=1, **kwargs):
    return inventory_pdf_page_regions(page,document_id='PDF001',page_number=n,**kwargs)


def test_each_page_has_fixed_unique_tile_partition_even_if_blank():
    d,p=_page('blank');x=_inspect(p);d.close()
    assert len(x['regions'])==16==x['expected_region_count']
    assert len({r['region_id'] for r in x['regions']})==16
    assert x['coverage_status']=='EXAMINED'
    assert all(r['status']=='EXAMINED' for r in x['regions'])
    assert all(r['physical_member_verified'] is False and r['financially_payable'] is False for r in x['regions'])


def test_vector_geometry_is_never_silently_marked_interpreted():
    d,p=_page('vector');x=_inspect(p);d.close()
    assert x['coverage_status']=='UNRESOLVED'
    assert any(r['status']=='UNRESOLVED' and r['vector_path_count'] for r in x['regions'])
    assert x['detail_geometry_interpreted'] is False


def test_two_explicit_detail_titles_preserve_independent_source_anchors():
    d,p=_page('detail');x=_inspect(p);d.close()
    assert len(x['detail_title_anchors'])==2
    assert len({k['anchor_id'] for k in x['detail_title_anchors']})==2
    assert all(k['status']=='UNRESOLVED' and k['page']==1 for k in x['detail_title_anchors'])
    assert sum(bool(r['explicit_detail_title_ids']) for r in x['regions'])>=2


def test_text_only_tag_indexing_does_not_claim_quantity():
    d,p=_page('text');x=_inspect(p);d.close()
    marks=[m for tile in x['regions'] for m in tile['searchable_member_marks']]
    assert 'C1' in marks
    assert all(not r['financially_payable'] for r in x['regions'])
    assert x['coverage_status']=='EXAMINED'


def test_dense_valid_vectors_not_truncated_when_within_budget():
    d,p=_page('many');x=_inspect(p);d.close()
    assert x['coverage_status']=='UNRESOLVED'
    assert x['vector_path_count']>=2
    assert not x['extraction_errors']


def test_exceeded_budget_blocks_entire_page_without_silent_drop():
    d,p=_page('many');x=_inspect(p,max_paths=2);d.close()
    assert x['coverage_status']=='BLOCKED'
    assert 'BLOCKED_EXCESSIVE_VECTOR_PATHS' in x['extraction_errors']
    assert len(x['regions'])==16
    assert all(r['status']=='BLOCKED' for r in x['regions'])


def test_multi_sheet_assembly_guards_all_pages_and_counts():
    d=pymupdf.open();a=d.new_page(width=600,height=500);a.draw_line((5,5),(500,400))
    b=d.new_page(width=600,height=500);b.insert_text((30,40),'B-2')
    pages=[_inspect(d[0],1),_inspect(d[1],2)];d.close()
    x=assemble_pdf_detail_inventory(pages,[{'document_id':'PDF001','page_count':2,'sha256':'a'*64}])
    assert x['all_input_pages_indexed'] is True
    assert x['page_count']==2 and x['region_count']==32
    assert x['expected_region_count']==32
    assert sum(x['region_status_counts'].values())==32
    assert not x['semantic_details_fully_interpreted']
    assert not x['complete'] and not x['quantity_approval_count']


def test_missing_pages_are_error_not_fake_coverage():
    d,p=_page();x=_inspect(p);d.close()
    with pytest.raises(ValueError,match='Missing'):
        assemble_pdf_detail_inventory([x],[{'document_id':'PDF001','page_count':2}])


def test_duplicate_pages_are_error():
    d,p=_page();x=_inspect(p);d.close()
    with pytest.raises(ValueError,match='Duplicate'):
        assemble_pdf_detail_inventory([x,x],[{'document_id':'PDF001','page_count':1}])


def test_wrong_document_ids_are_rejected():
    d,p=_page();x=_inspect(p);d.close()
    with pytest.raises(ValueError,match='Missing'):
        assemble_pdf_detail_inventory([x],[{'document_id':'PDF002','page_count':1}])


def test_duplicate_zone_ids_rejected():
    d,p=_page();x=_inspect(p);d.close()
    x['regions'][1]['region_id']=x['regions'][0]['region_id']
    result=assemble_pdf_detail_inventory([x],[{'document_id':'PDF001','page_count':1}])
    assert not result['all_input_pages_indexed']
    assert any('DUPLICATE_REGION' in v for v in result['errors'])


def test_invalid_grid_configuration_rejected():
    d,p=_page();
    for r,c in [(0,4),(4,0),(1,1),(9,4),(4,9)]:
        with pytest.raises(ValueError):_inspect(p,rows=r,columns=c)
    d.close()


def test_nondrawing_text_is_indexed_not_misclassified_as_detail():
    d,p=_page('blank');p.insert_text((12,12),'An ordinary sheet note')
    x=_inspect(p);d.close()
    assert x['detail_title_anchors']==[]
    assert x['coverage_status']=='EXAMINED'


def test_page_anchors_do_not_count_as_segmentation_or_finance():
    d,p=_page('detail');x=_inspect(p);d.close()
    assert x['explicit_detail_anchor_count']==2
    assert x['region_count']==16
    assert all(z['role']=='PAGE_EVIDENCE_ZONE_NOT_SEGMENTED_DETAIL' for z in x['regions'])
    assert x['financially_payable'] is False


def test_page_number_and_source_identity_checked():
    d,p=_page()
    with pytest.raises(ValueError):inventory_pdf_page_regions(p,document_id='',page_number=1)
    with pytest.raises(ValueError):inventory_pdf_page_regions(p,document_id='PDF001',page_number=0)
    d.close()


def test_unbounded_budget_rejected():
    d,p=_page()
    for m in (0,-1,100001):
        with pytest.raises(ValueError):_inspect(p,max_paths=m)
    d.close()


def test_records_sheet_kind_without_inventing_component():
    d,p=_page('vector');x=_inspect(p,sheet_kind='foundation_plan');d.close()
    assert x['sheet_kind']=='foundation_plan'
    assert x['coverage_status']=='UNRESOLVED'


def test_more_than_one_pdf_document_all_pages_accounted_for():
    d,p=_page();first=inventory_pdf_page_regions(p,document_id='PDF001',page_number=1);d.close()
    d,p=_page('text');second=inventory_pdf_page_regions(p,document_id='PDF002',page_number=1);d.close()
    x=assemble_pdf_detail_inventory([first,second],
      [{'document_id':'PDF001','page_count':1},{'document_id':'PDF002','page_count':1}])
    assert x['page_count']==2 and x['all_input_pages_indexed']
    assert x['region_count']==32


def test_line_only_cad_sheet_is_unresolved_not_empty():
    d,p=_page('blank')
    p.draw_line((100,0),(100,490))
    result=_inspect(p);d.close()
    assert result['coverage_status']=='UNRESOLVED'
    assert any(x['vector_path_count'] for x in result['regions'])


def test_forced_incorrect_bbox_fails_tile_coverage_check():
    d,p=_page();row=_inspect(p);d.close()
    row['regions'][0]['bbox_pt'][0] += 50.0
    result=assemble_pdf_detail_inventory([row],[{'document_id':'PDF001','page_count':1}])
    assert not result['all_input_pages_indexed']
    assert any(e.startswith('INVALID_TILE_BBOX') for e in result['errors'])


def test_missing_tile_row_fails_even_if_region_count_matches():
    d,p=_page();row=_inspect(p);d.close()
    row['regions'][1]['tile_row']=20
    result=assemble_pdf_detail_inventory([row],[{'document_id':'PDF001','page_count':1}])
    assert not result['all_input_pages_indexed']
    assert any('MISSING_TILE_CELL' in e for e in result['errors'])