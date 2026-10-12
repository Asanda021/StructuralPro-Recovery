from pathlib import Path

from core.ai.local_engine import LocalAIEngine


def test_light_engine_has_no_model_or_vision():
    engine = LocalAIEngine(model_dir=Path("."), edition="light")
    assert not engine.has_llm_model
    assert not engine.has_vision_model


def test_standard_engine_uses_base_tier(tmp_path):
    engine = LocalAIEngine(model_dir=tmp_path, edition="standard")
    assert engine.tier.value == "base"
    assert not engine.has_llm_model


def test_pro_engine_requires_both_model_and_mmproj(tmp_path):
    engine = LocalAIEngine(model_dir=tmp_path, edition="pro")
    assert engine.tier.value == "takeoff"
    assert not engine.has_vision_model
