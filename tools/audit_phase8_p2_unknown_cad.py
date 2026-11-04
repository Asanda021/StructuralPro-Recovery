"""Offline CLI for explicitly read-only historic LibreDWG proxy audit.

Usage: python tools/audit_phase8_p2_unknown_cad.py SOURCE.dwg SNAPSHOT.json RECEIPT.json OUT.json
No bytes from the private input are committed or uploaded automatically.
"""
import argparse
import json
from pathlib import Path
from core.drawings.dwg_unknown_object_audit import audit_unknown_objects


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dwg', type=Path)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('receipt', type=Path)
    parser.add_argument('out', type=Path)
    args = parser.parse_args()
    if any(args.out.resolve() == p.resolve() for p in (args.dwg,args.snapshot,args.receipt)):
        parser.error('Output cannot replace input evidence')
    snapshot = json.loads(args.snapshot.read_text(encoding='utf-8'))
    receipt = json.loads(args.receipt.read_text(encoding='utf-8'))
    result = audit_unknown_objects(args.dwg, snapshot, receipt)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n',encoding='utf-8')
    print(f"{result['verdict']}: {result['opaque_object_count']} opaque objects; ",
          f"previous C-API status {result['decoder_status_from_prior_c_api_receipt']}; ",
          'ZERO payable quantities authorized')

if __name__ == '__main__':
    main()