"""Explicit offline original-DWG vs converted-DXF read-only crosscheck."""
import argparse, json
from pathlib import Path
from core.drawings.dwg_native_roster_crosscheck import audit_native_to_dxf


def main():
    p=argparse.ArgumentParser(description='Compare original DWG via pinned independent reader against converted DXF, never approve finance')
    p.add_argument('original_dwg')
    p.add_argument('converted_dxf')
    p.add_argument('output_json')
    p.add_argument('--expected-dwg-sha256',required=True)
    p.add_argument('--expected-dxf-sha256',required=True)
    a=p.parse_args()
    result=audit_native_to_dxf(a.original_dwg,a.converted_dxf,expected_dwg_sha256=a.expected_dwg_sha256,expected_dxf_sha256=a.expected_dxf_sha256)
    Path(a.output_json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(result['status'], 'native=',result['native_modelspace_iterator_count'],'DXF=',result['dxf_modelspace_iterator_count'],'missing=',len(result['missing_native_entries']))
    return 2 if result['status']!='ACCEPTED' else 0

if __name__=='__main__':
    raise SystemExit(main())