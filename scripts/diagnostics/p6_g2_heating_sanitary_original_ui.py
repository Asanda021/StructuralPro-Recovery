"""Phase 6 G2: independently published IFC4 heating/sanitary models through real Qt UI.

Source: RWTH-E3D/DigitalHub at pinned commit, verified Git blob SHA-1/size.
This does not certify all geometries, complete IFC models, mapping, BOQ/QTO,
physical Windows UAT, renovation or site classes. No source model uploaded.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

from scripts.diagnostics.p6_independent_ifc_public_reference import REV, save_json

EXTRA_MODELS = {
    "heating": {
        "path": "Version_2/DigitalHub_FM-HZG_v2.ifc",
        "git_blob_sha1": "46fddf2f6a0b3a3855e701dede61adcb359c2031",
        "size": 20890415,
    },
    "sanitary": {
        "path": "Version_2/DigitalHub_FM-SAN_v2.ifc",
        "git_blob_sha1": "5725d3f84ff71eac57bde5e69a422f23a855ffd5",
        "size": 25178864,
    },
    "sanitary_v1": {
        "path": "Version_1/FM_SAN_DigitalHub_v1.ifc",
        "git_blob_sha1": "6fe0d15f8e139da47b33111431d9cff72a0b1c85",
        "size": 16846052,
    },
}
MAX_SOURCE_BYTES = 30 * 1024 * 1024
MAX_TRIANGLES = 40_000
PER_MODEL_SECONDS = 300


def fetch_pinned(model_name: str, target: Path) -> str:
    spec = EXTRA_MODELS[model_name]
    uri = "https://raw.githubusercontent.com/RWTH-E3D/DigitalHub/" + REV + "/" + spec["path"]
    sha1 = hashlib.sha1()
    sha1.update(("blob " + str(spec["size"]) + "\0").encode("ascii"))
    sha256 = hashlib.sha256()
    size = 0
    request = Request(uri, headers={"User-Agent": "StructuralPro-G2-source-audit/1.0"})
    with urlopen(request, timeout=80) as response, target.open("wb") as output:
        if response.status != 200:
            raise ValueError("PINNED_DOWNLOAD_HTTP_ERROR")
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_SOURCE_BYTES or size > spec["size"]:
                raise ValueError("PINNED_SOURCE_TOO_LARGE")
            sha1.update(chunk)
            sha256.update(chunk)
            output.write(chunk)
    if size != spec["size"] or sha1.hexdigest() != spec["git_blob_sha1"]:
        raise ValueError("PINNED_SOURCE_SIZE_OR_GIT_BLOB_MISMATCH")
    return sha256.hexdigest()


def pump(app, predicate, limit=115):
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        app.processEvents()
        if predicate():
            return True
        time.sleep(.025)
    return bool(predicate())


def examine(source: Path, expected_sha: str, model_name: str, record: Path, *, preferred_target_type: str | None = None) -> int:
    import ifcopenshell
    from PySide6.QtWidgets import QApplication
    from app.graphical_takeoff import GraphicalTakeoffDialog

    app = QApplication.instance() or QApplication([])
    gui = None
    evidence = {"model": model_name, "status": "NOT_ACCEPTED", "quantity_authority": False,
                "model_is_real_published_reference": True, "full_simultaneous_geometry_accepted": False}
    started = time.monotonic()
    stage = "SOURCE_DIGEST"
    try:
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected_sha:
            raise ValueError("DOWNLOADED_SOURCE_SHA_MISMATCH")
        stage = "IFC_PARSE_INDEPENDENT"
        independent = ifcopenshell.open(str(source))
        if str(independent.schema) != "IFC4":
            raise ValueError("SOURCE_SCHEMA_NOT_IFC4")
        elements = independent.by_type("IfcElement")
        ids = {obj.GlobalId for obj in elements}
        represented = {obj.GlobalId for obj in elements if getattr(obj, "Representation", None)}
        if not ids or len(ids) != len(elements) or len(represented) < 2:
            raise ValueError("SOURCE_HAS_NO_UNIQUE_REPRESENTED_ELEMENTS")
        stage = "SOURCE_CLASS_CENSUS"
        types = Counter(obj.is_a() for obj in elements if obj.GlobalId in represented)
        stage = "GUI_CREATE"
        gui = GraphicalTakeoffDialog()
        gui.ifc_revision.setText("RWTH-REAL-" + REV[:12])
        stage = "NORMAL_FILE_PICKER_QPROCESS"
        gui.open_cad_async(source)  # genuine user file-picker/QProcess path
        if not pump(app, lambda: gui._cad_job is None):
            raise RuntimeError("IFC_NORMAL_FILE_PICKER_TIMEOUT")
        if gui.viewer.kind != "ifc":
            raise ValueError("IFC_FILE_PICKER_DID_NOT_LOAD")
        stage = "IFC_DRAWING_CONTRACT"
        drawing = gui.viewer.ifc_document
        if drawing is None or drawing.source_sha256 != expected_sha:
            raise ValueError("DRAWING_SOURCE_MISMATCH")
        roster = drawing.source_roster
        if ({gid for gid, _ in roster} != ids or
                {gid for gid, flag in roster if flag} != represented):
            raise ValueError("CROSS_PARSER_FULL_SOURCE_CENSUS_MISMATCH")
        stage = "IFC_DRAWING_PREVIEW"
        if not drawing.meshes or not all(m.global_id in represented for m in drawing.meshes):
            raise ValueError("NO_GENUINE_DRAWING_PREVIEW_GEOMETRY")
        if sum(len(m.triangles) for m in drawing.meshes) > MAX_TRIANGLES:
            raise ValueError("DRAWING_PREVIEW_OVER_CAP")
        stage = "INITIAL_3D_WORKER"
        gui.open_ifc_3d()
        if not pump(app, lambda: gui._ifc_3d_loader is None):
            raise RuntimeError("IFC_INITIAL_3D_TIMEOUT")
        view = gui._ifc_3d_dialog
        if view is None or view.scene.display_catalog is None:
            raise ValueError("NO_ORIGINAL_3D_SOURCE_LEDGER")
        before = view.scene
        before.validate_source()
        if (before.source_sha256 != expected_sha or
                before.quantity_authority is not False or
                before.display_catalog["source_member_count"] != len(ids)):
            raise ValueError("INITIAL_3D_CONTRACT_INVALID")
        old_gid = before.meshes[0].global_id
        view.canvas.choose_member(old_gid)
        if view.canvas.selected_id != old_gid:
            raise ValueError("ORIGINAL_MEMBER_CANNOT_BE_SELECTED")
        stage = "FULL_SOURCE_3D_LEDGER"
        full = before.display_catalog["members"]
        if ({e["global_id"] for e in full} != ids or
                {e["global_id"] for e in full if e["status"] == "without_geometry"} != ids - represented):
            raise ValueError("SOURCE_LEDGER_LOST_MEMBERS")
        # Select another real SOURCE member, not a placeholder. A distinct floor
        # is preferred when available. The filter/pager must find that identity.
        stage = "BATCH_FILTER_SELECTION"
        candidates = [row for row in full
                      if row["global_id"] in represented and row["global_id"] != old_gid
                      and (preferred_target_type is None or row["ifc_type"] == preferred_target_type)]
        if not candidates:
            raise ValueError("NO_OTHER_MEMBER_WITH_REQUIRED_SOURCE_CLASS")
        candidates.sort(key=lambda row: (
            0 if row["storey_id"] and row["storey_id"] != before.meshes[0].storey_id else 1,
            row["ifc_type"], row["global_id"]))
        target = candidates[0]
        target_type = target["ifc_type"]
        view.batch_type.setCurrentIndex(view.batch_type.findData(target_type))
        if view.batch_type.currentData() != target_type:
            raise ValueError("SOURCE_IFC_TYPE_NOT_OFFERED")
        if target["storey_id"] is not None:
            view.batch_storey.setCurrentIndex(view.batch_storey.findData(target["storey_id"]))
            if view.batch_storey.currentData() != target["storey_id"]:
                raise ValueError("SOURCE_STOREY_NOT_OFFERED")
        view.batch_size.setValue(1)
        candidates_from_controls = view._filtered_batch_ids()
        if target["global_id"] not in candidates_from_controls:
            raise ValueError("FILTER_HID_ACTUAL_SOURCE_ID")
        page = candidates_from_controls.index(target["global_id"]) + 1
        view.batch_page.setValue(page)
        stage = "SECOND_BATCH_WORKER"
        if not view.request_selected_batch():
            raise ValueError("REAL_GUI_DID_NOT_DISPATCH_SELECTED_BATCH")
        if not pump(app, lambda: gui._ifc_3d_loader is None):
            raise RuntimeError("SECOND_REAL_SOURCE_WORKER_TIMEOUT")
        after = view.scene
        after.validate_source()
        if gui._ifc_3d_dialog is not view or after is before:
            raise ValueError("REAL_BATCH_NOT_ATOMICALLY_SWAPPED")
        if (after.source_sha256 != expected_sha or
                {m.global_id for m in after.meshes} != {target["global_id"]} or
                after.quantity_authority is not False):
            raise ValueError("NEW_SOURCE_BACKED_BATCH_INVALID")
        if view.canvas.selected_id is not None:
            raise ValueError("STALE_PICK_NOT_REVOKED")
        stage = "ATOMIC_SCENE_AND_SOURCE_COUNTS"
        counts = after.display_catalog["counts"]
        if counts != {"displayed": 1, "not_loaded": len(represented) - 1,
                      "without_geometry": len(ids) - len(represented)}:
            raise ValueError("INCOMPLETE_GLOBAL_SOURCE_COVERAGE_DISCLOSURE")
        if gui.session.items:
            raise ValueError("UNAUTHORIZED_BOQ_OR_TAKEOFF_WRITE")
        stage = "ACCEPTED"
        evidence.update({
            "status": "PASS_TWO_REAL_BATCHES_IN_ORIGINAL_QT_UI",
            "source_sha256_matches": True,
            "source_element_count": len(ids),
            "source_represented_count": len(represented),
            "source_unrepresented_count": len(ids) - len(represented),
            "different_real_source_member_selected": True,
            "different_storey_selected": target["storey_id"] != before.meshes[0].storey_id,
            "different_type_selected": target_type != before.meshes[0].ifc_type,
            "required_target_type_verified": target_type == preferred_target_type
                if preferred_target_type is not None else None,
            "represented_source_class_count": len(types),
            "represented_source_classes": sorted(types),
            "scene_member_count_after_swap": len(after.meshes),
            "catalog": counts,
            "old_pick_revoked": True,
            "boq_written": False,
            "quantity_authority": False,
        })
    except Exception as exc:
        evidence["status"] = "BLOCKED_OR_FAILED"
        evidence["error_class"] = type(exc).__name__
        evidence["failed_stage"] = stage
        if stage == "NORMAL_FILE_PICKER_QPROCESS":
            # Compare the two exact components used by the child QProcess:
            # independent BIM validation and the read-only drawing viewer.
            # Persist no original model details or raw free-form exceptions.
            import traceback
            from core.drawings.bim_adapter import BIMAdapter
            from core.drawings.viewer_model import DrawingViewerModel
            diagnosis = {}
            for label, attempt in (
                ("verified_bim_contract",
                 lambda: BIMAdapter().read_document(source, revision="diagnostic-only")),
                ("read_only_ifc_preview",
                 lambda: DrawingViewerModel().open(source)),
            ):
                try:
                    attempt()
                    diagnosis[label] = {"status": "PASS"}
                except Exception as component_exc:
                    frames = traceback.extract_tb(component_exc.__traceback__)
                    last = frames[-1] if frames else None
                    # Only controlled source filename basename + numeric lineno,
                    # not local directory, GUID, model name or exception contents.
                    diagnosis[label] = {
                        "status": "BLOCKED",
                        "error_type": type(component_exc).__name__,
                        "last_module": Path(last.filename).name if last else None,
                        "last_line": last.lineno if last else None,
                    }
            evidence["failure_isolation"] = diagnosis
        # Safe category only, never original paths, names or exception strings.
        safe = str(exc)
        evidence["error_category"] = ("NO_REPRESENTED_GEOMETRY" if "NO_UNIQUE_REPRESENTED" in safe
            else "SOURCE_IDENTITY_MISMATCH" if "SOURCE_CENSUS" in safe or "LOST_MEMBERS" in safe
            else "GEOMETRY_OR_CAPACITY" if "هندسه" in safe or "ظرفیت" in safe or "triangle" in safe.lower()
            else "FILE_PICKER_REJECTION" if "IFC_FILE_PICKER_DID_NOT_LOAD" in safe
            else "RUNTIME_OR_CONTRACT_ERROR")
        # Never publish free-text error, source filenames, GUIDs, vertices,
        # authors, individual model properties, sensitive SQL or QTO.
    finally:
        evidence["duration_seconds"] = round(time.monotonic() - started, 2)
        save_json(record, evidence)
        if gui is not None:
            try:
                gui.cancel_ifc_3d_loading()
                window = getattr(gui, "_ifc_3d_dialog", None)
                if window is not None:
                    window.close()
                gui.close()
                app.processEvents()
            except Exception:
                pass
    return 0 if evidence["status"].startswith("PASS_") else 1


def parent(output: Path, only: str | None = None) -> int:
    output.mkdir(parents=True, exist_ok=False)
    summary = {
        "kind": "phase6_g2_real_published_ifc4_heating_sanitary_original_gui",
        "upstream": "RWTH-E3D/DigitalHub",
        "source_pinned_commit": REV,
        "tested_product_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "models_are_same_published_project_not_independent_buildings": True,
        "source_files_uploaded": False,
        "boq_authority": False,
        "all_source_categories_accepted": False,
        "reports": [],
        "selected_models": [only] if only else list(EXTRA_MODELS),
        "status": "IN_PROGRESS",
    }
    save_json(output / "summary.json", summary)
    with tempfile.TemporaryDirectory(prefix="p6-g2-new-source-", ignore_cleanup_errors=True) as temp:
        folder = Path(temp)
        for model in ([only] if only else EXTRA_MODELS):
            row = {"model": model, "status": "SOURCE_NOT_VERIFIED"}
            summary["reports"].append(row)
            source = folder / (model + ".ifc")
            try:
                sha = fetch_pinned(model, source)
                row["pinned_blob_verified"] = True
                result = folder / (model + "-result.json")
                with (folder / (model + "-private-log.bin")).open("wb") as private:
                    try:
                        proc = subprocess.run(
                            [sys.executable, str(Path(__file__).resolve()), "--child",
                             "--model", model, "--source", str(source),
                             "--expected-sha", sha, "--report", str(result)],
                            stdout=private, stderr=subprocess.STDOUT,
                            cwd=Path(__file__).resolve().parents[2],
                            env={**os.environ, "PYTHONPATH": "."},
                            timeout=PER_MODEL_SECONDS, check=False)
                        row["child_exit_code"] = proc.returncode
                    except subprocess.TimeoutExpired:
                        row["child_exit_code"] = 124
                if result.is_file():
                    row.update(json.loads(result.read_text(encoding="utf-8")))
                row["pinned_source_sha256"] = sha
            except Exception as exc:
                row.update({"status": "SOURCE_OR_QT_BLOCKED",
                            "error_class": type(exc).__name__})
            save_json(output / "summary.json", summary)
            print(json.dumps({"model": model, "status": row["status"],
                              "element_count": row.get("source_element_count"),
                              "child_exit": row.get("child_exit_code")}), flush=True)
    ok = len(summary["reports"]) == len(summary["selected_models"]) and all(
        r.get("status") == "PASS_TWO_REAL_BATCHES_IN_ORIGINAL_QT_UI"
        and r.get("pinned_blob_verified") is True
        and r.get("child_exit_code") == 0
        for r in summary["reports"])
    summary["status"] = "PASS_SELECTED_PINNED_SOURCE_BATCH_LIMITED_SCOPE" if ok else "G2_SOURCE_COVERAGE_PARTIAL_OR_RED"
    save_json(output / "summary.json", summary)
    return 0 if ok else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--only", choices=tuple(EXTRA_MODELS), default=None)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--model", choices=tuple(EXTRA_MODELS))
    parser.add_argument("--expected-sha")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.child:
        if args.source is None or args.report is None or args.expected_sha is None or args.model is None:
            parser.error("child requires source, model, expected-sha and report")
        raise SystemExit(examine(args.source, args.expected_sha, args.model, args.report))
    if args.output is None:
        parser.error("--output required")
    raise SystemExit(parent(args.output, args.only))
