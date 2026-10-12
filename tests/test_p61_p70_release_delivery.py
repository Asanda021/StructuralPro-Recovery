import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts" / "ervira"

def load(n):
    return json.loads((CONTRACTS / f"p{n:02d}.json").read_text(encoding="utf-8"))

def test_p61_p70_are_runtime_implemented_but_customer_release_is_fail_closed():
    for n in range(61, 71):
        c = load(n)
        assert c["runtime_status"] == "implemented"
        assert c["release_ready"] is False

def test_release_contracts_cover_all_delivery_stages():
    names = [load(n)["name"] for n in range(61, 71)]
    assert names == [
        "Release Registry","Version Synchronization","Build Synchronization",
        "Release Notes Synchronization","Artifact Registry","SHA-256 Verification",
        "Download Authorization","Windows Installer Delivery","Installation Detection",
        "Installed-Version + License E2E Verification"
    ]

def test_release_notes_match_canonical_version():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
    assert f"## {version}" in notes

def test_windows_release_workflow_contains_required_delivery_gates():
    workflow = (ROOT / ".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    for token in [
        "Validate version","Build payload","Validate payload","Build installer",
        "Validate installer","Run installed application acceptance smoke",
        "Generate SHA256 checksums","Generate release manifest",
        "Validate release artifact hashes","Generate release registry",
        "Validate release registry","Upload artifacts"
    ]:
        assert token in workflow
