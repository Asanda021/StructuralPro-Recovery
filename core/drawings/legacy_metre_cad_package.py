"""Read-only safe legacy Persian metre ZIP importer with real CAD gating.

No user drawings or spreadsheets are uploaded to GitHub or other services.
Zip is read only from a local file. We do not execute archive members or
implicitly trust cached formula values, text matches, units, or pricing.
"""
from __future__ import annotations

from hashlib import sha256
from pathlib import Path, PurePosixPath
import stat
from tempfile import TemporaryDirectory
from zipfile import ZipFile, BadZipFile

from core.drawings.legacy_metre_cad_reconciliation import LegacyMetreCADReconciler

_REQUIRED = frozenset({"riz metre.xlsx", "gozaresh nahaei.xlsx", "naghshe ha.dwg"})
_MAX_ZIP_BYTES = 50 * 1024 * 1024
_MAX_TOTAL_EXTRACTED = 80 * 1024 * 1024
_MAX_SINGLE_FILE = 50 * 1024 * 1024
_MAX_MEMBERS = 40


def inspect_legacy_metre_package(
    source: str | Path, *, bindings: list[dict] | None = None,
) -> dict:
    path = Path(source)
    if path.suffix.lower() != ".zip" or not path.is_file():
        raise ValueError("Expected an existing real local ZIP archive")
    if not 1 <= path.stat().st_size <= _MAX_ZIP_BYTES:
        raise ValueError("ZIP size outside approved range")
    starting_sha = sha256(path.read_bytes()).hexdigest()
    files = {}
    contents = {}
    try:
        with ZipFile(path, "r") as package:
            members = package.infolist()
            if len(members) > _MAX_MEMBERS:
                raise ValueError("ZIP has too many members")
            total = sum(member.file_size for member in members)
            if total > _MAX_TOTAL_EXTRACTED:
                raise ValueError("ZIP declared expanded size exceeds the limit")
            for member in members:
                raw = member.filename.replace("\\", "/")
                part = PurePosixPath(raw)
                if (part.is_absolute() or ".." in part.parts or
                    not part.parts or ":" in part.parts[0] or "\x00" in raw):
                    raise ValueError("ZIP contains unsafe member path")
                if member.is_dir():
                    continue
                if stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError("ZIP symlinks are not allowed")
                if member.flag_bits & 1:
                    raise ValueError("Encrypted ZIP members not supported")
                name = part.name.casefold()
                if name not in _REQUIRED:
                    # Additional PDF / URL / image entries are not executed or extracted.
                    continue
                if name in files:
                    raise ValueError("Duplicate source file basename in archive")
                if member.file_size <= 0 or member.file_size > _MAX_SINGLE_FILE:
                    raise ValueError("Source member file outside approved bounds")
                blob = package.read(member)
                if len(blob) != member.file_size:
                    raise ValueError("ZIP member length differs from directory")
                contents[name] = blob
                files[name] = {"sha256": sha256(blob).hexdigest(), "bytes": len(blob)}
    except BadZipFile as exc:
        raise ValueError("ZIP cannot be read safely") from exc
    if set(files) != _REQUIRED:
        raise ValueError("ZIP must contain DWG, metre XLSX and summary XLSX exactly once")
    if not contents["naghshe ha.dwg"].startswith(b"AC10"):
        raise ValueError("Original DWG has no recognizable AutoCAD signature")
    if not all(contents[name][:2] == b"PK" for name in ("riz metre.xlsx", "gozaresh nahaei.xlsx")):
        raise ValueError("Excel source is not a genuine XLSX zip container")
    if sha256(path.read_bytes()).hexdigest() != starting_sha:
        raise ValueError("ZIP changed during inspection")
    with TemporaryDirectory(prefix="structuralpro_p8p2_zip_audit_") as tmp:
        root = Path(tmp)
        for name, blob in contents.items():
            (root / name).write_bytes(blob)
        report = LegacyMetreCADReconciler().inspect(
            root / "riz metre.xlsx",
            summary_path=root / "gozaresh nahaei.xlsx",
            drawing_path=root / "naghshe ha.dwg",
            bindings=bindings,
        )
        for name, record in files.items():
            if sha256((root / name).read_bytes()).hexdigest() != record["sha256"]:
                raise ValueError("Extracted source file changed during audit")
    if sha256(path.read_bytes()).hexdigest() != starting_sha:
        raise ValueError("ZIP changed before returning report")
    report["package"] = {
        "zip_sha256": starting_sha, "sources": files,
        "original_dwg_header": contents["naghshe ha.dwg"][:6].decode("ascii", "replace"),
        "user_data_uploaded": False, "read_only": True,
        "safe_member_count": len(files),
    }
    report["release"] = "NO_GO"
    return report
