"""Priority 50 — production-status documentation must match the verified release surface."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_status_documents_reflect_installer_acceptance():
    prod = (ROOT / "docs/PRODUCTION_STATUS.md").read_text(encoding="utf-8")
    proj = (ROOT / "docs/PROJECT_STATUS.md").read_text(encoding="utf-8")
    assert "Priority 49" in prod
    assert "real Windows installer E2E smoke" in prod
    assert "Installer install/run/uninstall smoke acceptance" in proj
    assert "installer packaging and hardware-based model selection must be completed and tested" not in proj


def test_status_documents_keep_external_release_dependencies_explicit():
    prod = (ROOT / "docs/PRODUCTION_STATUS.md").read_text(encoding="utf-8")
    required = (
        "official Iranian annual price-list datasets",
        "GGUF model",
        "DWG converter",
        "code-signing certificate",
    )
    for item in required:
        assert item in prod
