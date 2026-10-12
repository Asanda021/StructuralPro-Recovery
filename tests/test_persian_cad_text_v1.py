from core.cad.persian_text_v1 import (
    cad_text_height,
    is_rtl_cad_text,
    normalize_cad_text,
)


def test_normalizes_persian_unicode_escape_and_preserves_persian():
    assert normalize_cad_text(r"\U+0645\U+0647\U+0631") == "مهر"
    assert normalize_cad_text("سلام") == "سلام"
    assert is_rtl_cad_text("طبقه اول")


def test_decodes_common_mtext_line_break_and_symbols():
    assert normalize_cad_text(r"طبقه\Pاول") == "طبقه\nاول"
    assert normalize_cad_text("قطر %%c20 و زاویه %%d90") == "قطر Ø20 و زاویه °90"


def test_removes_format_controls_without_dropping_text():
    assert normalize_cad_text(r"{\fTahoma|b0|i0;ستون}") == "ستون"
    assert normalize_cad_text(r"مساحت\~ناخالص") == "مساحت\u00a0ناخالص"
    assert not is_rtl_cad_text("COLUMN A1")


def test_height_uses_only_finite_positive_plausible_values():
    assert cad_text_height({"height": 3.5}) == 3.5
    assert cad_text_height({"height": -1, "char_height": "bad"}) == 2.5
    assert cad_text_height({"text_height": 1e20}) == 2.5
