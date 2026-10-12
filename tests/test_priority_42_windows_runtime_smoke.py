"""Priority 42 — Windows runtime smoke contract."""
from pathlib import Path
from tests.historical_contracts import historical_root

HISTORY = historical_root()  # Isolated historical contract, never active Actions.

ROOT = Path(__file__).resolve().parents[1]


def test_app_has_ci_runtime_smoke_exit_path():
    source = (ROOT / "app/main.py").read_text(encoding="utf-8")
    assert "STRUCTURALPRO_SMOKE" in source
    assert "app.processEvents()" in source
    assert "app.quit()" in source
    assert "w.close()" in source
    assert "return 0" in source


def test_windows_workflow_executes_application_smoke():
    source = (HISTORY / ".github/workflows/windows-smoke.yml").read_text(encoding="utf-8")
    assert "STRUCTURALPRO_SMOKE:" in source
    assert "1" in source
    assert "from app.main import main" in source
