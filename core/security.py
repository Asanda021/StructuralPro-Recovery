"""Security boundary helpers for local project inputs."""
from pathlib import Path
import re

_ID = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
MAX_NAME = 200
MAX_BACKUP_BYTES = 25 * 1024 * 1024

class SecurityBoundaryError(ValueError):
    pass

def validate_project_id(value):
    value = str(value or "").strip()
    if not _ID.fullmatch(value):
        raise SecurityBoundaryError("invalid project id")
    return value

def validate_project_name(value):
    value = str(value or "").strip()
    if not value or len(value) > MAX_NAME:
        raise SecurityBoundaryError("invalid project name")
    return value

def validate_output_path(path, allowed_suffixes=()):
    target = Path(path).expanduser()
    if not str(target).strip() or target.name in {"", ".", ".."}:
        raise SecurityBoundaryError("invalid output path")
    if allowed_suffixes and target.suffix.lower() not in {s.lower() for s in allowed_suffixes}:
        raise SecurityBoundaryError("unsupported output suffix")
    return target

def validate_backup_file(path):
    target = validate_output_path(path, (".json", ".spbackup"))
    if not target.is_file():
        raise SecurityBoundaryError("backup file does not exist")
    if target.stat().st_size > MAX_BACKUP_BYTES:
        raise SecurityBoundaryError("backup file exceeds safety limit")
    return target
