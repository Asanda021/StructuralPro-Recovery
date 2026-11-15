"""PDF type mark word bbox witnesses: synthetic input, no financial approvals."""
import pytest
pymupdf = pytest.importorskip('pymupdf')

from core.drawings.pdf_type_word_witness import index_pdf_type_words
from core.drawings.pdf_sheet_detail_inventory import (
    inventory_pdf_page_regions, assemble_pdf_detail_inventory,
)


def _page():
    d=pymupdf.open();p=d.new_page(width=450,height=380)
    p.insert_text((20,40),'Beam Detail B1')
    p.insert_text((60,115),'B-1')
    p.insert_text((260,160),'C2')
    p.insert_text((280,190),'T3')
    return d,p


def test_word_bboxes_distinguish_detail_title_from_drawing_label():
    d,p=_page()
    anchor={'anchor_id':'PDF001:p1:title1','document_id':'PDF001',
            'page':1,'bbox_pt':[15,20,155,45]}
    x=index_pdf_type_words(p,document_id='PDF001',page_number=1,title_anchors=[anchor])
    d.close()
    assert x['status']=='INDEXED_TYPE_WORD_POSITIONS'
    assert x['all_words_examined']
    assert {w['type_tag'] for w in x['type_word_witnesses']}=={'B1','C2','T3'}
    b=[w for w in x['type_word_witnesses'] if w['type_tag']=='B1']
    assert len(b)==2
    assert len([w for w in b if w['status']=='TITLE_TEXT_MENTION_NOT_MEMBER'])==1
    assert len([w for w in b if w['status']=='ISOLATED_TYPE_WORD_POSITION_CANDIDATE'])==1
    assert len({w['witness_id'] for w in x['type_word_witnesses']})==4
    assert all(w['financially_payable'] is False for w in x['type_word_witnesses'])


def test_words_not_reconstructed_from_unrelated_separate_tokens():
    d=pymupdf.open();p=d.new_page(width=300,height=250)
    p.insert_text((30,40),'C 2')
    x=index_pdf_type_words(p,document_id='PDF001',page_number=1,title_anchors=[])
    d.close()
    assert x['type_word_witness_count']==0
    assert x['all_words_examined']


def test_word_budget_blocks_without_partial_candidates():
    d,p=_page()
    x=index_pdf_type_words(p,document_id='PDF001',page_number=1,
                           title_anchors=[],max_words=2)
    d.close()
    assert x['status']=='BLOCKED_EXCESSIVE_TYPE_WORDS'
    assert x['type_word_witnesses']==[] and not x['all_words_examined']


def test_foreign_or_duplicate_anchor_rejected():
    d,p=_page()
    item={'anchor_id':'PDF001:p1:title1','document_id':'PDF002',
          'page':1,'bbox_pt':[10,10,100,100]}
    with pytest.raises(ValueError,match='foreign'):
        index_pdf_type_words(p,document_id='PDF001',page_number=1,title_anchors=[item])
    item['document_id']='PDF001'
    with pytest.raises(ValueError,match='foreign'):
        index_pdf_type_words(p,document_id='PDF001',page_number=1,title_anchors=[item,item])
    d.close()


def test_sheet_inventory_preserves_all_word_witnesses_without_boq():
    d,p=_page()
    inv=inventory_pdf_page_regions(p,document_id='PDF001',page_number=1)
    d.close()
    cov=assemble_pdf_detail_inventory(
        [inv],[{'document_id':'PDF001','page_count':1}])
    assert cov['all_input_pages_indexed'] and cov['all_type_word_pages_examined']
    assert cov['type_word_index_page_count']==1
    assert cov['localized_type_word_witness_count']>=4
    assert any(x['status']=='TITLE_TEXT_MENTION_NOT_MEMBER'
               for x in cov['localized_type_word_witnesses'])
    assert all(not x['quantity_approved'] for x in cov['localized_type_word_witnesses'])
    assert cov['quantity_approval_count']==0
