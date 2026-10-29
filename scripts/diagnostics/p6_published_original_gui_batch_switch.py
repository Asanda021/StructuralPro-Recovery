"""Large pinned independent IFC4 through StructuralPro's ORIGINAL 2D->3D UI.

Uses original MIT published models, real source hash, real Qt widgets, original
async 3D Worker, source-only IFC identities and explicit batch swap. No GUID,
author, geometry, vertex, building file or QTO is published. Bounds each
model in a child and treats failures as failures, never inferred PASS.
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
    REV, authenticated_download, save_json,
)

TIMEOUT_PER_MODEL = 270


def _until(app, condition, seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.025)
    return bool(condition())


def child(path: Path, expected_sha: str, name: str, out: Path) -> int:
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog

    state = {
        "model": name,
        "status": "NOT_ACCEPTED",
        "source_verified": False,
        "quantity_authority": False,
        "ui_acceptance_is_one_batch_at_a_time": True,
    }
    started = time.monotonic()
    app = QApplication.instance() or QApplication([])
    main = None
    try:
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise ValueError("SOURCE_SHA_MISMATCH")
        state["source_verified"] = True
        main = GraphicalTakeoffDialog()
        main.ifc_revision.setText("RWTH-BATCH-" + REV[:12])
        main.open_cad_async(path)
        if not _until(app, lambda: main._cad_job is None, 115):
            raise RuntimeError("NORMAL_FILE_PICKER_SUBPROCESS_TIMEOUT")
        if main.viewer.kind != "ifc":
            raise ValueError("ORIGINAL_DRAWING_SOURCE_NOT_IFC")
        document = main.viewer.ifc_document
        if document.source_sha256 != expected_sha:
            raise ValueError("DRAWING_DIGEST_MISMATCH")
        count = len(document.source_roster)
        represented = sum(flag for _, flag in document.source_roster)
        expected = {
            "architecture": (957, 949, 8),
            "ventilation": (1310, 1310, 0),
        }[name]
        if (count, represented, count - represented) != expected:
            raise ValueError("SOURCE_IDENTITY_CENSUS_MISMATCH")
        if len(document.meshes) != 1:
            raise ValueError("LARGE_2D_PREVIEW_NOT_EXPLICITLY_BOUNDED")
        state["drawing_preview_member_count"] = len(document.meshes)
        state["source_member_count"] = count
        state["without_geometry"] = count - represented
        state["two_dimensional_not_loaded"] = represented - 1

        main.open_ifc_3d()
        if not _until(app, lambda: main._ifc_3d_loader is None, 110):
            raise RuntimeError("INITIAL_3D_WORKER_TIMEOUT")
        window = main._ifc_3d_dialog
        if window is None:
            raise ValueError("ORIGINAL_3D_WINDOW_NOT_OPEN")
        scene = window.scene
        if scene.display_catalog is None:
            raise ValueError("FULL_SOURCE_LEDGER_MISSING")
        if (scene.display_catalog["source_member_count"] != count or
                len(scene.meshes) != 1 or
                scene.source_sha256 != expected_sha or
                scene.quantity_authority is not False):
            raise ValueError("INITIAL_3D_SOURCE_CONTRACT_INVALID")
        original_id = scene.meshes[0].global_id
        window.canvas.choose_member(original_id)
        if window.canvas.selected_id != original_id:
            raise ValueError("SELECTED_SOURCE_MEMBER_NOT_PICKABLE")
        by_type = {}
        for member in scene.display_catalog["members"]:
            if member["status"] == "without_geometry":
                continue
            by_type.setdefault(member["ifc_type"], []).append(member["global_id"])
        kind = next((k for k in sorted(by_type) if len(by_type[k]) >= 2), None)
        if not kind:
            raise ValueError("NO_DUPLICATED_REAL_SOURCE_TYPE")
        window.batch_type.setCurrentIndex(window.batch_type.findData(kind))
        window.batch_size.setValue(1)
        selected = window._filtered_batch_ids()
        chosen_page = 1 if selected[0] != original_id else 2
        window.batch_page.setValue(chosen_page)
        expected_new_id = window._filtered_batch_ids()[chosen_page - 1]
        if expected_new_id == original_id or not window.request_selected_batch():
            raise ValueError("BATCH_SWITCH_NOT_REQUESTED")
        if not _until(app, lambda: main._ifc_3d_loader is None, 110):
            raise RuntimeError("SWAPPED_3D_WORKER_TIMEOUT")
        if (main._ifc_3d_dialog is not window
                or window.scene.source_sha256 != expected_sha
                or {m.global_id for m in window.scene.meshes} != {expected_new_id}
                or window.canvas.selected_id is not None):
            raise ValueError("ATOMIC_BATCH_SWAP_OR_STALE_SELECTION_FAILED")
        counts = window.scene.display_catalog["counts"]
        if counts != {
            "displayed": 1, "not_loaded": represented - 1,
            "without_geometry": count - represented,
        }:
            raise ValueError("UNVERIFIED_SOURCE_MEMBER_COUNTS")
        if main.session.items:
            raise ValueError("VIEWER_PUBLISHED_UNAUTHORIZED_TAKEOFF")
        state.update({
            "status": "PASS_ORIGINAL_UI_LARGE_SOURCE_TWO_REAL_BATCHES",
            "source_catalog_complete": True,
            "first_member_rendered": True,
            "selected_new_type": kind,
            "batch_size": 1,
            "second_batch_rendered": True,
            "old_pick_revoked": True,
            "source_counts": counts,
            "boq_mutated": False,
            "quantity_authority": False,
            "source_sha256_stable": True,
        })
    except Exception as exc:
        state["status"] = "BLOCKED_ORIGINAL_UI"
        state["error_class"] = type(exc).__name__
        # Traceback and error details remain local, not in artifact.
    finally:
        state["wall_seconds"] = round(time.monotonic() - started, 2)
        save_json(out, state)
        if main is not None:
            try:
                main.cancel_ifc_3d_loading()
                win = getattr(main, "_ifc_3d_dialog", None)
                if win is not None:
                    win.close()
                main.close()
                app.processEvents()
            except Exception:
                pass
    return 0 if state["status"].startswith("PASS_") else 1


def parent(out: Path) -> int:
    out.mkdir(parents=True, exist_ok=False)
    summary = {
        "kind": "p6_g2_original_gui_published_large_ifc4_v1",
        "upstream": "RWTH-E3D/DigitalHub",
        "source_commit": REV,
        "tested_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "platform": sys.platform,
        "model_files_not_redistributed": True,
        "not_full_model_3d_acceptance": True,
        "quantity_authority": False,
        "reports": [],
        "status": "RUNNING",
    }
    save_json(out / "summary.json", summary)
    with tempfile.TemporaryDirectory(prefix="p6-original-ui-published-", ignore_cleanup_errors=True) as td:
        temp = Path(td)
        for name in ("architecture", "ventilation"):
            state = {"model": name, "status": "DOWNLOAD_PENDING"}
            summary["reports"].append(state)
            source = temp / (name + ".ifc")
            try:
                prov = authenticated_download(name, source)
                artifact = temp / (name + ".json")
                with (temp / (name + "-private.log")).open("wb") as private:
                    try:
                        p = subprocess.run(
                            [sys.executable, str(Path(__file__).resolve()), "--child",
                             "--source", str(source), "--sha", prov["source_sha256"],
                             "--model", name, "--report", str(artifact)],
                            cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, "PYTHONPATH": "."},
                            timeout=TIMEOUT_PER_MODEL, check=False,
                            stdout=private, stderr=subprocess.STDOUT)
                        state["exit_code"] = p.returncode
                    except subprocess.TimeoutExpired:
                        state["exit_code"] = 124
                if artifact.is_file():
                    state.update(json.loads(artifact.read_text(encoding="utf-8")))
                state["source_git_blob_verified"] = prov["source_git_blob_sha1_verified"]
                state["source_sha256"] = prov["source_sha256"]
            except Exception as exc:
                state.update({"status": "SOURCE_OR_GUI_BLOCKED",
                              "error_class": type(exc).__name__})
            save_json(out / "summary.json", summary)
            print(json.dumps({
                "model": name, "status": state["status"],
                "counts": state.get("source_counts"), "exit": state.get("exit_code")
            }), flush=True)
    summary["status"] = (
        "PASS_ORIGINAL_GUI_TWO_PUBLISHED_LARGE_SOURCE_BATCHES_NOT_FULL_3D"
        if len(summary["reports"]) == 2 and all(
            r.get("status") == "PASS_ORIGINAL_UI_LARGE_SOURCE_TWO_REAL_BATCHES"
            and r.get("source_git_blob_verified") is True and r.get("exit_code") == 0
            for r in summary["reports"]
        ) else "BLOCKED_ORIGINAL_GUI_LARGE_SOURCE_BATCHES"
    )
    save_json(out / "summary.json", summary)
    return 0 if summary["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--sha")
    parser.add_argument("--model", choices=("architecture", "ventilation"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.source is None or args.sha is None or args.model is None or args.report is None:
            parser.error("missing required child args")
        raise SystemExit(child(args.source, args.sha, args.model, args.report))
    if args.output is None:
        parser.error("output required")
    raise SystemExit(parent(args.output))
