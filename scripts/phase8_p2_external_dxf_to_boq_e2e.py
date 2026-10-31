"""Real external CC0 DXF -> reviewed CAD selection -> SQLite -> BOQ.

Proof is intentionally limited to ONE explicitly selected QA entity, not the entire
site plan, never a payable construction item. Does not build an executable.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import Request, build_opener

from scripts.phase8_p2_cc0_dxf_import_probe import SOURCE_URL, CATALOG_URL, EXPECTED_SHA256, MAX_BYTES
from scripts.phase8_p2_real_dwg_source_probe import RestrictedRedirect, approved_url
from core.drawings.dwg_takeoff import DWGTakeoffEngine, cad_entity_geometry
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp

PROJECT_ID = "CC0-EXTERNAL-DXF-QA"
ITEM_CODE = "EXTERNAL_DXF_QA_LENGTH_ONLY"


def source_bytes() -> bytes:
    if not approved_url(SOURCE_URL):
        raise ValueError("Source not in allowlist")
    with build_opener(RestrictedRedirect()).open(
        Request(SOURCE_URL, headers={"User-Agent": "StructuralPro-source-test/1.0"}),
        timeout=35,
    ) as response:
        if not approved_url(response.geturl()):
            raise ValueError("Untrusted redirect")
        data = response.read(MAX_BYTES + 1)
    if not 1024 <= len(data) <= MAX_BYTES or sha256(data).hexdigest() != EXPECTED_SHA256:
        raise ValueError("External source differs from pinned reference")
    return data


def eligible_entity(document):
    candidates = []
    for entity in document.entities:
        if entity.entity_type != "LINE" or not entity.handle:
            continue
        try:
            selected, points, length = cad_entity_geometry(document, entity.handle, "length")
        except (ValueError, TypeError):
            continue
        if selected.data.get("layer_visible") is not True or len(points) != 2:
            continue
        if length <= 0 or not math.isfinite(length):
            continue
        from_xy = math.hypot(points[1][0] - points[0][0], points[1][1] - points[0][1])
        if not math.isclose(length, from_xy, rel_tol=1e-12, abs_tol=1e-8):
            raise ValueError("Parsed LINE geometric oracle disagrees with source geometry")
        candidates.append((entity.handle, length, entity.layer))
    if not candidates:
        raise ValueError("No eligible visible measurable CAD LINE exists")
    return sorted(candidates, key=lambda item: item[0])[0]


def audit() -> dict:
    data = source_bytes()
    with TemporaryDirectory(prefix="p8p2_external_dxf_to_boq_") as temp:
        root = Path(temp)
        drawing = root / "published-site-plan.dxf"
        drawing.write_bytes(data)
        doc = DWGTakeoffEngine().import_file(drawing)
        if doc.source_sha256 != EXPECTED_SHA256 or doc.units != "mm":
            raise ValueError("Real external DXF source or unit mismatch")
        handle, independently_recomputed_m, layer = eligible_entity(doc)

        app = StructuralProApp(root / "project")
        try:
            app.create_project("External source software QA only", PROJECT_ID)
            app.add_project_floor(PROJECT_ID, "QA source-only floor", level="QA-F1")
            app.add_project_member(PROJECT_ID, "QA-EXT-LINE-1", "QA-F1", "unclassified CAD line (not a physical construction item)")

            session = DrawingTakeoffSession(str(drawing))
            item = session.add_cad_entity(
                doc, handle, "length", takeoff_code=ITEM_CODE, floor_id="QA-F1",
                member_id="QA-EXT-LINE-1",
                quantity_owner="EXPLICIT QA SELECTION ONLY - NOT CONSTRUCTION CERTIFICATION",
                created_by="source-fixture-author",
                reference="Pinned CC0 source; explicit selection and independent endpoint calculation",
            )
            if not math.isclose(item.quantity, independently_recomputed_m, rel_tol=1e-12):
                raise ValueError("CAD selection and independent numeric calculation differ")
            saved = app.save_drawing_takeoff_session(PROJECT_ID, session)

            # A source-only, unreviewed candidate has NO automatic BOQ authority.
            before = deepcopy(app.open_project(PROJECT_ID))
            digest = app.store.current_digest(PROJECT_ID)
            try:
                app.commit_drawing_takeoff_to_boq(
                    PROJECT_ID, saved["session_id"], [item.id],
                    expected_session_revision=saved["revision"],
                )
            except (ValueError, RuntimeError):
                pass
            else:
                raise AssertionError("Unreviewed real external DXF was committed")
            assert app.open_project(PROJECT_ID) == before
            assert app.store.current_digest(PROJECT_ID) == digest

            # A changed drawing after user review must not be committed.
            session.review_cad_entity(
                item.id, reviewer="distinct-source-fixture-reviewer",
                note="QA review of exact pinned source/handle and endpoint-derived length; not site certification",
            )
            reviewed = app.save_drawing_takeoff_session(
                PROJECT_ID, session, session_id=saved["session_id"],
                expected_revision=saved["revision"],
            )
            drawing.write_bytes(data + b"\n0\n999\nqa-source-tampered\n")
            before_tamper = deepcopy(app.open_project(PROJECT_ID))
            digest_tamper = app.store.current_digest(PROJECT_ID)
            try:
                app.commit_drawing_takeoff_to_boq(
                    PROJECT_ID, reviewed["session_id"], [item.id],
                    expected_session_revision=reviewed["revision"],
                )
            except (ValueError, RuntimeError):
                pass
            else:
                raise AssertionError("Changed external DXF was committed")
            assert app.open_project(PROJECT_ID) == before_tamper
            assert app.store.current_digest(PROJECT_ID) == digest_tamper

            # Restore bytes exactly, with independently reviewed item unchanged.
            drawing.write_bytes(data)
            approved = app.commit_drawing_takeoff_to_boq(
                PROJECT_ID, reviewed["session_id"], [item.id],
                expected_session_revision=reviewed["revision"],
            )
            assert approved["boq_count"] == 1
            project = deepcopy(app.open_project(PROJECT_ID))
            assert len(project["boq"]) == 1
            row = project["boq"][0]
            assert row["item_code"] == ITEM_CODE and row["unit_price"] is None
            assert Decimal(str(row["quantity"])) == Decimal(str(item.quantity))
            assert project["takeoffs"][0]["params"]["cad_evidence"]["handle"] == handle
            assert project["takeoffs"][0]["params"]["source_sha256"] == EXPECTED_SHA256

            digest_committed = app.store.current_digest(PROJECT_ID)
            snapshot = deepcopy(project)
            for expected_revision in (reviewed["revision"], approved["revision"]):
                try:
                    app.commit_drawing_takeoff_to_boq(
                        PROJECT_ID, reviewed["session_id"], [item.id],
                        expected_session_revision=expected_revision,
                    )
                except (RuntimeError, ValueError):
                    pass
                else:
                    raise AssertionError("Duplicate/stale source was committed")
            assert app.open_project(PROJECT_ID) == snapshot
            assert app.store.current_digest(PROJECT_ID) == digest_committed
            assert app.store.db.execute("pragma integrity_check").fetchone()[0] == "ok"
            assert not app.store.db.execute("pragma foreign_key_check").fetchall()
        finally:
            app.store.close()

        reopened = StructuralProApp(root / "project")
        try:
            assert reopened.open_project(PROJECT_ID) == snapshot
            assert reopened.store.current_digest(PROJECT_ID) == digest_committed
        finally:
            reopened.store.close()
        return {
            "status": "EXTERNAL_CC0_DXF_ONE_EXPLICIT_REVIEWED_LINE_TO_PERSISTED_BOQ_PASS",
            "source_catalog": CATALOG_URL,
            "source_sha256": EXPECTED_SHA256,
            "source_sha256_pinned_from_prior_2os_read": True,
            "source_sha256_independently_published_by_author": False,
            "source_bytes": len(data), "dxf_version": doc.dxf_version,
            "units": doc.units, "selected_handle": handle, "selected_layer": layer,
            "selected_length_m": str(item.quantity),
            "independent_endpoint_length_m": str(independently_recomputed_m),
            "persisted_boq_rows": 1, "reopened_sqlite_equal": True,
            "unreviewed_rejected": True, "changed_source_rejected": True,
            "duplicate_and_stale_rejected": True,
            "non_payable_qa": True, "real_site_certified": False,
            "dwg_native_bridge_tested": False, "production_release": "NO_GO",
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
