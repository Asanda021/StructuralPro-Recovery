"""CAD/PDF beam label resolution must always be evidence-only and fail-closed."""
from types import SimpleNamespace
import pytest
from core.drawings.beam_detail_match import cad_beam_evidence, pdf_beam_evidence, suggested_link, parse_section_hint, validate_evidence_link


def entity(text, x=10, y=20, handle="A1", typ="TEXT"):
    return SimpleNamespace(entity_type=typ, handle=handle, layer="BEAMS",
                           data={"text": text, "insert": (x, y)})


def document(*entities):
    return SimpleNamespace(entities=list(entities))


def test_exact_tag_no_substring_collision():
    out = cad_beam_evidence(document(entity("B1", handle="1"),
                                     entity("B10", handle="2"), entity("XB1", handle="3")), "B1")
    assert len(out) == 1 and out[0].handle == "1"


def test_persian_digits_and_case():
    assert len(cad_beam_evidence(document(entity("b۱ / 30x50 cm")), "B1")) == 1


def test_scene_origin_selection_uses_model_transform():
    out = cad_beam_evidence(document(entity("B1", x=110, y=190)), "B1",
                            region=(8, 8, 5, 5), scene_origin=(100, 200))
    assert len(out) == 1 and out[0].in_selected_region and out[0].located


def test_outside_region_still_candidate_but_not_located_inside():
    out = cad_beam_evidence(document(entity("B1", x=110, y=190)), "B1",
                            region=(20, 20, 5, 5), scene_origin=(100, 200))
    assert not out[0].in_selected_region


def test_no_transform_region_fails_closed():
    with pytest.raises(ValueError, match="تبدیل مختصات"):
        cad_beam_evidence(document(entity("B1")), "B1", region=(0, 0, 10, 10))


def test_two_tags_are_ambiguous_never_autoselected():
    out = suggested_link(cad_beam_evidence(document(entity("B1", handle="1"),entity("B1", handle="2")), "B1"))
    assert len(out["candidates"]) == 2
    assert out["status"] == "needs_explicit_selection" and not out["quantity_approved"]


def test_pdf_page_text_is_unlocated_and_unapproved():
    out = pdf_beam_evidence("B1 30x50 cm\nB10 20x40\nB1 STIRRUPS", "B1", page=2)
    assert len(out) == 2 and all(not x.in_selected_region and not x.located for x in out)
    assert suggested_link(out)["requires_review"]


def test_no_match_is_not_assumed_absent():
    result = suggested_link(pdf_beam_evidence("B5", "B1", page=1))
    assert result["status"] == "no_match" and not result["quantity_approved"]


def test_duplicate_cad_handles_block_linking():
    with pytest.raises(ValueError, match="تکراری"):
        cad_beam_evidence(document(entity("B1", handle="1"),entity("B1", handle="1")), "B1")


def test_corrupt_coordinates_fail_closed():
    with pytest.raises(ValueError, match="مختصات"):
        cad_beam_evidence(document(entity("B1", x=float("nan"))), "B1", scene_origin=(0, 0))


def test_non_text_entities_are_ignored():
    assert cad_beam_evidence(document(entity("B1", typ="LINE")), "B1") == ()


def test_unusable_beam_tag_rejected():
    with pytest.raises(ValueError, match="شناسه تیر"):
        pdf_beam_evidence("B1", "", page=1)


def test_explicit_section_dimensions_proposed_in_meters_only():
    assert parse_section_hint("B1 b=30 cm h=50 cm", "B1") == {"width_m": .3, "depth_m": .5}


def test_unlabeled_dimensions_never_inferred():
    assert parse_section_hint("B1 30x50", "B1") is None
    assert parse_section_hint("B1 b=30cm", "B1") is None
    assert parse_section_hint("B10 b=30cm h=50cm", "B1") is None


def test_conflicting_dimensions_never_proposed():
    assert parse_section_hint("B1 b=30cm b=40cm h=50cm", "B1") is None


def test_persian_explicit_section():
    assert parse_section_hint("B۱ عرض=۳۰ سانتی‌متر ارتفاع=۵۰ سانتی‌متر", "B1") == {"width_m": .3, "depth_m": .5}


def test_drawing_evidence_link_consistency():
    source = {"mode": "drawing", "page": 2,
              "detail_evidence": {"beam_tag": "B1", "kind": "cad",
                                  "source_ref": "cad:page:2:handle:A1", "text": "b۱", "page": 2}}
    validate_evidence_link(source, "B1")
    with pytest.raises(ValueError, match="تیر دیگری"):
        validate_evidence_link(source, "B2")
    source["detail_evidence"]["page"] = 3
    with pytest.raises(ValueError, match="صفحه"):
        validate_evidence_link(source, "B1")


def test_invalid_evidence_does_not_pass_validation():
    src = {"mode": "manual", "page": 1, "detail_evidence": {"beam_tag": "B1"}}
    with pytest.raises(ValueError, match="نقشه معتبر"):
        validate_evidence_link(src, "B1")