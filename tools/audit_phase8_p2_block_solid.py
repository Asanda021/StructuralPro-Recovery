"""Run a read-only SHA-bound BLOCK/SOLID audit with a private-only receipt."""
from __future__ import annotations
import argparse
from core.drawings.dwg_insert_solid_contract import audit_insert_solid
from tools.audit_phase8_p2_opaque_source_bytes import (
    private_output_destination, write_private_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Source DWG v DXF BLOCK/SOLID audit (never payable approval)")
    parser.add_argument("original_dwg")
    parser.add_argument("diagnostic_dxf")
    parser.add_argument("output_json", help="Absolute private JSON outside Git; no overwrite")
    parser.add_argument("--dwg-sha256", required=True)
    parser.add_argument("--dxf-sha256", required=True)
    args = parser.parse_args()
    try:
        # The original audit contains source SHA and block identifiers. Treat
        # its receipt as PRIVATE, never a regular artifact or console log.
        # Validate the destination before opening any sensitive drawing.
        destination = private_output_destination(args.output_json)
        result = audit_insert_solid(
            args.original_dwg, args.diagnostic_dxf,
            args.dwg_sha256, args.dxf_sha256,
        )
        # Exclusive 0600 creation in a private 0700 folder; on Windows this
        # intentionally vetoes output until actual DACL checks are provided.
        write_private_report(destination, result)
    except Exception as exc:
        # A decoder exception may contain private paths, IDs or payload data.
        print("BLOCKED_READ_ONLY_AUDIT", type(exc).__name__)
        return 2
    print(
        result["status"],
        "renamed inserts:", result["renamed_insert_count"],
        "block lines:", result["block_definition_line_members_checked"],
        "SOLID status counts:", result["solid_selected_3d_status_counts"],
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())