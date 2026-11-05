"""Private-only AC1018 block reference audit, no source IDs in stdout.

Run as: python -m tools.audit_phase8_p2_original_block_source ORIGINAL.dwg
        /safe/private/report.json --private-config /safe/private/input.json
Config keys: handles, expected_original_sha256.
Windows remains blocked unless its private DACL is verified.
"""
from __future__ import annotations

import argparse
from core.drawings.dwg_original_block_source_oracle import (
    audit_original_dwg_block_references,
)
from tools.audit_phase8_p2_opaque_source_bytes import (
    read_private_config, private_output_destination, write_private_report,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_dwg")
    parser.add_argument("output_json")
    parser.add_argument("--private-config", required=True)
    args = parser.parse_args()
    try:
        destination = private_output_destination(args.output_json)
        selected, sha = read_private_config(args.private_config)
        receipt = audit_original_dwg_block_references(
            args.original_dwg, selected, expected_original_sha256=sha
        )
        write_private_report(destination, receipt)
    except Exception as exc:
        # Diagnostic type only: private locations, IDs and proprietary bytes
        # are never printed, even when the underlying decoder leaks them.
        print("BLOCKED_NO_PRIVATE_SOURCE_APPROVAL", type(exc).__name__)
        return 2
    print(
        receipt["status"],
        "disputed LINE owners:", receipt["disputed_lines_source_owner_verified_count"],
        "typed INSERT refs:", receipt["source_insert_typed_references_covered"],
        "typed DIMENSION refs:", receipt["source_dimension_typed_references_covered"],
        "financial approvals: 0",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
