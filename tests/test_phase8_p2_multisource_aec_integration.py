"""Phase 8 P2: one actual SQLite project, IFC + DXF + PDF + manual AEC.

All dimensions and source ownership are explicitly provided as synthetic
engineering fixtures. No model geometry, quantity, rate, or review is inferred.
This is automated software evidence, not a real-site signoff or native DWG
converter certification.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from hashlib import sha256

import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp
from core.reports.aec_office_package import audit_boq
from test_phase2_priority5_closure import crosswalk_case
from test_recovery_13_finishes_five_floors import explicit_inputs


def _quantity(project, code):
    return sum(
        (Decimal(str(row["quantity"])) for row in project["boq"]
         if row["item_code"] == code), Decimal("0")
    )


def _synthetic_plan(tmp_path):
    import pymupdf

    path = tmp_path / "five-floor-explicit-slab.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=220, height=220)
        page.draw_rect(pymupdf.Rect(20, 20, 120, 100))
        pdf.save(path)
    return path


def test_ifc_dxf_pdf_and_manual_mechanical_electrical_finishing_share_one_persistent_boq(tmp_path):
    """Independent source dimensions and work/material ownership never collapse."""
    app, ifc_path, dxf_path, cad_session, proposal, kw = crosswalk_case(tmp_path)
    try:
        # IFC is only reviewed physical ownership; the distinct CAD source
        # supplies the measured 4 m and is the *only* committed quantity.
        crosswalk = app.save_ifc_crosswalk("P", **kw)
        assert crosswalk["member_id"] == "B1"
        assert app.open_project("P")["boq"] == []
        item = kw["item_id"]
        receipt = app.commit_drawing_takeoff_to_boq(
            "P", kw["session_id"], [item], expected_session_revision=1
        )
        assert receipt["boq_count"] >= 1
        assert _quantity(app.open_project("P"), "TEST") == Decimal("4")

        for n in (2, 3, 4, 5):
            app.add_project_floor("P", f"Explicit synthetic floor {n}", level=f"F{n}")
        app.add_project_member("P", "SLAB-5", "F5", "slab")

        # The following independently scheduled quantity oracles correspond to
        # different real work classes and distinct synthetic physical sources.
        app.add_takeoff(
            "P", "building", "wall", source_id="manual:F2:W2",
            system="F2", length=10, height=3, count=1, openings=2,
        )
        app.add_takeoff(
            "P", "mechanical", "pipe", source_id="manual:F3:PIPE",
            system="F3", length=12, count=3,
        )
        app.add_takeoff(
            "P", "electrical", "cable_tray",
            source_id="manual:F4:CABLE-TRAY", system="F4",
            length=4, count=3,
        )
        finish = app.add_assembly_takeoff(
            "P", "wall_tile", explicit_inputs("wall_tile"),
            floor_id="F5", location_id="QA-ROOM-5",
            approved_by="independent-synthetic-reviewer",
        )
        assert {x["component_role"] for x in finish["rows"]} == {
            "work", "procurement", "material"
        }

        pdf_path = _synthetic_plan(tmp_path)
        pdf_session = DrawingTakeoffSession(str(pdf_path))
        pdf_session.calibrate(1, 100, 5)
        pdf_item = pdf_session.add_polygon(
            [Point(20, 20), Point(120, 20), Point(120, 100), Point(20, 100)],
            floor_id="F5", member_id="SLAB-5",
            quantity_owner="synthetic unique F5 slab",
            takeoff_code="PDF_SLAB_AREA",
            page=1,
        )
        assert Decimal(str(pdf_item.quantity)) == Decimal("20")
        saved_pdf = app.save_drawing_takeoff_session("P", pdf_session)
        app.commit_drawing_takeoff_to_boq(
            "P", saved_pdf["session_id"], [pdf_item.id],
            expected_session_revision=saved_pdf["revision"],
        )

        project = app.open_project("P")
        assert audit_boq(project)["reconciled"] is True
        independently_expected = {
            "TEST": Decimal("4"),
            "wall": Decimal("28"),
            "pipe": Decimal("36"),
            "cable_tray": Decimal("12"),
            "wall_tile_work": Decimal("28"),
            "PDF_SLAB_AREA": Decimal("20"),
        }
        for code, quantity in independently_expected.items():
            assert _quantity(project, code) == quantity, code
        assert len(project["boq"]) == len(independently_expected)
        assert len({r["source_id"] for r in project["takeoffs"]}) == len(project["takeoffs"])
        assert all(row.get("unit_price") is None for row in project["boq"])
        assert {t["component_role"] for t in project["takeoffs"]
                if t.get("component_role")} == {"work", "procurement", "material"}
        assert all(
            r["item_code"] not in {"wall_tile_material", "wall_tile_procurement"}
            for r in project["boq"]
        )
        sources = [s for row in project["boq"] for s in row.get("source_ids", [])]
        assert len(sources) == len(set(sources)), "one physical source billed twice"
        assert len({x["source_sha256"] for x in project["drawing_sessions"].values()}) == 2
        assert sha256(dxf_path.read_bytes()).hexdigest() == project["drawing_sessions"][kw["session_id"]]["source_sha256"]

        # Price/statement may never be guessed from the display model or drawings.
        original, digest = deepcopy(project), app.store.current_digest("P")
        with pytest.raises(ValueError):
            app.recalculate_estimate("P")
        with pytest.raises(ValueError):
            app.save_statement_period("P", period_no=1,
                                      current_quantities={"TEST": 1})
        assert app.open_project("P") == original
        assert app.store.current_digest("P") == digest

        # Explicit duplicate takes nothing, including no extra owner or amount.
        with pytest.raises(ValueError):
            app.add_takeoff(
                "P", "mechanical", "pipe", source_id="manual:F3:PIPE",
                system="F3", length=12, count=3,
            )
        with pytest.raises(RuntimeError, match="نسخه"):
            app.commit_drawing_takeoff_to_boq(
                "P", saved_pdf["session_id"], [pdf_item.id],
                expected_session_revision=saved_pdf["revision"],
            )
        current_pdf_revision = app.open_project("P")["drawing_sessions"][saved_pdf["session_id"]]["revision"]
        assert current_pdf_revision > saved_pdf["revision"]
        with pytest.raises(ValueError, match="قبلاً"):
            app.commit_drawing_takeoff_to_boq(
                "P", saved_pdf["session_id"], [pdf_item.id],
                expected_session_revision=current_pdf_revision,
            )
        assert app.open_project("P") == original
        assert app.store.current_digest("P") == digest

        reopened = StructuralProApp(tmp_path / "app")
        try:
            assert reopened.open_project("P") == original
            assert reopened.store.current_digest("P") == digest
            assert reopened.store.db.execute("pragma integrity_check").fetchone()[0] == "ok"
            assert not reopened.store.db.execute("pragma foreign_key_check").fetchall()
        finally:
            reopened.store.close()
    finally:
        app.store.close()


@pytest.mark.parametrize("tamper", ["ifc", "dxf", "review_json"])
def test_trisource_crosswalk_rejects_tamper_before_boq_write(tmp_path, tamper):
    """A mixed-source review is never automatic payment authority."""
    from pathlib import Path
    app, ifc_path, dxf_path, _, proposal, kw = crosswalk_case(tmp_path)
    try:
        before = deepcopy(app.open_project("P"))
        digest = app.store.current_digest("P")
        path = {
            "ifc": ifc_path,
            "dxf": dxf_path,
            "review_json": Path(kw["evidence_path"]),
        }[tamper]
        path.write_bytes(path.read_bytes() + b"\nsource-modified-after-review")
        with pytest.raises((ValueError, RuntimeError)):
            app.save_ifc_crosswalk("P", **kw)
        assert app.open_project("P") == before
        assert app.store.current_digest("P") == digest
        assert not app.open_project("P")["boq"]
    finally:
        app.store.close()
