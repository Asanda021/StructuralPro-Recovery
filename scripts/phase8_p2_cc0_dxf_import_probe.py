"""External CC0 DXF takeoff-read gate (real published bytes; no invented BOQ).

The catalog states a NOMINAL 64x32-m plan with millimetre drawing units.
The actual downloaded file must be parsed by StructuralPro's production engine.
This is NOT a real constructed site or approved quantity/financial statement.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, build_opener

from scripts.phase8_p2_real_dwg_source_probe import RestrictedRedirect, approved_url
from core.drawings.dwg_takeoff import DWGTakeoffEngine

CATALOG_URL = "https://www.innerscene.com/tools/library/drawings/school-general-site-plan-1-200-two-building-blocks-0ef5131d"
SOURCE_URL = "https://www.innerscene.com/api/library/school-general-site-plan-1-200-two-building-blocks-0ef5131d/download"
MAX_BYTES = 1024 * 1024
EXPECTED_SHA256 = "420fba86abbe33f49e846915ebb3dc6c1073a48252d3e1d76bd8447ca659a519"


def audit_download() -> dict:
    opener = build_opener(RestrictedRedirect())
    if not approved_url(SOURCE_URL):
        raise ValueError("DXF catalog URL is not approved")
    with opener.open(Request(SOURCE_URL, headers={"User-Agent": "StructuralPro-evidence-audit/1.0"}), timeout=35) as resp:
        if not approved_url(resp.geturl()):
            raise ValueError("Unapproved DXF redirect")
        final_url = resp.geturl()
        contents = resp.read(MAX_BYTES + 1)
    if not 1024 <= len(contents) <= MAX_BYTES:
        raise ValueError("DXF source length outside audited range")
    with TemporaryDirectory(prefix="p8p2_cc0_dxf_") as tmp:
        file = Path(tmp) / "school-site-independent.dxf"
        file.write_bytes(contents)
        original_digest = sha256(contents).hexdigest()
        if original_digest != EXPECTED_SHA256:
            raise ValueError("Published CC0 DXF checksum differs from prior independent Linux and Windows evidence")
        imported = DWGTakeoffEngine().import_file(file)
        if imported.source_sha256 != original_digest:
            raise ValueError("DXF production import did not preserve exact source SHA")
        if imported.format != "DXF" or imported.units != "mm":
            raise ValueError("External DXF version or claimed millimetre units are not preserved")
        if not imported.entities or not imported.layers:
            raise ValueError("Real external DXF has no imported entities/layers")
        independent_lines = []
        for entity in imported.entities:
            if entity.entity_type != "LINE":
                continue
            raw = entity.data
            if not {"start", "end", "length"} <= raw.keys():
                continue
            dx = raw["end"][0] - raw["start"][0]
            dy = raw["end"][1] - raw["start"][1]
            expected = math.hypot(dx, dy)
            if not math.isfinite(expected) or not math.isclose(expected, raw["length"], rel_tol=1e-12, abs_tol=1e-8):
                raise ValueError("Independent LINE length mismatch")
            independent_lines.append({"handle": entity.handle, "length_m": round(expected, 8)})
        if not independent_lines:
            raise ValueError("No dimensionally verifiable 2D LINE entity found")
        # Checksum is learned from the fetched source; not claimed independently pinned.
        return {
            "status": "EXTERNAL_CC0_DXF_SOURCE_ENGINE_READ_AND_LINE_ORACLE_PASS",
            "catalog_url": CATALOG_URL,
            "source_url": SOURCE_URL,
            "response_url": final_url,
            "source_bytes": len(contents),
            "source_sha256": original_digest,
            "source_sha256_pinned_in_test": True,
            "source_sha256_pinned_independently": False,
            "dxf_version": imported.dxf_version,
            "units": imported.units,
            "numeric_length_unit_after_normalization": "m",
            "entity_count": len(imported.entities),
            "layer_count": len(imported.layers),
            "line_oracle_count": len(independent_lines),
            "line_oracle_examples": independent_lines[:5],
            "catalog_nominal_site_dimensions_m": [64, 32],
            "site_boundary_geometry_independently_approved": False,
            "real_construction_project": False,
            "dwg_bridge_built": False,
            "boq_or_estimate_approved": False,
            "release": "NO_GO"
        }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = audit_download()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
