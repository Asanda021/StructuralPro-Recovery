from core.ai.local_engine import LocalAIEngine


def test_local_ai_has_no_network_requirement(tmp_path):
    engine = LocalAIEngine(model_dir=tmp_path / "models")
    assert engine.is_local is True
    result = engine.answer("آفلاین کار می‌کند؟")
    assert "اینترنت" in result.text


def test_local_ai_project_check(tmp_path):
    engine = LocalAIEngine(model_dir=tmp_path / "models")
    result = engine.inspect_project({"name": "نمونه", "takeoffs": []})
    assert "متره" in result.text
