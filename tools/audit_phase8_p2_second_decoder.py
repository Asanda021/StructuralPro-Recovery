"""Example: python tools/audit_phase8_p2_second_decoder.py original.dwg receipt.json"""
from __future__ import annotations
import argparse
from core.drawings.dwg_second_decoder_probe import save_probe_report


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only exact-original-DWG native second reader probe; NO-GO until opaque support verified')
    parser.add_argument('source_dwg')
    parser.add_argument('report_json')
    args = parser.parse_args()
    result = save_probe_report(args.source_dwg, args.report_json)
    print(result['status'], result.get('reason', ''), result.get('source_sha256', ''))
    return 0 if result.get('independent_decoder_executed') else 2


if __name__ == '__main__':
    raise SystemExit(main())