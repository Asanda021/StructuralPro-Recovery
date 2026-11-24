"""Synthetic end-to-end coverage gate for normal multi-PDF intake."""
import pytest
pymupdf = pytest.importorskip('pymupdf')
from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _build(tmp_path, name='drawings.pdf', texts=('Axis Plan','Column Type Plan','Connection Detail C-1')):
    d=pymupdf.open()
    for label in texts:
        p=d.new_page(width=842,height=595)
        if label:p.insert_text((30,28),label,fontsize=12)
        if 'Plan' in label:
            for x in (150,300,450):p.draw_line((x,130),(x,470))
            for y in (130,300,470):p.draw_line((150,y),(450,y))
        if 'Detail' in label:p.draw_rect(pymupdf.Rect(200,160,400,380))
    out=tmp_path/name
    d.save(out);d.close()
    return out


def test_all_pages_and_regions_pass_through_main_pdf_intake(tmp_path):
    path=_build(tmp_path)
    r=inspect_pdf_sheet_set([path])
    inventory=r['sheet_detail_inventory']
    assert inventory['page_count']==3
    assert inventory['region_count']==48
    assert inventory['expected_region_count']==48
    assert inventory['all_input_pages_indexed'] is True
    assert len(inventory['sheet_inventory'])==3
    assert inventory['region_status_counts']['UNRESOLVED']>0
    assert inventory['quantity_approval_count']==0 and not inventory['complete']
    assert r['quantity_approval_count']==0
    assert r['physical_member_count'] is None


def test_all_pages_of_multiple_files_are_indexed_without_duplicate_count(tmp_path):
    a=_build(tmp_path,'a.pdf',texts=('Beam Detail B-1','Plan'))
    b=_build(tmp_path,'b.pdf',texts=('','Electrical Detail'))
    r=inspect_pdf_sheet_set([a,b])
    inventory=r['sheet_detail_inventory']
    assert inventory['page_count']==4
    assert inventory['region_count']==64
    assert set(x['document_id'] for x in inventory['sheet_inventory'])=={'PDF001','PDF002'}
    assert len({(x['document_id'],x['page']) for x in inventory['sheet_inventory']})==4
    assert len({x['region_id'] for x in inventory['region_inventory']})==64
    assert inventory['all_input_pages_indexed']
    assert not inventory['semantic_details_fully_interpreted']


def test_multiple_titles_in_one_page_not_reduced_to_one_detail(tmp_path):
    d=pymupdf.open();p=d.new_page(width=842,height=595)
    p.insert_text((30,30),'Connection Detail B1',fontsize=12)
    p.insert_text((420,400),'Column Detail C2',fontsize=12)
    p.draw_line((20,100),(300,500))
    p.draw_line((400,120),(700,500))
    f=tmp_path/'two-details.pdf';d.save(f);d.close()
    r=inspect_pdf_sheet_set([f])
    anchors=r['sheet_detail_inventory']['detail_title_anchors']
    assert len(anchors)==2
    assert len(set(x['anchor_id'] for x in anchors))==2
    assert all(x['status']=='UNRESOLVED' for x in anchors)
    assert r['sheet_detail_inventory']['region_count']==16


def test_blank_page_does_not_disappear(tmp_path):
    f=_build(tmp_path,texts=('',))
    r=inspect_pdf_sheet_set([f])
    assert r['sheet_detail_inventory']['sheet_inventory'][0]['coverage_status']=='EXAMINED'
    assert r['sheet_detail_inventory']['page_count']==1


def test_region_inventory_marks_never_infer_boq_amount(tmp_path):
    f=_build(tmp_path,texts=('Column Detail C-3',))
    r=inspect_pdf_sheet_set([f])
    assert all(not x['financially_payable'] for x in r['sheet_detail_inventory']['region_inventory'])
    assert not r['sheet_detail_inventory']['complete']
    assert r['complete'] is False