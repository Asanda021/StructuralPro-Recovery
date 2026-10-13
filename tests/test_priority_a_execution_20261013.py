"""Independent source-attribution regressions; no engineering acceptance claim."""
import pytest

from core.drawings.beam_detail_match import parse_section_hint
from core.drawings.member_evidence import explicit_member_dimensions, index_member_evidence


@pytest.mark.parametrize("text", [
    "B1\nB2 b=30cm h=50cm",
    "B1; B2 b=30cm h=50cm",
    "B1 B2 b=30cm h=50cm",
    "B1 B2-EXTRA b=30cm h=50cm",
    "B1 LONGMEMBER2 b=30cm h=50cm",
    "B۱ B۲ عرض=۳۰ سانتی‌متر ارتفاع=۵۰ سانتی‌متر",
    "B1\nb=30cm h=50cm",
    r"B1\P b=30cm h=50cm",
])
def test_beam_section_never_borrows_dimensions_from_unowned_statement(text):
    assert parse_section_hint(text, "B1") is None


@pytest.mark.parametrize("text", [
    "F1\nF2 LENGTH=2m WIDTH=3m THICKNESS=50cm",
    "F1; F2 LENGTH=2m WIDTH=3m THICKNESS=50cm",
    "F1 F2 LENGTH=2m WIDTH=3m THICKNESS=50cm",
    "F1 F2-EXTRA LENGTH=2m WIDTH=3m THICKNESS=50cm",
    "F۱ F۲ طول=۲m عرض=۳m ضخامت=۵۰cm",
    "F1\nLENGTH=2m WIDTH=3m THICKNESS=50cm",
    r"F1\P LENGTH=2m WIDTH=3m THICKNESS=50cm",
])
def test_foundation_geometry_never_borrows_dimensions_from_unowned_statement(text):
    assert explicit_member_dimensions(text, "isolated_footing", "F1") is None


def test_pdf_index_retains_ambiguous_evidence_without_geometry_proposal():
    class Pages:
        page_count = 1

        def text(self, page):
            return "F1 F2 LENGTH=2m WIDTH=3m THICKNESS=50cm"

    result = index_member_evidence(
        "isolated_footing", "F1", drawing_sha256="a" * 64, pdf_engine=Pages())
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["proposed_geometry"] is None
    assert not result["ready_for_boq"]


def test_single_owned_statement_retains_explicit_unit_conversions():
    assert parse_section_hint("B۱ b=300mm h=50cm", "B1") == {
        "width_m": .3, "depth_m": .5}
    assert explicit_member_dimensions(
        "F۱ LENGTH=2000mm WIDTH=3m THICKNESS=50cm", "isolated_footing", "F1"
    ) == {"length": 2, "width": 3, "thickness": .5}


def test_persian_member_names_with_competing_identity_require_manual_review():
    assert parse_section_hint("تیر۱ تیر۲ b=30cm h=50cm", "تیر۱") is None


def test_dxf_mtext_roundtrip_keeps_evidence_but_rejects_cross_row_geometry(tmp_path):
    import ezdxf
    from core.drawings.dwg_takeoff import DWGTakeoffEngine
    from core.drawings.beam_detail_match import cad_beam_evidence

    path = tmp_path / "beam-mtext.dxf"
    drawing = ezdxf.new()
    drawing.modelspace().add_mtext(r"B1\P b=30cm h=50cm")
    drawing.saveas(path)
    document = DWGTakeoffEngine()._read_dxf(path)
    candidates = cad_beam_evidence(document, "B1")
    assert len(candidates) == 1
    assert parse_section_hint(candidates[0].text, "B1") is None
