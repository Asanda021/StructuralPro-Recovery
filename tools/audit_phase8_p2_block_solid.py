"""Run a read-only SHA-bound source-vs-DXF BLOCK and SOLID audit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from core.drawings.dwg_insert_solid_contract import audit_insert_solid


def main() -> int:
    parser = argparse.ArgumentParser(description="Source DWG v DXF BLOCK/SOLID audit (never payable approval)")
    parser.add_argument("original_dwg")
    parser.add_argument("diagnostic_dxf")
    parser.add_argument("output_json")
    parser.add_argument("--dwg-sha256", required=True)
    parser.add_argument("--dxf-sha256", required=True)
    args = parser.parse_args()
    try:
        result = audit_insert_solid(args.original_dwg,args.diagnostic_dxf,args.dwg_sha256,args.dxf_sha256)
    except Exception as exc:
        print("BLOCKED_READ_ONLY_AUDIT",type(exc).__name__,str(exc)[:160])
        return 2
    output = Path(args.output_json)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['status'],'renamed inserts:',result['renamed_insert_count'],'block lines:',result['block_definition_line_members_checked'],'SOLIDs:',result['solid_selected_3d_status_counts'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())