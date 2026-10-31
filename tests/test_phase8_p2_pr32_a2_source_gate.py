"""P8 P2 source-backed A2 numeric-answer regression, PR32 safety delta.

Tests operate on a real persisted SQLite BOQ, then supply isolated damaged
read snapshots to the existing readonly guide. They never put invalid rows
into the canonical store or create financial authority.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from core.ai.contextual_takeoff import ContextualTakeoffGuide, GuidedContext
from core.platform.application import StructuralProApp


def project_and_context(tmp_path):
    app = StructuralProApp(tmp_path / "db")
    app.create_project("داده مصنوعی A2", "P")
    app.add_project_floor("P", "اول", level="F1")
    app.add_project_member("P", "W1", "F1", "wall")
    app.add_takeoff(
        "P", "building", "wall",
        source_id="synthetic:manual:F1:W1",
        count=1, length=2, height=3, openings=0,
        description="داده مصنوعی دارای منبع",
    )
    ctx = GuidedContext("P", "F1", "W1", None, None, None, "block_wall")
    return app, ctx


def test_a2_real_active_boq_reads_exact_amount_with_provenance_and_no_write(tmp_path):
    app, ctx = project_and_context(tmp_path)
    try:
        before = deepcopy(app.open_project("P"))
        digest = app.store.current_digest("P")
        answer = ContextualTakeoffGuide(app).explain_persisted_boq(ctx, index=0)
        assert answer["read_only"] is True
        assert answer["source"] == "persisted_project_boq"
        assert answer["quantity"] == "6.0" or answer["quantity"] == "6"
        assert answer["unit"] == "m2"
        assert answer["source_ids"] == ("synthetic:manual:F1:W1",)
        assert answer["cas_digest"] == digest
        assert app.store.current_digest("P") == digest
        assert app.open_project("P") == before
    finally:
        app.store.close()


@pytest.mark.parametrize("fault", [
    "missing_sources", "empty_sources", "blank_source",
    "nonlist_sources", "duplicate_sources", "nonstring_source",
    "inactive", "superseded", "negative", "nan", "inf",
    "blank_unit", "nonstring_unit",
])
def test_a2_damaged_or_inactive_boq_row_never_becomes_numeric_answer(
    tmp_path, monkeypatch, fault,
):
    app, ctx = project_and_context(tmp_path)
    try:
        original = deepcopy(app.open_project("P"))
        digest = app.store.current_digest("P")
        damaged = deepcopy(original)
        row = damaged["boq"][0]
        if fault == "missing_sources":
            row.pop("source_ids", None)
        elif fault == "empty_sources":
            row["source_ids"] = []
        elif fault == "blank_source":
            row["source_ids"] = [" "]
        elif fault == "nonlist_sources":
            row["source_ids"] = "synthetic:manual:F1:W1"
        elif fault == "duplicate_sources":
            row["source_ids"] = ["synthetic:manual:F1:W1"] * 2
        elif fault == "nonstring_source":
            row["source_ids"] = [12]
        elif fault in ("inactive", "superseded"):
            row["status"] = fault
        elif fault == "negative":
            row["quantity"] = -1
        elif fault == "nan":
            row["quantity"] = float("nan")
        elif fault == "inf":
            row["quantity"] = float("inf")
        elif fault == "blank_unit":
            row["unit"] = " "
        elif fault == "nonstring_unit":
            row["unit"] = 12
        monkeypatch.setattr(app, "open_project", lambda project_id: deepcopy(damaged))
        guide = ContextualTakeoffGuide(app)
        with pytest.raises(ValueError):
            guide.explain_persisted_boq(ctx, index=0)
        assert app.store.current_digest("P") == digest
        # Only the read boundary is changed in-memory; persisted data is clean.
        assert app.store.get("P") == original
    finally:
        app.store.close()
