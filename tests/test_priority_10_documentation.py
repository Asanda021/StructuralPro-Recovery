from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

REQUIRED_RELEASE_DOCS = (
    "USER_GUIDE.md",
    "DEVELOPER_GUIDE.md",
    "INSTALLATION.md",
    "RELEASE_CHECKLIST.md",
    "CONFIGURATION.md",
    "LICENSE.md",
    "BACKUP_RESTORE.md",
    "TROUBLESHOOTING.md",
    "RELEASE_PROCESS.md",
)


def test_priority_10_release_documentation_exists():
    for name in REQUIRED_RELEASE_DOCS:
        path = DOCS / name
        assert path.is_file(), name
        assert path.read_text(encoding="utf-8").strip(), name


def test_release_docs_preserve_versioning_and_offline_boundaries():
    user = (DOCS / "USER_GUIDE.md").read_text(encoding="utf-8")
    release = (DOCS / "RELEASE_PROCESS.md").read_text(encoding="utf-8")
    license_doc = (DOCS / "LICENSE.md").read_text(encoding="utf-8")
    assert "offline-first" in user
    assert "VERSION" in release
    assert "private/signing secret" in license_doc


def test_release_checklist_contains_real_build_evidence_gate():
    text = (DOCS / "RELEASE_CHECKLIST.md").read_text(encoding="utf-8")
    assert "Windows runner build status is actually observed" in text
    assert "Installer artifact is retained" in text
