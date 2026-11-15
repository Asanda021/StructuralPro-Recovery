"""Synthetic, source-private-safe detail-object candidate and coverage tests."""
from copy import deepcopy

import pytest

from core.drawings.pdf_detail_object_index import build_pdf_detail_object_index
from core.drawings.pdf_sheet_detail_inventory import (
    inventory_pdf_page_regions, assemble_pdf_detail_inventory,
)


def _coverage(*, marks=(), title=None, title_box=(5, 5, 80, 22),
              vector_regions=(1,), documents=1, pages=1, blocked=False):
    """All indexed areas are synthetic, no real project geometry."""
    zones=[]; sheets=[]; anchors=[]; docs=[]
    for doc in range(1, documents + 1):
        did=f'PDF{doc:03d}'
        docs.append({'document_id':did,'page_count':pages,'source_name':f'test_{doc}.pdf'})
        for page in range(1,pages + 1):
            key=f'{did}:p{page}'
            sheets.append({'document_id':did,'page':page,'sheet_kind':'UNKNOWN_SHEET_KIND',
                           'coverage_status':'UNRESOLVED','region_count':4})
            for i in range(4):
                row=i//2; col=i%2
                zones.append({'region_id':f'{key}:r{row+1}:c{col+1}',
                  'document_id':did,'page':page,
                  'bbox_pt':[col*100,row*100,(col+1)*100,(row+1)*100],
                  'status':'BLOCKED' if blocked and i==0 else 'UNRESOLVED',
                  'searchable_member_marks':list(marks if i==0 else ()),
                  'vector_path_count':12 if i in vector_regions else 0,
                  'image_block_count':0})
            if title is not None:
                anchors.append({'anchor_id':f'{key}:title1',
                                'document_id':did,'page':page,'bbox_pt':title_box,
                                'title_preview':title,'status':'UNRESOLVED'})
    return {'all_input_pages_indexed':True,'errors':[],'documents':docs,
            'sheet_inventory':sheets,'region_inventory':zones,
            'detail_title_anchors':anchors,'note_anchors':[]}


def test_per_page_type_and_title_are_distinct_nonpayable_candidates():
    report=build_pdf_detail_object_index(_coverage(title='Beam B1 detail', marks=['B1']))
    assert len(report['detail_candidates'])==2
    title=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_DETAIL_TITLE')
    mark=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_TEXT_TYPE_MARK')
    assert title['family_candidates']==['beam']
    assert mark['family_candidates']==['beam']
    assert mark['proposed_detail_title_id']==title['candidate_id']
    assert mark['title_association_status']=='PROPOSED_SAME_REGION_TITLE_ASSOCIATION'
    assert title['linked_type_candidate_ids']==[mark['candidate_id']]
    assert not title['detail_boundary_verified'] and not mark['physical_member_verified']
    assert report['physical_member_count'] is None and report['quantity_approval_count']==0
    assert report['complete'] is False


def test_multiple_family_connection_title_stays_multi_family():
    report=build_pdf_detail_object_index(_coverage(title='Beam to Column Connection'))
    item=report['detail_candidates'][0]
    assert set(item['family_candidates'])=={'beam','column','reinforcement_connection'}
    assert item['status']=='MULTI_FAMILY_DETAIL_TITLE_CANDIDATE'
    assert not item['detail_boundary_verified']


def test_no_title_still_indexes_foundation_mark_and_visual_unassigned():
    report=build_pdf_detail_object_index(_coverage(marks=['F3'],vector_regions=(0,3)))
    marks=report['detail_candidates']
    assert len(marks)==1 and marks[0]['type_tag']=='F3'
    assert marks[0]['family_candidates']==['foundation']
    assert marks[0]['proposed_detail_title_id'] is None
    assert report['visual_region_count']==2
    assert len(report['unassigned_visual_regions'])==1
    assert report['unassigned_visual_regions'][0]['region_id'].endswith('r2:c2')
    assert report['visual_semantics_unresolved_region_count']==2


