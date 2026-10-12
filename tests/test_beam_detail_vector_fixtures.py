"""Synthetic vector drawing evidence checks; not a Windows GUI acceptance test."""
from types import SimpleNamespace

import pytest
from core.drawings.beam_detail_match import cad_beam_evidence, pdf_beam_evidence, parse_section_hint


def test_ezdxf_roundtrip_b1_tag_and_explicit_dimension_evidence(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    path = tmp_path / "sample_beam.dxf"
    drawing = ezdxf.new()
    drawing.header["$INSUNITS"] = 6  # metre
    drawing.modelspace().add_text("B1 b=30cm h=50cm", dxfattribs={"insert": (110, 190), "height": 0.2})
    drawing.modelspace().add_text("B10 b=40cm h=50cm", dxfattribs={"insert": (120, 200), "height": 0.2})
    drawing.saveas(path)
    reopened = ezdxf.readfile(path)
    entities = [SimpleNamespace(entity_type=e.dxftype(), layer=e.dxf.layer,
                                handle=e.dxf.handle, data={"text":e.dxf.text,
                                                        "insert":(e.dxf.insert.x,e.dxf.insert.y)})
                for e in reopened.modelspace() if e.dxftype()=="TEXT"]
    result = cad_beam_evidence(SimpleNamespace(entities=entities), "B1", region=(8, 8, 5, 5), scene_origin=(100, 200))
    assert len(result) == 1 and result[0].in_selected_region
    assert parse_section_hint(result[0].text, "B1") == {"width_m": .3, "depth_m": .5}


def test_real_pdf_vector_page_text_remains_unlocated(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "beam-schedule.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72,72), "B1 b=30cm h=50cm")
    document.save(path)
    document.close()
    opened=fitz.open(path)
    try:
        found=pdf_beam_evidence(opened[0].get_text(), "B1", page=1)
    finally:
        opened.close()
    assert len(found)==1 and found[0].kind=="pdf"
    assert not found[0].located and not found[0].in_selected_region
    assert parse_section_hint(found[0].text,"B1")=={"width_m":.3,"depth_m":.5}