"""Independent public AC1018 DWG and DXF *paired source* geometry oracle.

Samples are maintained by NextGIS and were generated with AutoCAD; they are
not construction as-builts and are not the user's private building drawing.
Git commit and Git blob SHA-1s prevent content-swapping or invented fixtures.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha1, sha256
import argparse
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from core.drawings.dwg_takeoff import DWGTakeoffEngine

COMMIT = "ff05d5a89ce123da511ed93c5fe5e6df85e02ab8"
BLOBS = {
    "line_2004.dwg": ("853557c80bbf0d3b2e925a1bb9c19c963ebb0498", 37281),
    "line_2004.dxf": ("38ef254517e3af7b2317f3100758b25e68b98469", 156843),
}


def _download(name: str) -> bytes:
    ident, length = BLOBS[name]
    url = f"https://raw.githubusercontent.com/nextgis/dwg_samples/{COMMIT}/{name}"
    with urlopen(Request(url, headers={"User-Agent": "StructuralPro-AC1018-paired-proof/1.0"}), timeout=35) as response:
        target = urlparse(response.geturl())
        if target.scheme != "https" or target.hostname != "raw.githubusercontent.com":
            raise ValueError("Unapproved public source redirect")
        data = response.read(length + 1)
    if len(data) != length or sha1(b"blob " + str(length).encode() + b"\0" + data).hexdigest() != ident:
        raise ValueError("Public fixture differs from immutable upstream Git blob")
    return data


def _lines(document):
    out = []
    for e in document.entities:
        if e.entity_type == "LINE" and e.data.get("layer_visible") is not False:
            start, end = e.data["start"], e.data["end"]
            if not math.isfinite(e.data.get("length", float("nan"))):
                raise ValueError("Non-finite CAD length")
            analytic = math.dist(start, end)
            if not math.isclose(analytic, e.data["length"], rel_tol=1e-11, abs_tol=1e-9):
                raise ValueError("Endpoint length oracle does not match CAD engine")
            out.append((e.layer, analytic))
    return sorted(out)


def run() -> dict:
    real_dwg = _download("line_2004.dwg")
    independent_dxf = _download("line_2004.dxf")
    if real_dwg[:6] != b"AC1018":
        raise ValueError("Wrong DWG version for uploaded-user-version reproduction")
    with TemporaryDirectory(prefix="p8p2_public_ac1018_") as tmp:
        dwg_path = Path(tmp) / "line_2004.dwg"
        dxf_path = Path(tmp) / "line_2004.dxf"
        dwg_path.write_bytes(real_dwg)
        dxf_path.write_bytes(independent_dxf)
        engine = DWGTakeoffEngine.with_array_support()
        decoded = engine.import_file(dwg_path)
        reference = engine.import_file(dxf_path)
        a, b = _lines(decoded), _lines(reference)
        if not a or len(a) != len(b):
            raise ValueError("DWG line roster disagrees with independently published DXF")
        if decoded.units != reference.units:
            raise ValueError("Independent DWG and DXF have incompatible units")
        for (la, qa), (lb, qb) in zip(a, b):
            if la != lb or not math.isclose(qa, qb, rel_tol=1e-9, abs_tol=1e-8):
                raise ValueError("Line layer/length differs from independent source DXF")
        if decoded.source_sha256 != sha256(real_dwg).hexdigest():
            raise ValueError("Original DWG SHA was not preserved by StructuralPro engine")
        conversion = decoded.conversion
        if conversion.get("provider") != "ezdwg strict Python bridge" or conversion.get("skipped_entities") != 0:
            raise ValueError("The tested path did not use strict conversion with zero skips")
        return {
            "status": "PUBLIC_PAIRED_AC1018_DWG_DXF_LINE_GEOMETRY_ORACLE_PASS",
            "source_repo": "https://github.com/nextgis/dwg_samples",
            "source_commit": COMMIT,
            "dwg_sha256": sha256(real_dwg).hexdigest(),
            "dxf_sha256": sha256(independent_dxf).hexdigest(),
            "dwg_signature": "AC1018",
            "original_file_sampled_in_user_zip": False,
            "units": decoded.units,
            "paired_line_count": len(a),
            "paired_analytic_lengths_m": [round(x[1], 9) for x in a[:10]],
            "source_published_independent_dxf": True,
            "strict_dwg_conversion_skipped": conversion["skipped_entities"],
            "no_automated_site_member_identity": True,
            "no_user_143_metre_rows_approved": True,
            "no_pricing_or_boq_committed": True,
            "executable_built": False,
            "release": "NO_GO"
        }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        answer = run()
    except Exception as exc:
        answer = {"status": "BLOCKED_PAIRED_AC1018_NOT_ACCEPTED",
                  "reason_type": type(exc).__name__, "reason": str(exc)[:400],
                  "user_private_dwg_tested": False, "release": "NO_GO"}
        args.output.write_text(json.dumps(answer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(answer, sort_keys=True))
        raise
    args.output.write_text(json.dumps(answer, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(answer, sort_keys=True))


if __name__ == "__main__":
    main()
