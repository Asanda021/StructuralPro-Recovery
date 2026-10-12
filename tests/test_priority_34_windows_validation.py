"""Priority 34 — Windows packaging and path compatibility checks."""
from __future__ import annotations
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def test_windows_packaging_surface_is_complete():
    required = (
        ROOT / "packaging" / "build_windows.ps1",
        ROOT / "packaging" / "installer.iss",
        ROOT / "packaging" / "structuralpro.spec",
        ROOT / "VERSION",
    )
    assert all(path.is_file() for path in required)

def test_windows_build_script_is_fail_closed():
    script = (ROOT / "packaging" / "build_windows.ps1").read_text(encoding="utf-8")
    assert '$ErrorActionPreference="Stop"' in script
    assert "StructuralPro" in script

def test_installer_and_spec_reference_real_application_surface():
    installer = (ROOT / "packaging" / "installer.iss").read_text(encoding="utf-8")
    spec = (ROOT / "packaging" / "structuralpro.spec").read_text(encoding="utf-8")
    assert "StructuralPro" in installer
    assert "app" in spec
    assert "main.py" in spec
    assert "core" in spec

def test_runtime_data_paths_remain_platform_neutral(tmp_path):
    from core.platform.application import StructuralProApp
    data_dir = tmp_path / "Windows Data" / "StructuralPro"
    app = StructuralProApp(data_dir)
    app.create_project("Windows Smoke", "WIN34")
    app.add_takeoff("WIN34", "building", "slab_volume", length=2, width=3, thickness=0.2)
    assert app.open_project("WIN34")["id"] == "WIN34"
    assert (data_dir / "projects.db").is_file()
