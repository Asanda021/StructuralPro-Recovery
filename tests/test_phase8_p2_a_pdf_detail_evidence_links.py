"""Synthetic negative and positive evidence-linkage tests; never BOQ."""
from copy import deepcopy

import pytest

pymupdf=pytest.importorskip('pymupdf')
from core.drawings.pdf_detail_evidence_links import link_pdf_detail_geometry_evidence
from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set
from core.drawings.pdf_detail_object_index import build_pdf_detail_object_index


def _source(*, two_titles=False, separate_groups=False, blocked=False):
    title={'candidate_id':'DETAIL_TITLE:PDF001:p1:title1',
           'kind':'EXPLICIT_DETAIL_TITLE','document_id':'PDF001','page':1,
           'title_anchor_id':'PDF001:p1:title1','status':'SINGLE_FAMILY_DETAIL_TITLE_CANDIDATE',
           'linked_type_candidate_ids':[],'financially_payable':False}
    anchors=[{'anchor_id':title['title_anchor_id'],'document_id':'PDF001','page':1}]
    objects=[title]
    if two_titles:
        extra=dict(title, candidate_id='DETAIL_TITLE:PDF001:p1:title2',
                   title_anchor_id='PDF001:p1:title2')
        objects.append(extra)
        anchors.append({'anchor_id':extra['title_anchor_id'],'document_id':'PDF001','page':1})
    groups=[]
    names=['PDF001:p1:title1']
    if two_titles:
        names.append('PDF001:p1:title2')
    for i in range(2 if separate_groups else 1):
        groups.append({'candidate_id':f'PDF001:p1:vector_group{i+1:05d}',
                       'document_id':'PDF001','page':1,
                       'source_path_indices':[i+1],
                       'nearby_title_anchor_ids':names.copy(),
                       'financially_payable':False,'detail_boundary_verified':False})
    pages=[{'document_id':'PDF001','page':1,'groups':groups if not blocked else [],
            'all_source_paths_grouped':not blocked}]
    cov={'sheet_inventory':[{'document_id':'PDF001','page':1}],
         'detail_title_anchors':anchors}
    return cov,objects,pages


def test_single_title_single_geometry_only_proposed_and_no_member_amount():
    cov,objects,pages=_source()
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['geometry_group_link_count']==1
    assert ledger['title_coverage_count']==1
    assert ledger['possible_page_local_links']==1
    assert ledger['possible_coarse_type_references']==0
    link=ledger['geometry_group_link_records'][0]
    assert link['proposed_title_candidate_id']==objects[0]['candidate_id']
    assert link['status']=='PROPOSED_GROUP_NEAR_SINGLE_EXPLICIT_TITLE'
    assert not link['type_verified'] and not link['physical_member_verified']
    assert not link['financially_payable'] and not link['quantity_approved']
    assert ledger['physical_member_count'] is None and ledger['quantity_approval_count']==0


def test_multiple_titles_one_group_never_picks_one_arbitrarily():
    cov,objects,pages=_source(two_titles=True)
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    link=ledger['geometry_group_link_records'][0]
    assert link['status']=='BLOCKED_GROUP_NEAR_MULTIPLE_TITLES'
    assert link['proposed_title_candidate_id'] is None
    assert ledger['title_coverage_count']==2 and ledger['possible_page_local_links']==0


def test_one_title_two_disconnected_groups_requires_review():
    cov,objects,pages=_source(separate_groups=True)
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['possible_page_local_links']==0
    assert all(x['status']=='BLOCKED_TITLE_OR_GROUP_AMBIGUITY'
               for x in ledger['geometry_group_link_records'])
    assert ledger['title_coverage_records'][0]['status']=='BLOCKED_TITLE_NEAR_MULTIPLE_VECTOR_GROUPS'


