#!/usr/bin/env python3
"""Generate an immutable independent instructional preview, not a BOQ."""
import argparse
import json
from pathlib import Path
from core.takeoff.stair_specialist import preview

def main():
    p=argparse.ArgumentParser()
    p.add_argument('input',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    data=json.loads(args.input.read_text(encoding='utf-8'))
    result=preview(data)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f"independent stair preview: {len(result['rows'])} rows, SHA256={result['input_sha256']}")

if __name__=='__main__':main()
