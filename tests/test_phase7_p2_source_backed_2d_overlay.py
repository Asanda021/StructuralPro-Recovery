"""Bounded Phase 7 priority 2: genuine source-pinned vector overlay tests."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import xml.etree.ElementTree as ET

import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.reports.source_backed_2d_overlay import build_source_backed_2d_overlay


OUTER = [(10, 10), (150, 10), (150, 150), (10, 150)]
HOLE = [(40, 40), (70, 40), (70, 70), (40, 70)]


def _case(tmp_path, *, holes=(), vector=True, member="W1"):
    import pymupdf
    path = tmp_path / "drawing.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=200)
        if vector:
            page.draw_rect(pymupdf.Rect(10, 10, 150, 150))
        else:
            page.insert_text((20, 20), "No vector geometry")
        doc.save(path)
    session = DrawingTakeoffSession(str(path))
    session.calibrate(1, 1, 1)
    item = session.add_polygon(
        [Point(*p) for p in OUTER],
        holes=[[Point(*p) for p in hole] for hole in holes],
        opening_refs=["بازشو O1"] if holes else [],
        source="pdf-explicit-region",
        floor_id="L1", member_id=member,
        quantity_owner="صفحه برداری مستند",
    )
    return path, session, item


def _overlay(session, item):
    return build_source_backed_2d_overlay(
        session.to_dict(), project_id="P", revision="R1", page=1,
        selected_takeoff_ids=(item.id,),
    )


def test_source_pdf_vector_overlay_preserves_exact_member_identity_and_source(tmp_path):
    path, session, item = _case(tmp_path)
    before = deepcopy(session.to_dict())
    result = _overlay(session, item)
    assert session.to_dict() == before
    assert result == _overlay(session, item)
    manifest = result["manifest"]
    assert manifest["source_sha256"] == sha256(path.read_bytes()).hexdigest()
    assert manifest["revision"] == "R1"
    assert manifest["financial_mutation"] is False
    assert manifest["quantity_authority"] is False
    assert manifest["links"][0]["member_id"] == "W1"
    assert manifest["links"][0]["floor_id"] == "L1"
    assert manifest["links"][0]["boq_row_id"] is None
    assert manifest["svg_sha256"] == sha256(result["svg"].encode()).hexdigest()
    root = ET.fromstring(result["svg"])
    assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) == 1


def test_deducted_opening_is_drawn_as_hole_without_inventing_boq(tmp_path):
    _, session, item = _case(tmp_path, holes=(HOLE,))
    result = _overlay(session, item)
    assert result["svg"].count(" Z") == 2
    assert 'fill-rule="evenodd"' in result["svg"]
    assert result["manifest"]["links"][0]["quantity"] == "18700"
    assert result["manifest"]["links"][0]["boq_row_id"] is None


def test_decimal_coordinates_and_xml_special_characters_are_safe(tmp_path):
    _, session, item = _case(tmp_path, member="W<&1")
    result = _overlay(session, item)
    assert "&lt;&amp;" in result["svg"]
    assert "W<&1" not in result["svg"]
    assert ET.fromstring(result["svg"]) is not None


def test_changed_source_bytes_are_rejected(tmp_path):
    path, session, item = _case(tmp_path)
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="SHA-256"):
        _overlay(session, item)


def test_text_only_pdf_does_not_acquire_geometry_authority(tmp_path):
    _, session, item = _case(tmp_path, vector=False)
    with pytest.raises(ValueError, match="برداری"):
        _overlay(session, item)


def test_corrupted_source_geometry_and_review_identity_are_rejected(tmp_path):
    _, session, item = _case(tmp_path)
    payload = session.to_dict()
    payload["items"][0]["geometry_evidence"]["net_m2"] = "999"
    with pytest.raises(ValueError):
        build_source_backed_2d_overlay(
            payload, project_id="P", revision="R1", page=1,
            selected_takeoff_ids=(item.id,),
        )
    payload = session.to_dict()
    payload["items"][0]["geometry_evidence"]["member_id"] = ""
    with pytest.raises(ValueError):
        build_source_backed_2d_overlay(
            payload, project_id="P", revision="R1", page=1,
            selected_takeoff_ids=(item.id,),
        )


def test_count_only_is_not_falsely_drawn_as_real_plan(tmp_path):
    import pymupdf
    path = tmp_path / "count.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=200)
        page.draw_rect(pymupdf.Rect(10, 10, 100, 100))
        doc.save(path)
    session = DrawingTakeoffSession(str(path))
    item = session.add_count(count=2, page=1, source="manual-count")
    with pytest.raises(ValueError, match="هندسه سطحی"):
        _overlay(session, item)


@pytest.mark.parametrize("wrong", [
    {"project_id": "", "revision": "R1", "page": 1},
    {"project_id": "P", "revision": "", "page": 1},
    {"project_id": "P", "revision": "R1", "page": True},
    {"project_id": "P", "revision": "R1", "page": 2},
])
def test_invalid_project_revision_page_rejected(tmp_path, wrong):
    _, session, item = _case(tmp_path)
    with pytest.raises(ValueError):
        build_source_backed_2d_overlay(
            session.to_dict(), selected_takeoff_ids=(item.id,), **wrong
        )


def test_missing_selected_item_or_duplicate_selection_fails_closed(tmp_path):
    _, session, item = _case(tmp_path)
    for selected in ((), (item.id, item.id), ("UNKNOWN",)):
        with pytest.raises(ValueError):
            build_source_backed_2d_overlay(
                session.to_dict(), project_id="P", revision="R1", page=1,
                selected_takeoff_ids=selected,
            )
