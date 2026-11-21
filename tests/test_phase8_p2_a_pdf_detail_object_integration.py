"""Full PDF intake -> evidence-zone inventory -> provisional multi-family detail index.

Only synthetic drawings are used; there are no accepted quantities.
"""
import pytest

from core.drawings.pdf_auto_intake import inspect_pdf_sheet_set


def _generate_pdf(path, title, tag, include_visual=True):
    import pymupdf
    doc=pymupdf.open()
    p=doc.new_page(width=600,height=500)
    p.insert_text((35,45),title,fontsize=12)
    p.insert_text((35,100),tag,fontsize=12)
    if include_visual:
        p.draw_rect(pymupdf.Rect(80,140,180,205))
        p.draw_line((350,260),(510,360))
    doc.save(path);doc.close()
    return path


def test_two_pdf_sources_are_indexed_independently_without_assumed_shared_revision(tmp_path):
    one=_generate_pdf(tmp_path/'type_beams.pdf','Beam detail B1','B1')
    two=_generate_pdf(tmp_path/'type_foundations.pdf','Foundation section F2','F2')
    report=inspect_pdf_sheet_set([one,two])
    graph=report['detail_object_index']
    assert graph['page_count']==2
    assert graph['source_coverage_index_complete'] is True
    assert graph['detail_title_candidate_count']==2
    assert graph['type_mark_candidate_count']==2
    assert graph['visual_regions_accounted_for']==graph['visual_region_count']
    assert {(r['document_id'], r['type_tag']) for r in graph['detail_candidates']
            if r['type_tag']}=={('PDF001','B1'),('PDF002','F2')}
    assert graph['potential_same_document_type_references']==[]
    assert graph['complete'] is False and graph['physical_member_count'] is None
    assert graph['quantity_approval_count']==0 and report['quantity_approval_count']==0


def test_unlabeled_visual_strokes_never_disappear_from_end_to_end_index(tmp_path):
    import pymupdf
    d=pymupdf.open();p=d.new_page(width=400,height=300)
    p.draw_line((40,40),(100,40))
    p.draw_line((230,190),(360,220))
    path=tmp_path/'only_lines.pdf';d.save(path);d.close()
    report=inspect_pdf_sheet_set([path])
    graph=report['detail_object_index']
    assert graph['detail_candidates']==[]
    assert graph['unassigned_visual_regions']
    assert graph['visual_regions_accounted_for']==graph['visual_region_count']
    assert all(r['status']=='UNRESOLVED_UNLABELED_VISUAL_REGION'
               for r in graph['unassigned_visual_regions'])
    assert report['complete'] is False