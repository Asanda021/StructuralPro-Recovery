from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]

def test_compliance_inventory_exists_and_has_no_license_claims_without_evidence():
    text=(ROOT/"docs/THIRD_PARTY_COMPLIANCE.md").read_text(encoding="utf-8")
    assert "Pending release evidence" in text
    assert "not a claim" in text

def test_requirements_are_explicit_and_optional_integrations_are_not_hidden():
    text=(ROOT/"requirements.txt").read_text(encoding="utf-8")
    assert "pypdf" in text and "PySide6" in text
    assert "# ezdxf" in text
    assert "# ifcopenshell" in text

def test_release_workflow_has_deterministic_artifact_inputs():
    text=(ROOT/".github/workflows/windows-release.yml").read_text(encoding="utf-8")
    assert "actions/checkout@v4" in text
    assert "Get-Content VERSION" in text
    assert "actions/upload-artifact@v4" in text
