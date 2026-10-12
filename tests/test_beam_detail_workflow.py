"""Contract tests for beam detail, SQLite persistence and fail-closed BOQ handoff."""
import copy
import hashlib
import json
import sqlite3

import pytest

from core.takeoff.beam_detail import BeamDetailWorkflow, BAR_TYPES, empty_beam, preview_beam
from core.takeoff.engine import TakeoffEngine
from core.projects.store import ProjectStore


def _draft():
    d = empty_beam("L1", "B1")
    d["source"] = {"mode": "drawing", "source_id": "sheet-17#beam-B1",
                   "sha256": "a" * 64, "page": 2}
    d["geometry"] = {"length": 5, "width": .3, "depth": .5, "count": 1,
                     "deductions_m3": 0, "approved_by": "engineer", "source_ref": "B1/section"}
    d["formwork"] = {"net_area_m2": 6.5, "approved_by": "engineer", "source_ref": "B1/face-schedule"}
    return d


def _review_all(d):
    for name in BAR_TYPES:
        d["bars"][name] = {"status": "not_applicable", "approved_by": "engineer",
                           "reason": "طبق دیتایل وجود ندارد", "source_ref": "B1/rebar-schedule"}
    d["bars"]["longitudinal"] = {"status": "confirmed", "approved_by": "engineer",
                                  "source_ref": "B1/longitudinal", "count": 4,
                                  "cut_length_m": 5.5, "unit_weight_kg_m": 2.47}
    d["bars"]["stirrups"] = {"status": "confirmed", "approved_by": "engineer",
                              "source_ref": "B1/stirrups", "count": 34,
                              "cut_length_m": 1.3, "unit_weight_kg_m": .395}
    return d


def _workflow(tmp_path):
    db = tmp_path / "projects.db"
    store = ProjectStore(db)
    store.save("P1", {"id": "P1", "name": "آزمون", "takeoffs": [], "boq": []})
    return BeamDetailWorkflow(store, TakeoffEngine()), store, db


def test_original_statuses_block_final_total():
    result = preview_beam(_draft(), TakeoffEngine())
    assert not result["ready"]
    assert len([x for x in result["blockers"] if "هنوز" in x]) == 5
    assert len(result["rows"]) == 2  # approved concrete/formwork remain previews only
    assert result["preview_only"]


def test_five_rebar_types_are_distinct_not_implicit_zero():
    d = empty_beam("L1", "B1")
    assert d["bars"]["longitudinal"]["status"] == "needs_detail"
    assert d["bars"]["stirrups"]["status"] == "needs_detail"
    assert all(d["bars"][k]["status"] == "unreviewed" for k in ("side_bars", "crossties", "additional"))


def test_rebar_weight_uses_existing_engine_and_reviewed_cut_lengths():
    result = preview_beam(_review_all(_draft()), TakeoffEngine())
    assert result["ready"]
    assert len(result["rows"]) == 4
    assert next(x for x in result["rows"] if x["code"] == "beam")["quantity"] == pytest.approx(.75)
    assert next(x for x in result["rows"] if x["source_id"].endswith("longitudinal"))["quantity"] == pytest.approx(54.34)
    assert next(x for x in result["rows"] if x["source_id"].endswith("stirrups"))["quantity"] == pytest.approx(17.459)


def test_bogus_geometry_and_unapproved_zero_are_blocked():
    d = _review_all(_draft())
    d["geometry"]["length"] = float("nan")
    assert not preview_beam(d, TakeoffEngine())["ready"]
    d = _review_all(_draft())
    d["bars"]["crossties"] = {"status": "not_applicable", "reason": ""}
    assert not preview_beam(d, TakeoffEngine())["ready"]
    d = _review_all(_draft())
    del d["geometry"]["deductions_m3"]
    assert not preview_beam(d, TakeoffEngine())["ready"]


def test_draft_survives_sqlite_reopen_and_fails_closed(tmp_path):
    w, store, db = _workflow(tmp_path)
    first = w.save_draft("P1", _draft())
    assert first["revision"] == 1
    store.close()
    with sqlite3.connect(db) as sql:
        assert sql.execute("SELECT count(*) FROM projects").fetchone()[0] == 1
    store2 = ProjectStore(db)
    w2 = BeamDetailWorkflow(store2, TakeoffEngine())
    assert w2.get("P1", "L1", "B1")["data"]["bars"]["stirrups"]["status"] == "needs_detail"
    with pytest.raises(ValueError, match="متره ناقص"):
        w2.commit("P1", "L1", "B1", expected_revision=1)
    assert store2.get("P1")["boq"] == []
    store2.close()


