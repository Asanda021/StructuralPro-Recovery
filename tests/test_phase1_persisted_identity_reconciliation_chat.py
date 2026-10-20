"""Phase-one persisted identity audit through actual SQLite and application services.

These cases assert *navigation identity* only, never engineering correctness or
approval/BOQ proof. Tests use synthetic explicit identifiers, not real projects.
"""
import pytest

from core.platform.application import StructuralProApp
from core.projects.user_workflow import LiveTakeoffTracker


def _project(app, *, members=("C1", "C2", "C3")):
    app.create_project("آزمون هویت", "P-IDENTITY")
    data = app.open_project("P-IDENTITY")
    data["floors"] = [{"id": "۱", "name": "طبقه یک"}]
    data["members"] = [{"id": m, "floor_id": "1", "kind": "ستون" if m == "C1" else "سیستم"}
                       for m in members]
    app.store.save("P-IDENTITY", data,
                   expected_digest=app.store.current_digest("P-IDENTITY"))
    return app.open_project("P-IDENTITY")


def _row(source, member, *, params=None, system="1", item="column", revision=1):
    return {"source_id": source, "member_code": member, "system": system,
            "item": item, "params": params if params is not None else {},
            "revision": revision}


def _save(app, data):
    app.store.save("P-IDENTITY", data,
                   expected_digest=app.store.current_digest("P-IDENTITY"))


def test_sqlite_real_services_reconcile_four_persisted_sources(tmp_path):
    app = StructuralProApp(tmp_path / "database")
    p = _project(app)
    p["reviewed_structural_members"] = {
        "column:1:C1": {"status": "committed", "revision": 2,
            "data": {"floor_id": "1", "member_id": "C1",
                     "source": {"source_id": "structural-evidence"}},
            "committed_source_ids": ["structural-qty"]}}
    p["reviewed_aec_systems"] = {
        "roof:1:C2": {"status": "committed", "revision": 3,
            "data": {"floor_id": "۱", "system_id": "C2",
                     "source": {"source_id": "roof-evidence"}},
            "source_ids": ["aec-qty"]}}
    p["manual_formula_register"] = {
        "MF-C3": {"status": "committed", "revision": 4,
                   "data": {"floor": "1", "member": "C3",
                            "source_id": "formula-qty"}}}
    p["takeoffs"] = [
        _row("manual-qty", "C1", params={"member_code": "C1"}),
        _row("structural-qty", "C1"),
        _row("aec-qty", "C2", item="roof"),
        _row("formula-qty", "C3", item="formula")]
    _save(app, p)
    digest = app.store.current_digest("P-IDENTITY")
    tracker = app.live_takeoff_tracker("P-IDENTITY")
    audit = app.takeoff_identity_snapshot("P-IDENTITY")
    assert audit["coverage"] == {"total": 7, "linked": 7, "blocked": 0}
    assert {x["registry"] for x in audit["records"]} == {
        "takeoffs", "reviewed_structural_members", "reviewed_aec_systems",
        "manual_formula_register"}
    assert tracker.select_persisted_record("takeoffs", "2")["member_id"] == "C2"
    assert tracker.select_persisted_record("reviewed_structural_members", "column:1:C1")["member_id"] == "C1"
    assert tracker.snapshot()["sequence"] == 2
    assert app.store.current_digest("P-IDENTITY") == digest
    app.store.close()


def test_synthetic_unscoped_legacy_takeoff_does_not_guess_member(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("column",))
    p["takeoffs"] = [_row("legacy-qty", "column", params={})]
    _save(app, p)
    tracker = app.live_takeoff_tracker("P-IDENTITY")
    audit = tracker.persisted_identity_snapshot()
    assert audit["blocked"] == 1
    with pytest.raises(ValueError, match="قابل انتخاب نیست"):
        tracker.select_persisted_record("takeoffs", "0")
    assert tracker.snapshot()["sequence"] == 0
    app.store.close()


