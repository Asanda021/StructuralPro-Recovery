"""P37 production deployment contract tests."""
from pathlib import Path
from tests.historical_contracts import historical_root

HISTORY = historical_root()  # Isolated historical contract, never active Actions.
ROOT = Path(__file__).resolve().parents[1]

def test_p37_deployment_contract_is_complete():
    workflow = HISTORY / ".github" / "workflows" / "p37-real-product-deployment.yml"
    doc = ROOT / "docs" / "P37_REAL_PRODUCT_DEPLOYMENT.md"
    assert workflow.exists()
    assert doc.exists()
    text = workflow.read_text(encoding="utf-8")
    for marker in (
        "actions/checkout@v4", "actions/setup-python@v5",
        "packaging/build_windows.ps1", "packaging/windows_installer_smoke.ps1",
        "packaging/generate_sha256.ps1", "packaging/generate_release_manifest.ps1",
        "actions/upload-artifact@v4", "softprops/action-gh-release@v2",
    ):
        assert marker in text, marker
    # Release tags and PR code are NOT owner binary-build permission.
    import re
    assert re.search(r"(?m)^  workflow_dispatch:\s*$", text)
    assert not re.search(r"(?m)^  (?:push|pull_request|pull_request_target|schedule|release|workflow_call|workflow_run|repository_dispatch):", text)
    for necessary in (
        "github.event_name == 'workflow_dispatch'",
        "github.actor == 'Asanda021'",
        "inputs.build_approved == true",
        "github.ref == 'refs/heads/main'",
        "github.repository == 'Asanda021/StructuralPro'",
        "name: binary-build-approval",
        "secrets.STRUCTURALPRO_BINARY_BUILD_APPROVAL",
    ):
        assert necessary in text, necessary
    assert text.index("environment:") < text.index("packaging/build_windows.ps1")
    assert text.index("Require environment-scoped owner authorization") < text.index("packaging/build_windows.ps1")

def test_p37_is_desktop_first_and_does_not_fake_cloud_deployment():
    text = (ROOT / "docs" / "P37_REAL_PRODUCT_DEPLOYMENT.md").read_text(encoding="utf-8")
    assert "Windows desktop" in text
    assert "GitHub Release" in text
    assert "cloud-hosted" in text
    assert "not" in text.lower()