def test_atomic_commit_no_duplicates_and_source_trace(tmp_path):
    w, store, db = _workflow(tmp_path)
    saved = w.save_draft("P1", _review_all(_draft()))
    assert w.commit("P1", "L1", "B1", expected_revision=saved["revision"])["takeoff_rows"] == 4
    p = store.get("P1")
    assert len(p["takeoffs"]) == 4 and len(p["boq"]) > 0
    assert all(x["source_id"].startswith("beam-detail:") for x in p["takeoffs"])
    with pytest.raises(ValueError, match="قبلاً"):
        w.commit("P1", "L1", "B1", expected_revision=saved["revision"])
    assert len(store.get("P1")["takeoffs"]) == 4
    store.close()


def test_revision_and_cross_beam_source_uniqueness(tmp_path):
    w, store, _ = _workflow(tmp_path)
    d = _draft()
    w.save_draft("P1", d)
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        w.save_draft("P1", d, expected_revision=0)
    d2 = _draft(); d2["beam_id"] = "B2"
    with pytest.raises(ValueError, match="منبع برداشت تیر تکراری"):
        w.save_draft("P1", d2)
    assert w.get("P1", "L1", "B2") is None
    store.close()


def test_variable_stirrup_zones_and_missing_segment_block():
    d = _review_all(_draft())
    d["bars"]["stirrups"]["segments"] = [
        {"count": 12, "cut_length_m": 1.3, "unit_weight_kg_m": .395, "source_ref": "B1/end-zone"},
        {"count": 17, "cut_length_m": 1.3, "unit_weight_kg_m": .395, "source_ref": "B1/mid-zone"},
    ]
    preview = preview_beam(d, TakeoffEngine())
    assert preview["ready"]
    assert next(x for x in preview["rows"] if x["source_id"].endswith("stirrups"))["quantity"] == pytest.approx(29*1.3*.395)
    del d["bars"]["stirrups"]["segments"][0]["source_ref"]
    assert not preview_beam(d, TakeoffEngine())["ready"]


def test_invalid_float_not_written_to_sqlite(tmp_path):
    w, store, db = _workflow(tmp_path)
    d = _draft()
    d["geometry"]["depth"] = float("inf")
    with pytest.raises(ValueError, match="غیرمتناهی"):
        w.save_draft("P1", d)
    assert store.get("P1").get("beam_detail_register") is None
    store.close()


def test_drawing_evidence_sha_mandatory_and_manual_mode_explicit():
    d = _review_all(_draft())
    d["source"]["sha256"] = "malformed"
    assert not preview_beam(d, TakeoffEngine())["ready"]
    d = _review_all(_draft())
    d["source"] = {"mode": "manual", "source_id": "manual:P1:L1:B1"}
    assert preview_beam(d, TakeoffEngine())["ready"]


def test_source_change_cannot_reuse_old_approvals(tmp_path):
    w, store, _ = _workflow(tmp_path)
    d = _review_all(_draft())
    saved = w.save_draft("P1", d)
    changed = copy.deepcopy(d)
    changed["source"]["sha256"] = "b" * 64
    with pytest.raises(ValueError, match="منبع نقشه تغییر کرده"):
        w.save_draft("P1", changed, expected_revision=saved["revision"])
    assert w.get("P1", "L1", "B1")["revision"] == 1
    store.close()


def test_floor_scope_and_no_cross_beam_reuse(tmp_path):
    w, store, _ = _workflow(tmp_path)
    d = _review_all(_draft())
    w.save_draft("P1", d)
    second = _review_all(_draft())
    second["floor_id"] = "L2"
    second["source"]["source_id"] = "sheet-17#beam-B1-floor-2"
    assert w.save_draft("P1", second)["revision"] == 1
    assert w.get("P1", "L1", "B1") is not None
    assert w.get("P1", "L2", "B1") is not None
    store.close()


def test_commit_stale_revision_changes_nothing(tmp_path):
    w, store, _ = _workflow(tmp_path)
    d = _review_all(_draft())
    w.save_draft("P1", d)
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        w.commit("P1", "L1", "B1", expected_revision=0)
    assert store.get("P1")["boq"] == []
    store.close()


def test_beam_identity_normalizes_persian_digits_and_letter_case(tmp_path):
    w, store, _ = _workflow(tmp_path)
    original = _draft()
    w.save_draft("P1", original)
    variant = _draft()
    variant["beam_id"] = "b۱"
    variant["source"]["source_id"] = "different-drawing-region"
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        w.save_draft("P1", variant, expected_revision=0)
    assert w.get("P1", "L1", "b۱")["data"]["beam_id"] == "B1"
    store.close()
