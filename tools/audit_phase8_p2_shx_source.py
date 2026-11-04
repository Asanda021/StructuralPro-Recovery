"""Read-only audit of a PRIVATE SHX raw-text ledger. No CAD changes or approval."""
import argparse
from core.drawings.dwg_shx_source_audit import audit_original_shx_ledger
from tools.audit_phase8_p2_opaque_source_bytes import write_private_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dwg")
    parser.add_argument("converted_dxf")
    parser.add_argument("private_ledger_csv")
    parser.add_argument("private_json_output", help="Absolute 0600 private report outside Git")
    parser.add_argument("--expected-count", type=int)
    args = parser.parse_args()
    try:
        result = audit_original_shx_ledger(
            args.source_dwg, args.converted_dxf, args.private_ledger_csv,
            expected_record_count=args.expected_count,
        )
        write_private_report(args.private_json_output, result)
    except Exception as exc:
        print("BLOCKED_SHX_SOURCE_AUDIT:", type(exc).__name__)
        return 2
    print("PARTIAL_NO_GO; source-bound legacy SHX candidates:",
          result["private_shx_candidate_count"],
          "financial quantities approved:", result["financial_quantities_approved"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())