def test_duplicate_takeoff_source_is_blocked_not_backfilled(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1",))
    p["takeoffs"] = [_row("SAME", "C1", params={"member_code": "C1"}),
                     _row("SAME", "C1", params={"member_code": "C1"})]
    _save(app, p)
    digest = app.store.current_digest("P-IDENTITY")
    audit = app.takeoff_identity_snapshot("P-IDENTITY")
    assert audit["coverage"] == {"total": 2, "linked": 0, "blocked": 2}
    assert {x["reason"] for x in audit["records"]} == {"duplicate_takeoff_source"}
    assert app.store.current_digest("P-IDENTITY") == digest
    app.store.close()


@pytest.mark.parametrize("system,member,params,expected", [
    ("G", "C1", {"member_code": "C1"}, "unknown_floor"),
    ("1", "UNKNOWN", {"member_code": "UNKNOWN"}, "unknown_member"),
    ("1", "C1", {"member_code": "C2"}, "explicit_member_conflict"),
])
def test_invalid_manual_links_fail_closed(tmp_path, system, member, params, expected):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1", "C2"))
    p["takeoffs"] = [_row("X", member, params=params, system=system)]
    _save(app, p)
    row = app.takeoff_identity_snapshot("P-IDENTITY")["records"][0]
    assert row["status"] == "blocked"
    assert row["reason"] == expected
    app.store.close()


def test_committed_register_identity_mismatch_blocks_both_records(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1", "C2"))
    p["reviewed_structural_members"] = {
        "column:1:C1": {"status": "committed", "revision": 2,
            "data": {"floor_id": "1", "member_id": "C1",
                     "source": {"source_id": "evidence"}},
            "committed_source_ids": ["S"]}}
    p["takeoffs"] = [_row("S", "C2")]
    _save(app, p)
    audit = app.takeoff_identity_snapshot("P-IDENTITY")
    assert audit["coverage"] == {"total": 2, "linked": 0, "blocked": 2}
    app.store.close()


def test_sqlite_version_change_invalidates_loaded_selection(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1",))
    p["takeoffs"] = [_row("S", "C1", params={"member_code": "C1"})]
    _save(app, p)
    tracker = app.live_takeoff_tracker("P-IDENTITY")
    p = app.open_project("P-IDENTITY")
    p["name"] = "نسخه تازه"
    _save(app, p)
    with pytest.raises(RuntimeError, match="تغییر"):
        tracker.select_persisted_record("takeoffs", "0")
    assert tracker.snapshot()["sequence"] == 0
    assert app.live_takeoff_tracker("P-IDENTITY").select_persisted_record("takeoffs", "0")["member_id"] == "C1"
    app.store.close()


def test_existing_project_without_new_structure_does_not_infer_floors(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("قدیمی", "OLD")
    original = app.open_project("OLD")
    digest = app.store.current_digest("OLD")
    audit = app.takeoff_identity_snapshot("OLD")
    assert audit["coverage"] == {"total": 0, "linked": 0, "blocked": 0}
    assert app.store.current_digest("OLD") == digest
    assert app.open_project("OLD") == original
    app.store.close()


def test_invalid_registry_and_corrupt_project_are_rejected_without_write(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1",))
    p["reviewed_aec_systems"] = ["invalid"]
    _save(app, p)
    digest = app.store.current_digest("P-IDENTITY")
    with pytest.raises(ValueError, match="ساختار دفتر"):
        app.takeoff_identity_snapshot("P-IDENTITY")
    assert app.store.current_digest("P-IDENTITY") == digest
    app.store.close()


def test_identity_audit_cannot_emit_boq_transfer_or_fake_engine_events(tmp_path):
    app = StructuralProApp(tmp_path)
    p = _project(app, members=("C1",))
    p["takeoffs"] = [_row("S", "C1", params={"member_code": "C1"})]
    _save(app, p)
    tracker = app.live_takeoff_tracker("P-IDENTITY")
    assert tracker.select_persisted_record("takeoffs", "0")["type"] == "member_selected"
    with pytest.raises(ValueError):
        tracker.emit("review_approved", floor_id="1", member_id="C1", task_id="column")
    with pytest.raises(ValueError):
        tracker.emit("boq_transfer_confirmed", floor_id="1", member_id="C1", task_id="column")
    assert app.open_project("P-IDENTITY")["boq"] == []
    app.store.close()
