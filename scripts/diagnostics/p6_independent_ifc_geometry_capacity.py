"""Phase 6 G2: measure pinned independent IFC4 geometry, not render or take off.

Measures ALL representable IfcElements without retaining display meshes, under
a separate subprocess memory/time budget. Stops visibly on any bound. All
measurements are aggregate; raw IFC, author data, ids, vertex coordinates,
QTO, names, paths, tracebacks and debugger output remain runner-local.
This MUST NOT raise product's 40k triangle safety gate or imply acceptance.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

import psutil
from scripts.diagnostics.p6_independent_ifc_public_reference import (
    MODELS, REV, authenticated_download, save_json,
)

MAX_RSS_BYTES = 1_400_000_000
MAX_TRIANGLES_MEASURED = 4_000_000
CHILD_TIMEOUT_SECONDS = 330
POLL_SECONDS = 0.05
DEFAULT_REVISION = "RWTH-PUBLIC-" + REV[:12]


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def percentile(values, pct):
    if not values:
        return 0
    ordered = sorted(values)
    # Nearest-rank empirical percentile, no interpolation/invention.
    index = max(0, (pct * len(ordered) + 99) // 100 - 1)
    return ordered[index]


def analyze_file(source: Path, expected_sha: str, output: Path) -> dict:
    import ifcopenshell
    import ifcopenshell.geom

    began = time.monotonic()
    state = {
        "kind": "p6_g2_geometry_capacity_measurement_v1",
        "source_sha256_verified": False,
        "revision": DEFAULT_REVISION,
        "schema": None,
        "source_ifc_elements": 0,
        "source_represented_elements": 0,
        "processed_elements": 0,
        "failed_to_tessellate_elements": 0,
        "valid_mesh_elements": 0,
        "triangle_total_measured": 0,
        "triangle_total_is_complete": False,
        "maximum_member_triangles": 0,
        "maximum_member_vertices": 0,
        "map_conversion_present": False,
        "quantity_authority": False,
        "product_triangle_limit_unchanged": 40000,
        "status": "STARTED_NOT_ACCEPTED",
    }
    save_json(output, state)
    if digest_file(source) != expected_sha:
        state["status"] = "SOURCE_HASH_MISMATCH"
        save_json(output, state)
        return state
    state["source_sha256_verified"] = True
    model = ifcopenshell.open(str(source))
    state["schema"] = str(model.schema)
    if state["schema"] != "IFC4":
        state["status"] = "UNSUPPORTED_SCHEMA"
        save_json(output, state)
        return state
    state["map_conversion_present"] = bool(model.by_type("IfcMapConversion"))
    elements = model.by_type("IfcElement")
    state["source_ifc_elements"] = len(elements)
    candidates = [e for e in elements if getattr(e, "Representation", None)]
    state["source_represented_elements"] = len(candidates)
    state["representation_absent"] = len(elements) - len(candidates)
    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)
    failed_types = Counter()
    triangle_counts = []
    type_triangles = Counter()
    start_rss = psutil.Process().memory_info().rss
    state["child_rss_at_start_bytes"] = start_rss
    state["status"] = "MEASURING"
    save_json(output, state)
    for index, element in enumerate(candidates, 1):
        kind = element.is_a()
        try:
            shape = ifcopenshell.geom.create_shape(settings, element)
        except RuntimeError:
            failed_types[kind] += 1
            state["failed_to_tessellate_elements"] += 1
            state["processed_elements"] = index
        else:
            geom = shape.geometry
            # Count faces/vertices without copying or holding any mesh arrays.
            face_len = len(geom.faces)
            vertex_len = len(geom.verts)
            if (face_len == 0 or vertex_len == 0 or
                    face_len % 3 or vertex_len % 3):
                state["status"] = "INVALID_MESH_COUNTS"
                state["processed_elements"] = index
                save_json(output, state)
                return state
            triangle_count = face_len // 3
            vertex_count = vertex_len // 3
            triangle_counts.append(triangle_count)
            type_triangles[kind] += triangle_count
            state["valid_mesh_elements"] += 1
            state["triangle_total_measured"] += triangle_count
            state["maximum_member_triangles"] = max(
                state["maximum_member_triangles"], triangle_count
            )
            state["maximum_member_vertices"] = max(
                state["maximum_member_vertices"], vertex_count
            )
            state["processed_elements"] = index
            del geom, shape
        if index % 32 == 0 or index == len(candidates):
            state["elapsed_seconds"] = round(time.monotonic() - began, 2)
            save_json(output, state)
        if state["triangle_total_measured"] > MAX_TRIANGLES_MEASURED:
            state["status"] = "MEASUREMENT_TRIANGLE_BUDGET_EXCEEDED"
            save_json(output, state)
            return state
        if index % 64 == 0:
            gc.collect()
    state.update({
        "mesh_member_triangles_p50": percentile(triangle_counts, 50),
        "mesh_member_triangles_p90": percentile(triangle_counts, 90),
        "mesh_member_triangles_p99": percentile(triangle_counts, 99),
        "triangle_totals_by_type": dict(sorted(type_triangles.items())),
        "failed_mesh_types": dict(sorted(failed_types.items())),
        "triangle_total_is_complete": (
            state["processed_elements"] == len(candidates) and
            state["failed_to_tessellate_elements"] == 0 and
            state["representation_absent"] == 0
        ),
        "all_represented_elements_measured": (
            state["processed_elements"] == len(candidates) and
            state["failed_to_tessellate_elements"] == 0
        ),
        "elapsed_seconds": round(time.monotonic() - began, 2),
    })
    # "complete" requires no representable failures, and explicit reporting of
    # members with no representation. No hidden omissions.
    state["status"] = (
        "COMPLETE_ALL_MEMBERS_MEASURED"
        if state["triangle_total_is_complete"]
        else "INCOMPLETE_EXPLICIT_MISSING_GEOMETRY"
    )
    save_json(output, state)
    return state


def run_child(path: Path, expected_sha: str, output: Path) -> int:
    try:
        row = analyze_file(path, expected_sha, output)
    except Exception as exc:
        # The category alone is safe; no raw errors, paths, or model metadata.
        if not output.is_file():
            row = {"status": "UNRECOVERABLE_MEASUREMENT_FAILURE"}
        else:
            row = json.loads(output.read_text(encoding="utf-8"))
        row["status"] = "MEASUREMENT_EXCEPTION"
        row["exception_class"] = type(exc).__name__
        save_json(output, row)
        return 2
    return 0 if row["status"] == "COMPLETE_ALL_MEMBERS_MEASURED" else 1


def controlled_child(source: Path, expected_sha: str, output: Path,
                     private_log: Path) -> dict:
    start = time.monotonic()
    peak_rss = 0
    observed_samples = 0
    exit_reason = "CHILD_EXIT"
    with private_log.open("wb") as log:
        child = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "--child",
             "--source", str(source), "--expected-sha", expected_sha,
             "--child-output", str(output)],
            cwd=str(Path(__file__).resolve().parents[2]),
            env={**os.environ, "PYTHONPATH": ".", "PYTHONFAULTHANDLER": "1"},
            stdout=log, stderr=subprocess.STDOUT,
        )
        target = psutil.Process(child.pid)
        while child.poll() is None:
            try:
                rss = target.memory_info().rss
                peak_rss = max(peak_rss, rss)
                observed_samples += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if peak_rss > MAX_RSS_BYTES:
                exit_reason = "RSS_SAFETY_LIMIT"
                child.kill()
                break
            if time.monotonic() - start > CHILD_TIMEOUT_SECONDS:
                exit_reason = "TIME_SAFETY_LIMIT"
                child.kill()
                break
            time.sleep(POLL_SECONDS)
        try:
            exit_code = child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            exit_code = child.wait()
            exit_reason = "CHILD_TERMINATION_TIMEOUT"
    # The child writes only aggregate JSON. Incomplete results stay incomplete.
    try:
        state = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {"status": "NO_CHILD_SUMMARY"}
    state.update({
        "child_exit_code": exit_code,
        "exit_reason": exit_reason,
        "observed_peak_child_rss_bytes": peak_rss,
        "sampled_child_rss_points": observed_samples,
        "wall_seconds": round(time.monotonic() - start, 2),
        "rss_sampling_interval_seconds": POLL_SECONDS,
        "rss_limit_bytes": MAX_RSS_BYTES,
        "triangle_measurement_budget": MAX_TRIANGLES_MEASURED,
        "child_timeout_seconds": CHILD_TIMEOUT_SECONDS,
    })
    if exit_reason != "CHILD_EXIT":
        state["status"] = "INCOMPLETE_" + exit_reason
        state["triangle_total_is_complete"] = False
    if exit_code != 0 and state["status"] == "COMPLETE_ALL_MEMBERS_MEASURED":
        state["status"] = "INCOMPLETE_EXIT_CODE"
        state["triangle_total_is_complete"] = False
    return state


def main(output_dir: Path) -> int:
    output_dir.mkdir(parents=True, exist_ok=False)
    result = {
        "kind": "p6_g2_independent_geometry_capacity_measurement_v1",
        "source_repository": "RWTH-E3D/DigitalHub",
        "source_commit": REV,
        "published_source_is_not_a_verified_client_building": True,
        "quantity_authority": False,
        "safety_cap_not_modified": 40000,
        "status": "RUNNING",
        "reports": [],
        "git_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    save_json(output_dir / "summary.json", result)
    with tempfile.TemporaryDirectory(prefix="p6-ifc-capacity-", ignore_cleanup_errors=True) as t:
        private = Path(t)
        for name in ("architecture", "ventilation"):
            current = {"model": name, "status": "SOURCE_DOWNLOAD_PENDING"}
            result["reports"].append(current)
            save_json(output_dir / "summary.json", result)
            source = private / (name + ".ifc")
            try:
                prov = authenticated_download(name, source)
                current.update({
                    "source_verified": prov["source_git_blob_sha1_verified"],
                    "source_sha256": prov["source_sha256"],
                    "source_bytes": prov["bytes"],
                })
                measured = controlled_child(
                    source, prov["source_sha256"],
                    private / (name + "-summary.json"),
                    private / (name + "-private.log")
                )
                current.update(measured)
                current["source_verified"] = (
                    current["source_verified"] and
                    measured.get("source_sha256_verified") is True
                )
            except Exception as exc:
                current["status"] = "SOURCE_OR_MEASUREMENT_BLOCKED"
                current["exception_class"] = type(exc).__name__
            save_json(output_dir / "summary.json", result)
            print(json.dumps({
                "model": name, "status": current.get("status"),
                "measured_triangles": current.get("triangle_total_measured"),
                "complete": current.get("triangle_total_is_complete", False),
            }), flush=True)
    result["status"] = (
        "COMPLETE_CAPACITY_MEASUREMENT_NOT_3D_ACCEPTANCE"
        if len(result["reports"]) == 2 and all(
            item.get("status") == "COMPLETE_ALL_MEMBERS_MEASURED"
            and item.get("source_verified") is True
            for item in result["reports"]
        ) else "INCOMPLETE_CAPACITY_MEASUREMENT_NOT_3D_ACCEPTANCE"
    )
    save_json(output_dir / "summary.json", result)
    return 0 if result["status"].startswith("COMPLETE_") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--expected-sha")
    parser.add_argument("--child-output", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.source is None or args.expected_sha is None or args.child_output is None:
            parser.error("child requires source, expected SHA and child-output")
        raise SystemExit(run_child(args.source, args.expected_sha, args.child_output))
    if args.output is None:
        parser.error("--output required")
    raise SystemExit(main(args.output))
