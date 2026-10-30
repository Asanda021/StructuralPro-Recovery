"""P7 P2 synthetic five-storey Golden for source-backed *per-floor* exports.

This is a five-page genuine vector PDF and one persisted five-floor SQLite
project; it does NOT imply the software can infer missing building geometry.
"""
from __future__ import annotations

from decimal import Decimal
import json

import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp
from core.reports.source_backed_2d_office_bundle import export_verified_2d_office_bundle


def test_five_storey_real_pdf_boq_office_bundle_keeps_each_floor_isolated(tmp_path):
    import pymupdf

    source = tmp_path / "five_storey_vector.pdf"
    with pymupdf.open() as doc:
        for _ in range(5):
            page = doc.new_page(width=220, height=220)
            page.draw_rect(pymupdf.Rect(10, 10, 200, 200))
        doc.save(source)

    app = StructuralProApp(tmp_path / "store")
    app.create_project("پروژه مرجع پنج طبقه", "P5")
    session = DrawingTakeoffSession(str(source))
    items, expected = [], {}
    for page in range(1, 6):
        floor_id = f"L{page}"
        member_id = f"W{page}"
        app.add_project_floor("P5", f"طبقه {page}", level=floor_id)
        app.add_project_member("P5", member_id, floor_id, "سقف")
        session.calibrate(page, 100, 5)
        width, height = 40 + page * 10, 20 + page * 5
        outer = [(20,20),(20+width,20),(20+width,20+height),(20,20+height)]
        opening = [(30, 25),(40, 25),(40, 35),(30, 35)] if page == 3 else None
        item = session.add_polygon(
            [Point(*p) for p in outer],
            holes=[[Point(*p) for p in opening]] if opening else (),
            opening_refs=[f"O{page}"] if opening else (),
            page=page, floor_id=floor_id, member_id=member_id,
            quantity_owner=f"سند برداری طبقه {page}",
            source=f"verified-floor-{page}", takeoff_code=f"WALL_{page}",
        )
        items.append(item)
        expected[page] = Decimal(width * height - (100 if opening else 0)) * Decimal("0.0025")
    receipt = app.save_drawing_takeoff_session("P5", session)
    app.commit_drawing_takeoff_to_boq(
        "P5", receipt["session_id"], [i.id for i in items],
        expected_session_revision=receipt["revision"],
    )
    before = app.open_project("P5")
    original_digest = app.store.current_digest("P5")
    record = before["drawing_sessions"][receipt["session_id"]]
    generated = []
    try:
        assert len(before["boq"]) == 5
        for page, item in enumerate(items, 1):
            target = tmp_path / f"floor_{page}_bundle"
            built = export_verified_2d_office_bundle(
                app, project_id="P5", session_id=receipt["session_id"],
                expected_project_version=before["_meta"]["version"],
                expected_session_revision=record["revision"],
                revision="R1", page=page, selected_takeoff_ids=(item.id,),
                destination=target,
            )
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            assert manifest == built["manifest"]
            link = manifest["overlay"]["links"][0]
            assert link["floor_id"] == f"L{page}"
            assert link["member_id"] == f"W{page}"
            assert link["page"] == page
            assert Decimal(link["quantity"]) == expected[page]
            assert link["boq_row_id"] == f"boq-item-no:{page}"
            assert len(manifest["files"]) == 6
            assert (target / "report.pdf").is_file()
            assert (target / "report.xlsx").is_file()
            assert (target / "report.docx").is_file()
            assert (target / "report.csv").is_file()
            generated.append(target)

        assert len(generated) == 5
        assert app.store.current_digest("P5") == original_digest
        assert app.open_project("P5") == before
        # A single map page cannot silently merge members from other floors.
        with pytest.raises(ValueError, match="صفحات"):
            export_verified_2d_office_bundle(
                app, project_id="P5", session_id=receipt["session_id"],
                expected_project_version=before["_meta"]["version"],
                expected_session_revision=record["revision"],
                revision="R1", page=1, selected_takeoff_ids=(items[0].id, items[1].id),
                destination=tmp_path / "invalid_mixed_pages",
            )
        assert not (tmp_path / "invalid_mixed_pages").exists()
    finally:
        app.store.close()