def test_missing_group_title_preserved_with_status():
    cov,objects,pages=_source()
    pages[0]['groups'][0]['nearby_title_anchor_ids']=[]
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['geometry_group_link_records'][0]['status']=='UNRESOLVED_GROUP_WITHOUT_TITLE'
    assert ledger['title_coverage_records'][0]['status']=='UNRESOLVED_TITLE_WITHOUT_NEARBY_VECTOR_GROUP'
    assert ledger['all_vector_groups_accounted_for'] and ledger['all_titles_accounted_for']


def test_blocked_title_never_links_to_geometry():
    cov,objects,pages=_source()
    objects[0]['status']='BLOCKED_DETAIL_TITLE_SOURCE_INCOMPLETE'
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['geometry_group_link_records'][0]['status']=='BLOCKED_TITLE_OR_GROUP_AMBIGUITY'
    assert ledger['geometry_group_link_records'][0]['proposed_title_candidate_id'] is None


def test_blocked_page_no_partial_groups_or_title_link():
    cov,objects,pages=_source(blocked=True)
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['geometry_group_link_count']==0
    assert ledger['blocked_geometry_page_count']==1
    assert ledger['title_coverage_records'][0]['status']=='BLOCKED_GEOMETRY_GROUPING_INCOMPLETE'
    assert ledger['possible_page_local_links']==0


def test_foreign_title_group_and_duplicate_group_rejected():
    cov,objects,pages=_source()
    pages[0]['groups'][0]['nearby_title_anchor_ids']=['PDF002:p1:title1']
    with pytest.raises(ValueError,match='Foreign or missing'):
        link_pdf_detail_geometry_evidence(cov,objects,pages)
    cov,objects,pages=_source()
    pages[0]['groups'].append(deepcopy(pages[0]['groups'][0]))
    with pytest.raises(ValueError,match='duplicate'):
        link_pdf_detail_geometry_evidence(cov,objects,pages)


def test_cross_document_or_missing_page_group_does_not_create_link():
    cov,objects,pages=_source()
    pages[0]['document_id']='PDF002'
    with pytest.raises(ValueError,match='foreign'):
        link_pdf_detail_geometry_evidence(cov,objects,pages)
    cov,objects,pages=_source()
    missing=link_pdf_detail_geometry_evidence(cov,objects,[])
    assert missing['possible_page_local_links']==0
    assert missing['title_coverage_records'][0]['status']=='BLOCKED_NO_VECTOR_GROUP_INDEX'


def test_coarse_mark_reference_never_promoted_to_verified_member():
    cov,objects,pages=_source()
    objects[0]['linked_type_candidate_ids']=['TYPE_MARK:PDF001:p1:B1']
    objects.append({'candidate_id':'TYPE_MARK:PDF001:p1:B1','kind':'EXPLICIT_TEXT_TYPE_MARK',
                    'document_id':'PDF001','page':1,
                    'proposed_detail_title_id':objects[0]['candidate_id'],
                    'status':'TYPE_MARK_TEXT_ONLY_CANDIDATE','financially_payable':False})
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    link=ledger['geometry_group_link_records'][0]
    assert link['coarse_zone_type_mark_candidate_ids']==['TYPE_MARK:PDF001:p1:B1']
    assert link['type_source_quality']=='COARSE_PAGE_TILE_ONLY_NOT_GLYPH_POSITION'
    assert link['type_verified'] is False and link['physical_member_verified'] is False


def test_two_conflicting_type_marks_never_select_arbitrary_type():
    cov,objects,pages=_source()
    objects[0]['linked_type_candidate_ids']=['TYPE_MARK:PDF001:p1:B1',
                                              'TYPE_MARK:PDF001:p1:B2']
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['possible_coarse_type_references']==0
    assert ledger['geometry_group_link_records'][0]['coarse_zone_type_mark_candidate_ids']==[]


