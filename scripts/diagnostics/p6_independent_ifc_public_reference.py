"""Bounded probe of original independently published IFC4 architectural / HVAC models.

The input is NOT a client's building or an acceptance-certified dataset.
Source: RWTH-E3D/DigitalHub MIT, commit 36565d529b4dadeca625de2b793d7e16700171e9.
No raw IFC file, model author, path, shape coordinates, QTO or names are
ever uploaded. Accepted output contains only safe aggregate counts and hashes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import urllib.request

REV = "36565d529b4dadeca625de2b793d7e16700171e9"
OWNER = "RWTH-E3D"
REPO = "DigitalHub"
MODELS = {
    "architecture": {
        "path": "Version_2/DigitalHub_FM-ARC_v2.ifc",
        "git_blob_sha1": "c3951b5061cdabecdeaf7eaa0f957175221200f5",
        "size": 9022255,
    },
    "ventilation": {
        "path": "Version_2/DigitalHub_FM-LFT_v2.ifc",
        "git_blob_sha1": "2d8e2428ebfeffa7c555bd463fef6afe6671f41f",
        "size": 12737833,
    },
}
MAX_BYTES = 30 * 1024 * 1024
CHILD_LIMIT_S = 240
EXPECTED_SCHEMA = "IFC4"


def save_json(path: Path, data: dict) -> None:
    temp = path.with_suffix(".pending")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def authenticated_download(name: str, destination: Path) -> dict:
    spec = MODELS[name]
    url = ("https://raw.githubusercontent.com/" + OWNER + "/" + REPO +
           "/" + REV + "/" + spec["path"])
    req = urllib.request.Request(url, headers={
        "User-Agent": "StructuralPro-independent-IFC4-acceptance/1.0",
        "Accept": "application/octet-stream",
    })
    h256 = hashlib.sha256()
    sha1 = hashlib.sha1()
    sha1.update(("blob " + str(spec["size"]) + "\0").encode("ascii"))
    total = 0
    with urllib.request.urlopen(req, timeout=75) as response, destination.open("wb") as output:
        if response.status != 200:
            raise ValueError("SOURCE_HTTP_NOT_OK")
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            if total > MAX_BYTES or total > spec["size"]:
                raise ValueError("SOURCE_SIZE_EXCEEDS_PINNED_EXPECTATION")
            h256.update(block)
            sha1.update(block)
            output.write(block)
    if total != spec["size"] or sha1.hexdigest() != spec["git_blob_sha1"]:
        raise ValueError("SOURCE_GIT_BLOB_SHA1_OR_SIZE_MISMATCH")
    return {
        "source_commit": REV,
        "source_public_repository": OWNER + "/" + REPO,
        "source_path": spec["path"],
        "source_license": "MIT (publisher repository LICENSE)",
        "bytes": total,
        "source_git_blob_sha1_verified": True,
        "source_sha256": h256.hexdigest(),
    }


def child_analyze(source: Path, result: Path, expected_sha256: str) -> None:
    from core.bim.ifc import DeepIFCAdapter
    from core.drawings.source_mesh3d import VerifiedScene3D
    import ifcopenshell

    stamp = time.monotonic()
    state = {"result": "ANALYZING", "geometry": "NOT_VERIFIED",
             "quantities_authorized": False}
    try:
        model = ifcopenshell.open(str(source))
        state["source_schema"] = str(model.schema)
        state["ifc_element_count"] = len(model.by_type("IfcElement"))
        state["ifc_space_count"] = len(model.by_type("IfcSpace"))
        state["ifc_with_3d_representation"] = sum(
            bool(getattr(e, "Representation", None))
            for e in model.by_type("IfcElement")
        )
        if state["source_schema"] != EXPECTED_SCHEMA:
            raise ValueError("SOURCE_SCHEMA_NOT_SUPPORTED_BY_THIS_PROBE")
        contract = DeepIFCAdapter().read_display_contract(
            source, revision="RWTH-PUBLIC-" + REV[:12],
            max_triangles=40_000, batch_size=32
        )
        scene = VerifiedScene3D(contract, max_triangles=40_000)
        count = sum(len(m.faces) for m in scene.meshes)
        state.update({
            "geometry": "ACCEPTED_WITHIN_40000_TRIANGLES",
            "source_sha256_verified": scene.source_sha256 == expected_sha256,
            "scene_count": len(scene.meshes),
            "scene_type_count": len(set(x.ifc_type for x in scene.meshes)),
            "type_counts": dict(sorted(Counter(m.ifc_type for m in scene.meshes).items())),
            "storey_count": len(scene.storeys),
            "triangles": count,
            "omitted_count": len(scene.omitted_ids),
            "quantities_authorized": scene.quantity_authority,
        })
        if not state["source_sha256_verified"] or not scene.meshes or count > 40_000:
            raise ValueError("SOURCE_OR_GEOMETRY_INVARIANTS_FAILED")
        if scene.quantity_authority is not False:
            raise ValueError("UNAUTHORIZED_QUANTITY_AUTHORITY")
        if scene.omitted_ids:
            raise ValueError("SOME_SOURCE_MEMBERS_NOT_RENDERABLE")
        # Independently force the rendering and picker paths without saving.
        faces = scene.visible_faces(1100, 750)
        state["projected_face_count"] = len(faces)
        if not faces:
            raise ValueError("NO_PROJECTED_IFC_FACES")
        state["result"] = "PASS_SOURCE_BACKED_READONLY"
    except Exception as exc:
        state["result"] = "BLOCKED_OR_FAILED"
        state["error_type"] = type(exc).__name__
        message = str(exc)
        if "ظرفیت" in message or "triangle" in message.lower():
            state["error_category"] = "CAPACITY_40000_TRIANGLES"
        elif "unit" in message.lower() or "واحد" in message:
            state["error_category"] = "SOURCE_UNIT_CONTRACT"
        elif "Placement" in message or "مبدأ" in message:
            state["error_category"] = "SOURCE_PLACEMENT_CONTRACT"
        elif "پشتیبانی" in message or "SOURCE_SCHEMA" in message:
            state["error_category"] = "UNSUPPORTED_SOURCE_FORMAT"
        elif "هندسه" in message:
            state["error_category"] = "SOURCE_GEOMETRY_CONTRACT"
        else:
            state["error_category"] = "OTHER_VALIDATION_OR_NATIVE"
        # Never write free-form exceptions: they might contain private IFC
        # content or source file paths. Raw subprocess output is ephemeral.
    finally:
        state["elapsed_seconds"] = round(time.monotonic() - stamp, 2)
        save_json(result, state)


def run_parent(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=False)
    result = {
        "kind": "p6_independent_public_ifc4_reference_v1",
        "source": OWNER + "/" + REPO,
        "pinned_commit": REV,
        "license": "MIT; source model not redistributed",
        "is_user_or_client_real_building": False,
        "is_independent_published_reference_model": True,
        "tested_software_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "python_version": sys.version.split()[0],
        "platform": sys.platform,
        "per_child_timeout_seconds": CHILD_LIMIT_S,
        "release_permission": False,
        "reports": [],
        "status": "RUNNING",
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    save_json(out / "summary.json", result)
    with tempfile.TemporaryDirectory(prefix="p6-public-ifc-", ignore_cleanup_errors=True) as transient:
        temp = Path(transient)
        for name in MODELS:
            row = {"name": name, "status": "DOWNLOAD_STARTED"}
            result["reports"].append(row)
            save_json(out / "summary.json", result)
            original = temp / (name + ".ifc")
            try:
                row.update(authenticated_download(name, original))
                row["status"] = "SOURCE_VERIFIED"
                save_json(out / "summary.json", result)
                child_output = temp / (name + "-analysis.json")
                env = os.environ.copy()
                env["PYTHONPATH"] = "."
                # Do not publish raw traceback that could include source
                # creator names, source paths or IFC entity attributes.
                with (temp / (name + "-private-logs.txt")).open("wb") as log:
                    try:
                        completed = subprocess.run([
                            sys.executable, __file__, "--child",
                            "--file", str(original), "--analysis", str(child_output),
                            "--sha256", row["source_sha256"]
                        ], cwd=Path(__file__).resolve().parents[2],
                            env=env, stdout=log, stderr=subprocess.STDOUT,
                            timeout=CHILD_LIMIT_S, check=False)
                        row["child_exit"] = completed.returncode
                        row["timed_out"] = False
                    except subprocess.TimeoutExpired:
                        row["child_exit"] = 124
                        row["timed_out"] = True
                analyzed = json.loads(child_output.read_text(encoding="utf-8")) if child_output.exists() else None
                row["diagnostic"] = analyzed
                row["status"] = (
                    "ACCEPTED" if analyzed and analyzed.get("result") == "PASS_SOURCE_BACKED_READONLY"
                    and row["child_exit"] == 0 and not row["timed_out"]
                    else "BLOCKED_OR_FAILED"
                )
            except Exception as exc:
                row["status"] = "BLOCKED_OR_FAILED"
                row["error_type"] = type(exc).__name__
                row["error_category"] = "PINNED_SOURCE_DOWNLOAD_OR_VERIFICATION"
            save_json(out / "summary.json", result)
            print(json.dumps({"name": name, "status": row["status"],
                              "diagnostic": (row.get("diagnostic") or {}).get("error_category"),
                              "source_verified": row.get("source_git_blob_sha1_verified", False)},
                             ensure_ascii=False), flush=True)
    result["status"] = ("ACCEPTED_TWO_INDEPENDENT_REFERENCE_DISCIPLINES"
                        if len(result["reports"]) == 2 and
                        all(x["status"] == "ACCEPTED" for x in result["reports"])
                        else "BLOCKED_PARTIAL_EXTERNAL_IFC4_VALIDATION")
    save_json(out / "summary.json", result)
    return 0 if result["status"] == "ACCEPTED_TWO_INDEPENDENT_REFERENCE_DISCIPLINES" else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", type=Path)
    p.add_argument("--child", action="store_true")
    p.add_argument("--file", type=Path)
    p.add_argument("--analysis", type=Path)
    p.add_argument("--sha256")
    a = p.parse_args()
    if a.child:
        child_analyze(a.file, a.analysis, a.sha256)
    else:
        if a.output is None:
            p.error("--output required")
        raise SystemExit(run_parent(a.output))
