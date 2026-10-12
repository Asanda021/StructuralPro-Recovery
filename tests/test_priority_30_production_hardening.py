from pathlib import Path
from core.platform.hardening import run_hardening
from core.platform.release_security import ROOT
def test_release_security_root_points_to_repository_root():
    assert (ROOT/"VERSION").exists()
    assert (ROOT/"core").exists()
def test_production_hardening_checks_current_release_surface():
    result=run_hardening(Path(ROOT))
    assert result.version_valid and result.packaging_present
def test_hardening_is_fail_closed_for_missing_packaging(tmp_path):
    (tmp_path/"VERSION").write_text("0.1.0",encoding="utf-8")
    result=run_hardening(tmp_path)
    assert not result.packaging_present and not result.ready