def test_real_pdf_intake_has_same_source_title_and_geometry_link_candidates(tmp_path):
    d=pymupdf.open();page=d.new_page(width=400,height=400)
    page.insert_text((30,40),'Beam Detail B1')
    page.draw_rect(pymupdf.Rect(45,90,110,150))
    path=tmp_path/'detail.pdf';d.save(path);d.close()
    report=inspect_pdf_sheet_set([path])
    ledger=report['detail_object_index']['geometry_detail_link_ledger']
    assert ledger['all_vector_groups_accounted_for']
    assert ledger['all_titles_accounted_for']
    assert ledger['geometry_group_link_count']>=1
    assert ledger['title_coverage_count']>=1
    assert all(x['financially_payable'] is False for x in ledger['geometry_group_link_records'])
    assert ledger['quantity_approval_count']==0
    assert ledger['complete'] is False



def test_two_independent_details_on_one_sheet_link_only_to_nearby_title(tmp_path):
    doc=pymupdf.open()
    page=doc.new_page(width=500,height=400)
    page.insert_text((30,50),'Beam Detail B1')
    page.draw_rect(pymupdf.Rect(40,80,100,140))
    page.insert_text((250,225),'Column Detail C2')
    page.draw_rect(pymupdf.Rect(260,255,315,320))
    path=tmp_path/'two_provisional_details.pdf'
    doc.save(path);doc.close()
    graph=inspect_pdf_sheet_set([path])['detail_object_index']
    ledger=graph['geometry_detail_link_ledger']
    assert ledger['title_coverage_count']==2
    assert ledger['geometry_group_link_count']==2
    assert ledger['possible_page_local_links']==2
    assert len({x['proposed_title_candidate_id'] for x in
                ledger['geometry_group_link_records']})==2
    assert all(x['status']=='PROPOSED_GROUP_NEAR_SINGLE_EXPLICIT_TITLE'
               and x['financially_payable'] is False
               and x['type_verified'] is False
               and x['physical_member_verified'] is False
               for x in ledger['geometry_group_link_records'])
    assert ledger['quantity_approval_count']==0
    assert graph['physical_member_count'] is None



def test_partially_returned_groups_from_blocked_page_are_rejected_but_audited():
    cov,objects,pages=_source()
    pages[0]['all_source_paths_grouped']=False
    ledger=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert ledger['blocked_geometry_page_count']==1
    assert ledger['rejected_partial_group_count']==1
    assert ledger['geometry_group_link_records']==[]
    assert ledger['title_coverage_records'][0]['status']=='BLOCKED_GEOMETRY_GROUPING_INCOMPLETE'
    assert ledger['possible_page_local_links']==0
    assert ledger['quantity_approval_count']==0



def _put_word(cov, word_id, tag, box, *, status='ISOLATED_TYPE_WORD_POSITION_CANDIDATE'):
    word={'witness_id':f'PDF001:p1:word{word_id:06d}',
          'document_id':'PDF001','page':1,'source_word_index':word_id,
          'type_tag':tag,'bbox_pt':box,'status':status,'financially_payable':False,
          'localization':'PDF_WORD_BBOX_NOT_GLYPH_OR_MEMBER'}
    cov.setdefault('localized_type_word_witnesses',[]).append(word)
    cov['type_word_page_index']=[{
        'document_id':'PDF001','page':1,'status':'INDEXED_TYPE_WORD_POSITIONS',
        'all_words_examined':True,
        'type_word_witnesses':cov['localized_type_word_witnesses']}]
    cov['localized_type_word_witness_count']=len(cov['localized_type_word_witnesses'])
    return word


def test_isolated_type_word_near_unique_beam_geometry_is_only_proposed():
    cov,objects,pages=_source()
    objects[0]['family_candidates']=['beam']
    pages[0]['groups'][0]['bbox_pt']=[40,60,130,160]
    witness=_put_word(cov,1,'B1',[60,85,78,98])
    title=_put_word(cov,2,'B1',[20,25,38,38],status='TITLE_TEXT_MENTION_NOT_MEMBER')
    out=link_pdf_detail_geometry_evidence(cov,objects,pages)
    rec=out['geometry_group_link_records'][0]
    assert rec['localized_proposed_type_tag']=='B1'
    assert rec['localized_type_word_witness_ids']==[witness['witness_id']]
    assert rec['localized_word_link_status']=='PROPOSED_LOCALIZED_TYPE_WORD_NEAR_DETAIL_GROUP'
    assert out['localized_word_proposed_link_count']==1
    assert out['localized_title_word_mentions']==1
    assert title['witness_id'] in out['unlinked_localized_type_word_witness_ids']
    assert rec['type_verified'] is False and rec['physical_member_verified'] is False
    assert out['quantity_approval_count']==0


