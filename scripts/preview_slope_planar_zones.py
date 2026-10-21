"""Preview exact, non-payable planar-zone geometry; no BOQ or file mutation."""
from __future__ import annotations

import argparse
import json
from hashlib import sha256
from pathlib import Path

from core.takeoff.slope_planar_zones import calculate_planar_slope_zones


def main(argv=None):
    parser=argparse.ArgumentParser(description="Documented planar slope geometry (no BOQ/pricing)")
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,default=None)
    parser.add_argument("--source-file",type=Path,default=None,
                        help="Optional local source evidence file; verify bytes against declared SHA-256")
    args=parser.parse_args(argv)
    data=json.loads(args.input.read_text(encoding="utf-8"),parse_float=str)
    result=calculate_planar_slope_zones(data)
    if args.source_file is not None:
        actual=sha256(args.source_file.read_bytes()).hexdigest()
        if actual != result["source_sha256_claim"]:
            raise ValueError("هش فایل مدرک با SHA-256 اظهارشده مطابقت ندارد")
        result["source_sha256_verified"]=True  # Verifies bytes, not authorship or engineering acceptance.
    out=json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n"
    if args.output is None:
        print(out,end="")
    else:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        with args.output.open("x",encoding="utf-8") as stream:stream.write(out)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
