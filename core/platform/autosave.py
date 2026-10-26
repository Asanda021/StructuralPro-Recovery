"""Deterministic local autosave and crash-recovery contract."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping
from .backup import create_backup, validate_backup

def create_autosave(project_id: str, revision: int, payload: Mapping[str, Any]) -> dict[str, Any]:
    backup=create_backup(project_id,revision,payload)
    backup["kind"]="autosave"
    return backup

def validate_autosave(snapshot: Mapping[str, Any]) -> list[str]:
    if snapshot.get("kind")!="autosave": return ["invalid autosave kind"]
    return validate_backup({k:v for k,v in snapshot.items() if k!="kind"})

def recover_autosave(snapshot: Mapping[str, Any], *, expected_project_id: str) -> dict[str, Any]:
    errors=validate_autosave(snapshot)
    if errors: raise ValueError("; ".join(errors))
    if snapshot["project_id"]!=expected_project_id: raise ValueError("project_id mismatch")
    return deepcopy(dict(snapshot["payload"]))


# E2 view-state persistence: use the established hashed autosave contract,
# never project financial/engineering payload and never write to SQLite.
import json
import os
import stat
import tempfile
from pathlib import Path

_VIEW_KEYS = frozenset((
    "document_id", "floor_id", "member_id", "zone_id", "current_tab",
    "filter", "zoom_2d", "camera_3d", "pending_review_ids",
))


def _checked_view(view: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(view, Mapping) or set(view) - _VIEW_KEYS:
        raise ValueError("session view contains unsupported or financial fields")
    result = deepcopy(dict(view))
    for key in ("document_id", "floor_id", "member_id", "zone_id", "current_tab", "filter"):
        if key in result and (not isinstance(result[key], str) or len(result[key]) > 256):
            raise ValueError("invalid view identifier")
    if "pending_review_ids" in result:
        ids = result["pending_review_ids"]
        if not isinstance(ids, list) or len(ids) > 100 or any(
            not isinstance(x, str) or len(x) > 256 for x in ids
        ):
            raise ValueError("invalid pending review identifiers")
    import math
    if "zoom_2d" in result and (
        type(result["zoom_2d"]) not in (int, float)
        or not math.isfinite(result["zoom_2d"])
        or not 0.01 <= result["zoom_2d"] <= 1000
    ):
        raise ValueError("invalid 2D zoom")
    if "camera_3d" in result:
        camera = result["camera_3d"]
        if not isinstance(camera, dict) or set(camera) - {"yaw_deg", "pitch_deg", "distance"}:
            raise ValueError("invalid 3D camera")
        if any(type(v) not in (int, float) or not math.isfinite(v)
               for v in camera.values()):
            raise ValueError("invalid 3D camera coordinates")
        if ("distance" in camera and camera["distance"] <= 0) or (
            "pitch_deg" in camera and not -90 <= camera["pitch_deg"] <= 90
        ):
            raise ValueError("invalid 3D camera bounds")
    encoded = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False)
    if len(encoded.encode("utf-8")) > 32768:
        raise ValueError("session view too large")
    return result


def write_view_session(
    target: str | Path,
    *,
    project_id: str,
    revision: int,
    subject_id: str,
    view: Mapping[str, Any],
    document_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Publish a new, immutable session snapshot; never replace a live snapshot.

    The caller supplies the identity obtained from the OS-authorized store.
    A UI string is not a substitute for that authentication boundary.
    """
    if not isinstance(subject_id, str) or not subject_id.strip():
        raise ValueError("authenticated subject required")
    if not isinstance(document_hashes, Mapping) or any(
        not isinstance(k, str) or not isinstance(v, str) or
        len(v) != 64 or any(c not in "0123456789abcdef" for c in v.lower())
        for k, v in document_hashes.items()
    ):
        raise ValueError("invalid source document digests")
    state = _checked_view(view)
    if state.get("document_id") and state["document_id"] not in document_hashes:
        raise ValueError("selected document has no verified digest")
    payload = {
        "session_schema": 1,
        "subject_id": subject_id,
        "view": state,
        "documents": dict(document_hashes),
    }
    snapshot = create_autosave(project_id, revision, payload)
    dest = Path(target)
    if dest.exists() or dest.is_symlink():
        raise FileExistsError("session snapshot already exists")
    if not dest.parent.is_dir() or dest.parent.is_symlink():
        raise ValueError("session parent must be an existing regular directory")
    raw = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    tmp = None
    try:
        fd, name = tempfile.mkstemp(prefix=".session-", suffix=".tmp", dir=dest.parent)
        tmp = Path(name)
        with os.fdopen(fd, "wb") as out:
            if os.name == "posix":
                os.fchmod(out.fileno(), 0o600)
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.link(tmp, dest)  # no-clobber, including concurrent destination creation
        if os.name == "posix":
            directory_fd = os.open(dest.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)
    return snapshot


def read_view_session(
    source: str | Path,
    *,
    project_id: str,
    revision: int,
    subject_id: str,
    document_hashes: Mapping[str, str],
    existing_ids: Mapping[str, set[str]] | None = None,
) -> dict[str, Any]:
    """Return read-only view preferences only if identity and evidence still match.

    Callers must fetch revision, principal and source hashes from the active,
    authorized ProjectStore before invoking this function. No approval or BOQ write.
    """
    path = Path(source)
    mode = path.lstat().st_mode
    if not stat.S_ISREG(mode) or path.is_symlink() or path.parent.is_symlink():
        raise ValueError("unsafe session snapshot path")
    if path.stat().st_size > 65536:
        raise ValueError("session snapshot too large")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    data = recover_autosave(snapshot, expected_project_id=project_id)
    if snapshot["revision"] != revision:
        raise ValueError("session revision conflict")
    if data.get("session_schema") != 1 or data.get("subject_id") != subject_id:
        raise PermissionError("session identity mismatch")
    if data.get("documents") != dict(document_hashes):
        raise ValueError("session source digest conflict")
    view = _checked_view(data.get("view"))
    for key, allowed in (existing_ids or {}).items():
        if key not in _VIEW_KEYS:
            raise ValueError("unsupported selected item verification")
        if view.get(key) and view[key] not in allowed:
            raise ValueError("stale session selection")
    return view
