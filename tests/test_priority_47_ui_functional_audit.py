"""Priority 47 — UI functional audit contract."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_quality_control_is_not_hardcoded_as_green():
    source=(ROOT/"app/main.py").read_text(encoding="utf-8")
    assert "اجرای کنترل کیفیت پروژه" in source
    assert "service.validate_project_data(project_id)" in source
    assert "🟢 کنترل ساختار پروژه" not in source
