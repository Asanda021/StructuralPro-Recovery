from core.ai.edition_models import AITier, ai_model_spec_for_edition, ai_tier_for_edition


def test_ai_tier_matches_edition_contract():
    assert ai_tier_for_edition("light") is AITier.NONE
    assert ai_tier_for_edition("standard") is AITier.BASE
    assert ai_tier_for_edition("pro") is AITier.TAKEOFF
    assert ai_tier_for_edition("enterprise") is AITier.TAKEOFF


def test_standard_has_text_model_only():
    spec = ai_model_spec_for_edition("standard")
    assert spec is not None
    assert spec.tier is AITier.BASE
    assert spec.model_filename.endswith(".gguf")
    assert spec.mmproj_filename is None


def test_pro_and_enterprise_have_multimodal_assets():
    for edition in ("pro", "enterprise"):
        spec = ai_model_spec_for_edition(edition)
        assert spec is not None
        assert spec.tier is AITier.TAKEOFF
        assert spec.model_filename.endswith(".gguf")
        assert spec.mmproj_filename.endswith(".gguf")
        assert spec.model_sha256 and spec.mmproj_sha256


def test_light_has_no_ai_model():
    assert ai_model_spec_for_edition("light") is None
