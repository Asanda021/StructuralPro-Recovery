"""Priority 41 — CI dependency parity with the supported application surface."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = [ROOT / ".github/workflows/tests.yml", ROOT / ".github/workflows/full-tests.yml", ROOT / ".github/workflows/windows-smoke.yml"]

def test_ci_workflows_install_canonical_runtime_requirements():
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        assert "python -m pip install -r requirements.txt" in text, workflow

def test_ci_workflows_keep_test_runner_explicit():
    for workflow in WORKFLOWS:
        text = workflow.read_text(encoding="utf-8")
        assert "python -m pip install pytest" in text, workflow
