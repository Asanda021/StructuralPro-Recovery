"""Independent third-party DWG import through a prebuilt Python wheel.

No EXE/installer build. No user files are uploaded. This only proves one
public AC1015 binary. strict=True refuses lost entities/attributes.
"""
from __future__ import annotations
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, build_opener

from core.drawings.dwg_takeoff import DWGTakeoffEngine
from scripts.phase8_p2_real_dwg_source_probe import (
    RestrictedRedirect, approved_url, STUDIO_SOURCE, SOURCES,
)

PIN = SOURCES["studio_cc0"]["expected_sha256"]
MAX_BYTES = 1_000_000


def run() -> dict:
    import ezdwg
    if not approved_url(STUDIO_SOURCE):
        raise ValueError("Source not approved")
    with build_opener(RestrictedRedirect()).open(
        Request(STUDIO_SOURCE, headers={"User-Agent": "StructuralPro-dwg-alternative-audit/1.0"}),
        timeout=35,
    ) as response:
        if not approved_url(response.geturl()):
            raise ValueError("Source escaped allowlist")
        data = response.read(MAX_BYTES + 1)
    if len(data) < 1024 or len(data) > MAX_BYTES or sha256(data).hexdigest() != PIN:
        raise ValueError("Public source changed or exceeded bounds")
    if data[:6] != b"AC1015":
        raise ValueError("Public DWG signature changed")

    with TemporaryDirectory(prefix="p8p2_ezdwg_") as tmp:
        dwg = Path(tmp) / "public-pinned.dwg"
        dxf = Path(tmp) / "strict-output.dxf"
        dwg.write_bytes(data)
        source = ezdwg.read(str(dwg))
        if source.version != "AC1015":
            raise ValueError("DWG decoder did not preserve source version")
        entities = list(source.modelspace().iter_entities())
        if not entities:
            raise ValueError("Decoder returned no model-space entities")
        type_counts = dict(sorted(Counter(str(e.dxftype) for e in entities).items()))
        result = ezdwg.to_dxf(str(dwg), str(dxf), strict=True)
        if result.skipped_entities or result.written_entities != result.total_entities:
            raise ValueError("Strict DWG to DXF conversion lost any entity")
        if not dxf.is_file() or not dxf.stat().st_size:
            raise ValueError("Strict DXF output was empty")
        drawing = DWGTakeoffEngine.with_array_support().import_file(dxf)
        if len(drawing.entities) == 0 or drawing.source_sha256 != sha256(dxf.read_bytes()).hexdigest():
            raise ValueError("StructuralPro CAD engine could not read strict exported DXF")
        production = DWGTakeoffEngine.with_array_support().import_file(dwg)
        if not production.format.startswith("DWG") or production.source_sha256 != PIN:
            raise ValueError("Product DWG importer failed to preserve original binary source identity")
        if production.conversion.get("provider") != "ezdwg strict Python bridge":
            raise ValueError("Product did not invoke the intended strict prebuilt Python reader")
        if production.conversion.get("skipped_entities") != 0:
            raise ValueError("Product accepted skipped DWG entities")
        if production.conversion.get("total_entities") != result.total_entities:
            raise ValueError("Product DWG import entity coverage differs from strict reference")
        if sha256(dwg.read_bytes()).hexdigest() != PIN:
            raise ValueError("Source changed while decoded")
        return {
            "status": "PUBLIC_CC0_AC1015_EZDWG_STRICT_DWG_TO_DXF_ENGINE_READ_PASS",
            "public_source": STUDIO_SOURCE,
            "source_sha256": PIN,
            "source_dwg_signature": "AC1015",
            "original_modelspace_entities": len(entities),
            "original_types": type_counts,
            "strict_conversion_total": result.total_entities,
            "strict_conversion_written": result.written_entities,
            "strict_conversion_skipped": result.skipped_entities,
            "strict_output_sha256": sha256(dxf.read_bytes()).hexdigest(),
            "production_engine_entities": len(drawing.entities),
            "product_dwg_import_entities": len(production.entities),
            "product_native_automatic_optional_fallback": True,
            "product_import_source_sha256": production.source_sha256,
            "product_decoder_version": production.conversion.get("decoder_version"),
            "production_engine_layers": len(drawing.layers),
            "production_engine_document_unit": drawing.units,
            "uploaded_user_dwg_tested": False,
            "quantity_oracle_independently_certified": False,
            "legacy_metre_rows_approved": 0,
            "automatic_boq_commit": False,
            "owner_executable_build_performed": False,
            "release": "NO_GO",
        }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    try:
        result = run()
    except Exception as exc:
        result = {
            "status": "BLOCKED_PUBLIC_DWG_STRICT_CONVERSION_NOT_ACCEPTED",
            "reason_type": type(exc).__name__, "reason": str(exc)[:500],
            "source_dwg_signature": "AC1015", "user_dwg_tested": False,
            "legacy_metre_rows_approved": 0, "release": "NO_GO",
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        raise
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
