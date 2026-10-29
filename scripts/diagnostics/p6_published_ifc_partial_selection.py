"""Pinned independent IFC4 bounded-selection acceptance, never full-model UAT.

An explicit one-member subset avoids the fixed 40k-triangle UI limit without
discarding any IFC identity from the checked ledger. Original author data,
GUIDs, element names, coordinates, QTO and raw IFC never leave the runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from scripts.diagnostics.p6_independent_ifc_public_reference import (
    MODELS, REV, authenticated_download, save_json,
)

TARGET_TYPES = {
    "architecture": ("IfcWall", "IfcSlab", "IfcBeam"),
    "ventilation": ("IfcDuctSegment", "IfcDuctFitting", "IfcFlowTerminal"),
}
EXPECTED = {
    "architecture": (957, 949, 8),
    "ventilation": (1310, 1310, 0),
}
CHILD_TIMEOUT = 240


def child(source: Path, summary_path: Path, expected_hash: str, name: str) -> int:
    import ifcopenshell
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D

    state = {
        "model": name, "status": "NOT_ACCEPTED",
        "source_digest_verified": False,
        "quantity_authority": False,
        "limited_display_not_full_model_acceptance": True,
    }
    start = time.monotonic()
    try:
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != expected_hash:
            raise ValueError("SOURCE_SHA_MISMATCH")
        state["source_digest_verified"] = True
        model = ifcopenshell.open(str(source))
        all_members = model.by_type("IfcElement")
        represented = [m for m in all_members
                       if getattr(m, "Representation", None) is not None]
        nonrepresented = len(all_members) - len(represented)
        if (len(all_members), len(represented), nonrepresented) != EXPECTED[name]:
            raise ValueError("MODEL_SOURCE_ROSTER_CHANGED")
        if model.schema != "IFC4":
            raise ValueError("SOURCE_SCHEMA_CHANGED")
        # A real source-derived, reproducible selection. No fabricated mesh.
        order = {typ: i for i, typ in enumerate(TARGET_TYPES[name])}
        represented.sort(key=lambda m: (order.get(m.is_a(), len(order)), m.GlobalId))
        first = represented[0]
        requested = [first.GlobalId]
        contract = DeepIFCAdapter().read_display_contract(
            source, revision="RWTH-LIMITED-" + REV[:12],
            selected_global_ids=requested, max_triangles=40_000,
        )
        cat = contract["display_catalog"]
        scene = VerifiedScene3D(contract)
        scene.validate_source()
        visible = scene.visible_faces(1000, 720)
        expected_counts = {
            "displayed": 1,
            "not_loaded": len(represented) - 1,
            "without_geometry": nonrepresented,
        }
        if (cat["counts"] != expected_counts or
            cat["source_member_count"] != len(all_members) or
            len(cat["members"]) != len(all_members) or
            len(scene.meshes) != 1 or scene.meshes[0].global_id != first.GlobalId or
            not visible or len(visible) > 40_000 or
            scene.quantity_authority is not False or
            cat["complete_model_displayed"] is not False or
            contract["quantity_authority"] is not False):
            raise ValueError("BOUNDED_ROSTER_OR_VIEWER_INVARIANT_FAILED")
        state.update({
            "status": "PASS_BOUNDED_SOURCE_VIEW_ONLY",
            "source_members": len(all_members),
            "represented_members": len(represented),
            "counts": expected_counts,
            "selected_class": first.is_a(),
            "selected_mesh_triangles": len(scene.meshes[0].faces),
            "projected_faces": len(visible),
            "mesh_limit": 40_000,
            "map_conversion_present": contract["map_conversion_present"],
            "map_conversion_supported": contract["map_conversion_supported"],
            "source_digest_verified": scene.source_sha256 == expected_hash,
        })
    except Exception as exc:
        # Only the exception class; no GUIDs, paths, IFC names or raw traces.
        state["status"] = "BLOCKED"
        state["exception_class"] = type(exc).__name__
    finally:
        state["elapsed_seconds"] = round(time.monotonic() - start, 3)
        save_json(summary_path, state)
    return 0 if state["status"] == "PASS_BOUNDED_SOURCE_VIEW_ONLY" else 1


def parent(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=False)
    overall = {
        "kind": "p6_g2_published_ifc4_bounded_source_selection_v1",
        "fixed_source_commit": REV,
        "source_repository": "RWTH-E3D/DigitalHub",
        "software_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "platform": sys.platform,
        "is_customer_building": False,
        "quantity_authority": False,
        "release_ready": False,
        "results": [],
        "status": "RUNNING",
    }
    save_json(output_dir / "summary.json", overall)
    with tempfile.TemporaryDirectory(prefix="p6-limited-published-", ignore_cleanup_errors=True) as td:
        temp = Path(td)
        for name in ("architecture", "ventilation"):
            row = {"model": name, "status": "NOT_EXECUTED"}
            overall["results"].append(row)
            source = temp / (name + ".ifc")
            try:
                provenance = authenticated_download(name, source)
                child_output = temp / (name + "-result.json")
                with (temp / (name + "-private.log")).open("wb") as private:
                    try:
                        p = subprocess.run(
                            [sys.executable, str(Path(__file__).resolve()),
                             "--child", "--file", str(source), "--json", str(child_output),
                             "--sha256", provenance["source_sha256"], "--model", name],
                            stdout=private, stderr=subprocess.STDOUT,
                            cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, "PYTHONPATH": "."},
                            check=False, timeout=CHILD_TIMEOUT,
                        )
                        row["exit_code"] = p.returncode
                        row["timed_out"] = False
                    except subprocess.TimeoutExpired:
                        row["exit_code"] = 124
                        row["timed_out"] = True
                if child_output.exists():
                    row.update(json.loads(child_output.read_text(encoding="utf-8")))
                row["verified_upstream_git_blob"] = provenance["source_git_blob_sha1_verified"]
                row["source_sha256"] = provenance["source_sha256"]
            except Exception as exc:
                row.update({"status": "BLOCKED", "error_class": type(exc).__name__})
            save_json(output_dir / "summary.json", overall)
            print(json.dumps({
                "model": name, "status": row["status"],
                "count": row.get("counts"), "exit": row.get("exit_code")
            }), flush=True)
    overall["status"] = (
        "PASS_TWO_LIMITED_INDEPENDENT_SOURCE_SUBSETS_NOT_FULL_3D"
        if len(overall["results"]) == 2 and all(
            r.get("status") == "PASS_BOUNDED_SOURCE_VIEW_ONLY"
            and r.get("exit_code") == 0 and not r.get("timed_out", True)
            and r.get("verified_upstream_git_blob") is True
            for r in overall["results"]
        ) else "BLOCKED_LIMITED_INDEPENDENT_SOURCE_SUBSETS"
    )
    save_json(output_dir / "summary.json", overall)
    return 0 if overall["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--sha256", type=str)
    parser.add_argument("--model", choices=["architecture", "ventilation"])
    opts = parser.parse_args()
    if opts.child:
        if not opts.file or not opts.json or not opts.sha256 or not opts.model:
            parser.error("missing child source arguments")
        raise SystemExit(child(opts.file, opts.json, opts.sha256, opts.model))
    if not opts.output:
        parser.error("missing --output")
    raise SystemExit(parent(opts.output))