def test_incompatible_type_word_is_blocked_without_guessing():
    cov,objects,pages=_source()
    objects[0]['family_candidates']=['column']
    pages[0]['groups'][0]['bbox_pt']=[40,60,130,160]
    _put_word(cov,1,'B1',[60,85,78,98])
    out=link_pdf_detail_geometry_evidence(cov,objects,pages)
    rec=out['geometry_group_link_records'][0]
    assert rec['localized_word_link_status']=='BLOCKED_WORD_DETAIL_FAMILY_MISMATCH'
    assert rec['localized_proposed_type_tag'] is None


def test_multiple_localized_words_near_one_geometry_are_ambiguous():
    cov,objects,pages=_source()
    objects[0]['family_candidates']=['beam']
    pages[0]['groups'][0]['bbox_pt']=[40,60,130,160]
    _put_word(cov,1,'B1',[60,85,78,98])
    _put_word(cov,2,'B2',[90,85,108,98])
    out=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert out['geometry_group_link_records'][0]['localized_word_link_status']=='BLOCKED_MULTIPLE_LOCAL_TYPE_WORDS'
    assert out['localized_word_proposed_link_count']==0


def test_one_localized_word_near_two_groups_is_not_assigned_twice():
    cov,objects,pages=_source(separate_groups=True)
    objects[0]['family_candidates']=['beam']
    pages[0]['groups'][0]['bbox_pt']=[0,0,10,10]
    pages[0]['groups'][1]['bbox_pt']=[35,0,45,10]
    _put_word(cov,1,'B1',[18,0,26,10])
    out=link_pdf_detail_geometry_evidence(cov,objects,pages)
    assert all(x['localized_word_link_status']=='BLOCKED_WORD_NEAR_MULTIPLE_VECTOR_GROUPS'
               for x in out['geometry_group_link_records'])
    assert out['localized_word_proposed_link_count']==0


def test_cross_page_words_and_missing_index_cannot_attach():
    cov,objects,pages=_source()
    pages[0]['groups'][0]['bbox_pt']=[40,60,130,160]
    w=_put_word(cov,1,'B1',[60,85,78,98])
    w['document_id']='PDF002'
    with pytest.raises(ValueError,match='Invalid or duplicate'):
        link_pdf_detail_geometry_evidence(cov,objects,pages)
    cov,objects,pages=_source()
    cov['localized_type_word_witnesses']=[{
        'witness_id':'PDF001:p1:word000001','document_id':'PDF001',
        'page':1,'type_tag':'B1','bbox_pt':[60,85,78,98],
        'status':'ISOLATED_TYPE_WORD_POSITION_CANDIDATE','financially_payable':False,
    }]
    with pytest.raises(ValueError,match='require document'):
        link_pdf_detail_geometry_evidence(cov,objects,pages)


def test_pdf_integration_word_inside_title_is_not_physical_mark(tmp_path):
    d=pymupdf.open();p=d.new_page(width=400,height=300)
    p.insert_text((25,35),'Beam Detail B1')
    p.draw_rect(pymupdf.Rect(40,60,120,150))
    p.insert_text((65,105),'B-1')
    src=tmp_path/'beam_word_position.pdf';d.save(src);d.close()
    out=inspect_pdf_sheet_set([src])['detail_object_index']
    ledger=out['geometry_detail_link_ledger']
    assert ledger['localized_word_witness_count']>=2
    assert ledger['localized_title_word_mentions']>=1
    assert ledger['localized_isolated_word_count']>=1
    assert ledger['localized_word_proposed_link_count']>=1
    assert all(not x['type_verified'] and not x['financially_payable']
               for x in ledger['geometry_group_link_records'])
