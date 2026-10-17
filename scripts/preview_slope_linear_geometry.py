"""Read a documented synthetic/user-supplied slope geometry and preview exact m3.

This is NOT a BOQ commitment, a structural design check, or a takeoff from a drawing.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from core.takeoff.slope_linear_geometry import calculate_linear_slope


def main(argv=None):
    parser = argparse.ArgumentParser(description="Preview reviewed linear-rectangle slope geometry; no BOQ or pricing")
    parser.add_argument("--input", required=True, type=Path, help="Explicit JSON geometry")
    parser.add_argument("--output", type=Path, help="New JSON file; existing files are never overwritten")
    args = parser.parse_args(argv)
    data = json.loads(args.input.read_text(encoding="utf-8"))
    result = calculate_linear_slope(data)
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as dest:
            dest.write(payload + "\n")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
