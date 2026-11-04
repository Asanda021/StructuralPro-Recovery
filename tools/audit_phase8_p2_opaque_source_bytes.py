"""Read-only original-DWG opaque record receipt, never a DXF repair command."""
import argparse, json
from pathlib import Path
from core.drawings.dwg_opaque_source_receipt import audit_original_opaque_records

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_dwg');p.add_argument('converted_dxf');p.add_argument('output_json')
    p.add_argument('--handles',required=True,help='Comma-separated source handles, kept OUT of public GitHub')
    p.add_argument('--expected-original-sha256',required=True)
    a=p.parse_args()
    try:
        result=audit_original_opaque_records(a.original_dwg,a.converted_dxf,
                     a.handles.split(','),expected_original_sha256=a.expected_original_sha256)
    except Exception as exc:
        print('BLOCKED_NO_SAFE_SOURCE_RECEIPT:',type(exc).__name__,str(exc)[:160]);return 2
    dest=Path(a.output_json);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['status'],'original records',result['source_record_count'],
          'dangling DXF refs',result['converted_dxf_dangling_ref_count'])
    return 0
if __name__=='__main__':raise SystemExit(main())