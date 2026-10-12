"""Priority 40 — cross-platform version and optional-capability contract."""
from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

def canonical_version() -> str:
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip()

def test_android_version_is_derived_from_canonical_version():
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    assert 'rootProject.file("../VERSION")' in gradle
    assert "versionName = canonicalVersion" in gradle

def test_android_version_contract_is_not_hardcoded():
    gradle = (ROOT / "android" / "app" / "build.gradle.kts").read_text(encoding="utf-8")
    assert not re.search(r'versionName\s*=\s*"\d+\.\d+\.\d+"', gradle)

def test_optional_drawing_dependencies_are_explicit():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "# Optional drawing integrations:" in requirements
    assert "# ezdxf" in requirements
    assert "# ifcopenshell" in requirements

def test_optional_drawing_backends_fail_with_actionable_messages():
    dwg = (ROOT / "core" / "drawings" / "dwg_takeoff.py").read_text(encoding="utf-8")
    bim = (ROOT / "core" / "drawings" / "bim_quantities.py").read_text(encoding="utf-8")
    assert "کتابخانه ezdxf برای تحلیل DXF نصب نیست" in dwg
    assert "Install ifcopenshell for local IFC parsing" in bim

def test_canonical_version_is_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", canonical_version())
