from pathlib import Path
import pytest
from core.security import SecurityBoundaryError, validate_backup_file, validate_output_path, validate_project_id, validate_project_name

def test_security_accepts_safe_values():
    assert validate_project_id("project-01_A") == "project-01_A"
    assert validate_project_name("پروژه نمونه") == "پروژه نمونه"

@pytest.mark.parametrize("value", ["", "../escape", "a/b", "a b", "x" * 81])
def test_security_rejects_unsafe_ids(value):
    with pytest.raises(SecurityBoundaryError):
        validate_project_id(value)

def test_security_rejects_invalid_names():
    with pytest.raises(SecurityBoundaryError):
        validate_project_name("")
    with pytest.raises(SecurityBoundaryError):
        validate_project_name("x" * 201)

def test_security_rejects_wrong_output_suffix(tmp_path: Path):
    with pytest.raises(SecurityBoundaryError):
        validate_output_path(tmp_path / "report.exe", (".pdf", ".xlsx"))

def test_security_validates_backup_file(tmp_path: Path):
    good = tmp_path / "project.spbackup"
    good.write_text("{}", encoding="utf-8")
    assert validate_backup_file(good) == good
    with pytest.raises(SecurityBoundaryError):
        validate_backup_file(tmp_path / "missing.spbackup")
