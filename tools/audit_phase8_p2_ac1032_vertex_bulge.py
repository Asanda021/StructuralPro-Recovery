"""Run the AC1032 VERTEX provenance audit using private, SHA-bound inputs.

No user drawing, handles, hashes or coordinates may be committed or printed.
The diagnostic never authorizes any quantity, even when both DXFs agree.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from core.drawings.dwg_legacy_vertex_bulge_audit import (
    audit_ac1032_legacy_vertex_bulge_parity,
)
from tools.audit_phase8_p2_opaque_source_bytes import (
    _no_symlink_ancestors,
    _private_directory_guard,
    private_output_destination,
    write_private_report,
)

_CONFIG_FIELDS = frozenset({
    "original_dwg", "reference_dxf", "candidate_dxf",
    "original_sha256", "reference_sha256", "candidate_sha256",
    "output_json",
})


def read_private_vertex_config(path: str | Path) -> dict:
    """Read 0600, private JSON; sensitive locations and SHA stay off argv."""
    config_path = Path(path).expanduser()
    if not config_path.is_absolute() or config_path.suffix.lower() != ".json":
        raise ValueError("Absolute private JSON configuration is required")
    _no_symlink_ancestors(config_path)
    if not config_path.is_file():
        raise ValueError("Private configuration file is missing")
    project = Path(__file__).resolve().parents[1]
    resolved = config_path.resolve(strict=True)
    if resolved == project or project in resolved.parents:
        raise ValueError("Private configuration cannot reside inside source repository")
    _private_directory_guard(resolved.parent)
    if os.name == "nt":
        raise ValueError("WINDOWS_PRIVATE_ACL_NOT_VERIFIED")
    if resolved.stat().st_mode & 0o077 or resolved.stat().st_size > 16384:
        raise ValueError("Private configuration must be a 0600 JSON below 16 KiB")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(resolved, flags)
    with os.fdopen(fd, "r", encoding="utf-8") as f:
        payload = f.read(16385)
    if len(payload) > 16384:
        raise ValueError("Private configuration exceeds safe limit")
    config = json.loads(payload)
    if not isinstance(config, dict) or set(config) != _CONFIG_FIELDS:
        raise ValueError("Private configuration has unexpected or missing fields")
    for key in ("original_dwg", "reference_dxf", "candidate_dxf"):
        loc = Path(config[key]).expanduser() if isinstance(config[key], str) else None
        if loc is None or not loc.is_absolute() or loc.is_symlink() or not loc.is_file():
            raise ValueError("Source inputs must be absolute, existing regular files")
        _no_symlink_ancestors(loc)
        location = loc.resolve(strict=True)
        if location == project or project in location.parents:
            raise ValueError("Private source inputs cannot be committed into the repository")
    private_output_destination(config["output_json"])
    return config


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-config", required=True,
                        help="Absolute POSIX 0600 private JSON containing file paths, hashes and output path")
    args = parser.parse_args(argv)
    try:
        settings = read_private_vertex_config(args.private_config)
        report = audit_ac1032_legacy_vertex_bulge_parity(
            settings["original_dwg"], settings["reference_dxf"], settings["candidate_dxf"],
            original_sha256=settings["original_sha256"],
            reference_sha256=settings["reference_sha256"],
            candidate_sha256=settings["candidate_sha256"],
        )
        write_private_report(settings["output_json"], report)
    except Exception as exc:
        # Never print exception text: paths, handles or private byte snippets
        # may appear in third-party parser failures.
        print("BLOCKED_PRIVATE_VERTEX_AUDIT:", type(exc).__name__)
        return 2
    print(report["status"],
          "legacy vertex differences:", report["bulge_difference_count"],
          "order differences:", report["parent_vertex_order_difference_count"],
          "closed/flags differences:", report["parent_polyline_flags_difference_count"],
          "financial approvals:", report["financial_quantity_rows_approved"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
