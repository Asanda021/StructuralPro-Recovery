"""Run read-only source-bound opaque-class DXF consistency audit locally."""
import argparse
import json
from pathlib import Path
from core.drawings.dwg_opaque_conversion_diff import audit_opaque_conversion_loss


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dwg', type=Path, required=True)
    p.add_argument('--dxf', type=Path, required=True)
    p.add_argument('--ledger', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    evidence = audit_opaque_conversion_loss(args.dwg, args.dxf, json.loads(args.ledger.read_text(encoding='utf8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n',encoding='utf8')
    print(f"{evidence['verdict']} | opaque missing: {evidence['dxf_missing_opaque_count']}/{evidence['source_opaque_count']} | dangling root refs: {evidence['dangling_named_dictionary_references_count']}")

if __name__ == '__main__':
    main()