def test_type_T_not_guessed_as_beam_or_foundation_and_newline_normalized():
    report=build_pdf_detail_object_index(_coverage(marks=['T\n10']))
    item=report['detail_candidates'][0]
    assert item['type_tag']=='T10' and item['family_candidates']==[]
    assert item['physical_member_verified'] is False


def test_tag_dedup_within_page_but_retains_all_source_zones():
    cover=_coverage(marks=['B1'])
    cover['region_inventory'][1]['searchable_member_marks']=['B1']
    report=build_pdf_detail_object_index(cover)
    marks=[x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_TEXT_TYPE_MARK']
    assert len(marks)==1 and len(marks[0]['region_ids'])==2


def test_same_tag_different_pages_provisional_no_double_count():
    report=build_pdf_detail_object_index(_coverage(marks=['F1'],pages=2))
    assert report['type_mark_candidate_count']==2
    assert len(report['potential_same_document_type_references'])==1
    ref=report['potential_same_document_type_references'][0]
    assert ref['pages']==[1,2] and ref['type_tag']=='F1'
    assert ref['physical_member_count'] is None and not ref['financially_payable']


def test_same_mark_cross_document_must_not_link_without_revision():
    report=build_pdf_detail_object_index(_coverage(marks=['C1'],documents=2))
    assert len(report['detail_candidates'])==2
    assert report['potential_same_document_type_references']==[]
    assert report['physical_member_count'] is None


def test_incompatible_same_tile_title_never_assigns_wrong_type():
    report=build_pdf_detail_object_index(_coverage(title='Foundation detail',marks=['B1']))
    mark=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_TEXT_TYPE_MARK')
    assert mark['proposed_detail_title_id'] is None
    assert mark['title_association_status']=='BLOCKED_AMBIGUOUS_OR_INCOMPATIBLE_TITLE_ASSOCIATION'


def test_multiple_detail_titles_same_tile_no_arbitrary_binding():
    cover=_coverage(title='Beam detail',marks=['B1'])
    title=deepcopy(cover['detail_title_anchors'][0]);title['anchor_id']='PDF001:p1:title2'
    cover['detail_title_anchors'].append(title)
    report=build_pdf_detail_object_index(cover)
    mark=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_TEXT_TYPE_MARK')
    assert len(mark['source_title_candidate_ids'])==2
    assert mark['proposed_detail_title_id'] is None


def test_missing_title_position_rejected_not_silently_omitted():
    cover=_coverage(title='Beam detail')
    cover['detail_title_anchors'][0]['bbox_pt']=[900,900,999,999]
    with pytest.raises(ValueError,match='no location'):
        build_pdf_detail_object_index(cover)


def test_incomplete_page_coverage_is_rejected():
    cover=_coverage()
    cover['all_input_pages_indexed']=False
    with pytest.raises(ValueError,match='incomplete'):
        build_pdf_detail_object_index(cover)


def test_missing_page_zones_raises_even_when_flag_is_true():
    cover=_coverage(pages=2)
    cover['region_inventory']=[z for z in cover['region_inventory'] if z['page']==1]
    with pytest.raises(ValueError,match='missing coverage'):
        build_pdf_detail_object_index(cover)


def test_duplicate_visual_zone_identity_is_rejected():
    cover=_coverage()
    cover['region_inventory'].append(deepcopy(cover['region_inventory'][0]))
    with pytest.raises(ValueError,match='Invalid source zone'):
        build_pdf_detail_object_index(cover)


def test_invalid_type_mark_source_rejected_no_partial_commit():
    cover=_coverage(marks=['T\0x'])
    with pytest.raises(ValueError,match='Unparseable'):
        build_pdf_detail_object_index(cover)


def test_blocked_source_mark_preserves_unapproved_status():
    report=build_pdf_detail_object_index(_coverage(marks=['C1'],blocked=True))
    mark=report['detail_candidates'][0]
    assert mark['status']=='BLOCKED_TYPE_MARK_SOURCE_INCOMPLETE'
    assert not mark['financially_payable'] and not mark['quantity_approved']


def test_max_candidate_budget_fails_closed():
    with pytest.raises(ValueError,match='budget'):
        build_pdf_detail_object_index(_coverage(marks=['B1'],title='Beam detail'),max_candidates=1)


def test_all_drawn_zones_remain_unresolved_after_index():
    report=build_pdf_detail_object_index(_coverage(vector_regions=(0,1,2,3)))
    assert report['visual_region_count']==4
    assert report['visual_regions_accounted_for']==4
    assert len(report['unassigned_visual_regions'])==4
    assert report['semantic_details_fully_interpreted'] is False
    assert not report['complete']


def test_real_synthetic_pdf_multiple_details_and_untitled_geometry(tmp_path):
    import pymupdf
    doc=pymupdf.open()
    page=doc.new_page(width=600,height=400)
    page.insert_text((35,45),'Beam detail B1')
    page.insert_text((355,105),'Column section C2')
    page.insert_text((35,275),'F1')
    page.draw_rect(pymupdf.Rect(70,70,150,140))
    page.draw_rect(pymupdf.Rect(385,70,465,140))
    page.draw_rect(pymupdf.Rect(400,300,500,340))
    path=tmp_path/'multi-details.pdf'
    doc.save(path);doc.close()
    with pymupdf.open(path) as src:
        inv=inventory_pdf_page_regions(src[0],document_id='PDF001',page_number=1)
    complete=assemble_pdf_detail_inventory([inv],
        [{'document_id':'PDF001','page_count':1,'source_name':path.name}])
    graph=build_pdf_detail_object_index(complete)
    assert graph['page_count']==1
    assert graph['visual_region_count']>0
    assert graph['detail_title_candidate_count']>=2
    assert 'B1' in {x['type_tag'] for x in graph['detail_candidates'] if x['type_tag']}
    assert graph['unassigned_visual_regions']
    assert graph['quantity_approval_count']==0 and graph['physical_member_count'] is None


def test_bounded_total_mark_count_rejected_without_approval():
    cover=_coverage()
    cover['region_inventory'][0]['searchable_member_marks']=['B1']*1001
    with pytest.raises(ValueError,match='Unbounded member-mark'):
        build_pdf_detail_object_index(cover)


def test_persian_presentation_form_column_detail_family():
    report=build_pdf_detail_object_index(_coverage(title='ﺟﺰﯾﯿــــﺎت ﺳــــﺘﻮن ﻫﺎ'))
    title=report['detail_candidates'][0]
    assert title['family_candidates']==['column']
    assert title['status']=='SINGLE_FAMILY_DETAIL_TITLE_CANDIDATE'


def test_persian_beam_to_column_connection_retains_all_component_families():
    report=build_pdf_detail_object_index(_coverage(title='ﺟﺰﺋﯿــــﺎت اﺗﺼــــﺎل ﭘــﻞ ﺑــﻪ ﺳــــﺘﻮن'))
    assert set(report['detail_candidates'][0]['family_candidates'])=={
        'beam','column','reinforcement_connection'}


def test_financial_full_width_text_not_auto_approved_as_detail():
    cover=_coverage(title='Beam connection with many amounts and units',
                    title_box=(2,4,198,22),marks=['B1'])
    report=build_pdf_detail_object_index(cover)
    title=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_DETAIL_TITLE')
    mark=next(x for x in report['detail_candidates'] if x['kind']=='EXPLICIT_TEXT_TYPE_MARK')
    assert title['status']=='BLOCKED_BROAD_TITLE_TEXT_NOT_DETAIL'
    assert mark['proposed_detail_title_id'] is None


def test_coverage_page_count_not_accepted_from_flag_alone():
    cover=_coverage(pages=2)
    cover['sheet_inventory']=cover['sheet_inventory'][:1]
    with pytest.raises(ValueError,match='missing or foreign'):
        build_pdf_detail_object_index(cover)


def test_foreign_zone_id_does_not_misbind():
    cover=_coverage()
    cover['region_inventory'][0]['region_id']='PDF002:p9:r1:c1'
    with pytest.raises(ValueError,match='source zone'):
        build_pdf_detail_object_index(cover)