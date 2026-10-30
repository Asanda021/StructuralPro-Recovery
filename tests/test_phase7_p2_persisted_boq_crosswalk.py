"""Phase 7 P2: independently persisted SQLite takeoff -> BOQ -> SVG linkage.

Fixture uses actual StructuralProApp and source-backed vector PDF, not
fabricated BOQ/measurements. Read-only pass and negative tests.
"""
from copy import deepcopy
from decimal import Decimal

import pytest

from test_phase2_pdf_roof import fixture
from test_phase2_advanced_geometry_sqlite import polygon
from core.reports.source_backed_2d_overlay import link_source_backed_2d_overlay_to_boq


def _persisted(tmp_path, *, commit=True):
    app, _, _, _ = fixture(tmp_path)
    session, item, receipt = polygon(app, tmp_path / "plan.pdf")
    if commit:
        app.commit_drawing_takeoff_to_boq(
            "P", receipt["session_id"], [item.id],
            expected_session_revision=receipt["revision"],
        )
    project = app.open_project("P")
    version = project["_meta"]["version"]
    session_revision = project["drawing_sessions"][receipt["session_id"]]["revision"]
    kwargs = dict(
        session_id=receipt["session_id"],
        expected_project_version=version,
        expected_session_revision=session_revision,
        revision="R1", page=1, selected_takeoff_ids=(item.id,),
    )
    return app, project, kwargs, item


def test_real_sqlite_boq_item_links_to_source_svg_without_writes(tmp_path):
    app, project, kwargs, item = _persisted(tmp_path)
    before, digest = deepcopy(project), app.store.current_digest("P")
    try:
        result = link_source_backed_2d_overlay_to_boq(project, **kwargs)
        link = result["manifest"]["links"][0]
        assert result == link_source_backed_2d_overlay_to_boq(project, **kwargs)
        assert result["manifest"]["project_version"] == kwargs["expected_project_version"]
        assert result["manifest"]["session_revision"] == kwargs["expected_session_revision"]
        assert link["takeoff_id"] == item.id
        assert link["member_id"] == "P1" and link["floor_id"] == "L1"
        assert link["boq_row_id"] == "boq-item-no:1"
        assert link["quantity"] == project["boq"][0]["quantity"]
        assert link["source_id"] == project["takeoffs"][0]["source_id"]
        assert link["measurement_identity"] == project["takeoffs"][0]["params"]["measurement_identity"]
        assert "not_engineering_approval" in link["review_status"]
        assert result["manifest"]["quantity_authority"] is False
        assert result["manifest"]["financial_mutation"] is False
        assert project == before
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()


def test_missing_boq_commit_is_not_labeled_source_verified(tmp_path):
    app, project, kwargs, _ = _persisted(tmp_path, commit=False)
    try:
        with pytest.raises(ValueError, match="ثبت"):
            link_source_backed_2d_overlay_to_boq(project, **kwargs)
    finally:
        app.store.close()


@pytest.mark.parametrize("field, value", [
    ("boq.quantity", "999"),
    ("boq.unit", "kg"),
    ("boq.item_code", "OTHER"),
    ("boq.status", "cancelled"),
    ("boq.source_ids", ["unrelated"]),
    ("boq.item_no", True),
    ("takeoff.params.measurement_identity", "bad"),
    ("takeoff.params.geometry_evidence", {}),
    ("takeoff.params.geometry", [[0, 0], [1, 0], [1, 1]]),
    ("takeoff.quantities.amount", "999"),
    ("takeoff.quantities.unit", "kg"),
    ("takeoff.drawing_session_id", "wrong"),
    ("session.source_sha256", "0" * 64),
    ("session.committed_item_ids", []),
])
def test_tampered_provenance_or_boq_does_not_link(tmp_path, field, value):
    app, project, kwargs, _ = _persisted(tmp_path)
    copy = deepcopy(project)
    try:
        if field.startswith("boq."):
            copy["boq"][0][field.removeprefix("boq.")] = value
        elif field.startswith("takeoff.params."):
            copy["takeoffs"][0]["params"][field.removeprefix("takeoff.params.")] = value
        elif field.startswith("takeoff.quantities."):
            copy["takeoffs"][0]["quantities"][0][field.removeprefix("takeoff.quantities.")] = value
        elif field.startswith("takeoff."):
            copy["takeoffs"][0][field.removeprefix("takeoff.")] = value
        elif field.startswith("session."):
            copy["drawing_sessions"][kwargs["session_id"]][field.removeprefix("session.")] = value
        with pytest.raises(ValueError):
            link_source_backed_2d_overlay_to_boq(copy, **kwargs)
        assert app.open_project("P") == project
    finally:
        app.store.close()


def test_reject_stale_project_version_and_session_revision(tmp_path):
    app, project, kwargs, _ = _persisted(tmp_path)
    try:
        for changed in ({"expected_project_version": kwargs["expected_project_version"] + 1},
                        {"expected_session_revision": kwargs["expected_session_revision"] - 1}):
            with pytest.raises(ValueError, match="نسخه"):
                link_source_backed_2d_overlay_to_boq(project, **(kwargs | changed))
    finally:
        app.store.close()


def test_reject_ambiguous_aggregate_or_duplicate_boq(tmp_path):
    app, project, kwargs, _ = _persisted(tmp_path)
    try:
        aggregated = deepcopy(project)
        aggregated["boq"][0]["source_ids"].append("drawing:another-session:TO-00001")
        with pytest.raises(ValueError, match="تجمیعی"):
            link_source_backed_2d_overlay_to_boq(aggregated, **kwargs)
        duplicate = deepcopy(project)
        duplicate["boq"].append(deepcopy(duplicate["boq"][0]))
        with pytest.raises(ValueError, match="یکتا"):
            link_source_backed_2d_overlay_to_boq(duplicate, **kwargs)
    finally:
        app.store.close()


def test_member_floor_mismatch_rejected_without_mutation(tmp_path):
    app, project, kwargs, _ = _persisted(tmp_path)
    wrong = deepcopy(project)
    wrong["members"][0]["floor_id"] = "DIFFERENT"
    try:
        with pytest.raises(ValueError, match="طبقه"):
            link_source_backed_2d_overlay_to_boq(wrong, **kwargs)
        assert app.open_project("P") == project
    finally:
        app.store.close()
