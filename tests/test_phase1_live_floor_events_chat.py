"""Phase-one floor/member identity and nonfinancial live-event regressions."""
import json
import pytest
from core.projects.project_model import ProjectModel
from core.projects.user_workflow import LiveTakeoffTracker, evaluate_workflow, stage_status


def sample():
    p = ProjectModel("P1", "ساختمان")
    p.add_floor("همکف", level="G")
    p.add_floor("اول", level=1)
    p.add_member("C1", 1, "ستون", source_id="drawing:V1")
    return p


@pytest.mark.parametrize("count", [1, 5, 20, 50, 100])
def test_dynamic_floors_and_members(count):
    p = ProjectModel("P", "ساختمان")
    for i in range(1, count + 1):
        p.add_floor(f"طبقه {i}")
        p.add_member(f"C{i}", i, "ستون")
    assert len(p.floors) == len(p.members) == count
    assert p.validate() == []
    assert ProjectModel(**json.loads(json.dumps(p.to_dict(), ensure_ascii=False))).validate() == []


def test_duplicate_floor_unicode_and_atomicity():
    p = ProjectModel("P", "سازه")
    p.add_floor("اول", level="۱")
    with pytest.raises(ValueError, match="تکراری"):
        p.add_floor("دوباره", level=1)
    p.add_floor("دوم", level="kي١")
    with pytest.raises(ValueError, match="تکراری"):
        p.add_floor("دوباره", level="Kی1")
    assert len(p.floors) == 2


def test_auto_floor_allocates_unused_id():
    p = ProjectModel("P", "سازه")
    p.add_floor("اول", level="1")
    p.add_floor("سوم", level="3")
    assert p.add_floor("دوم")["id"] == "2"


@pytest.mark.parametrize("invalid", ["", " ", True])
def test_floor_blank_id_is_rejected(invalid):
    p = ProjectModel("P", "سازه")
    with pytest.raises(ValueError):
        p.add_floor("طبقه", level=invalid)
    assert p.floors == []


def test_member_must_have_real_parent_and_unique_project_id():
    p = ProjectModel("P", "سازه")
    p.add_floor("اول", level=1)
    p.add_member("Kي١", 1, "ستون")
    for ident, floor, kind in [("Kی1", 1, "تیر"), ("C2", 9, "ستون"), ("C3", 1, "")]:
        with pytest.raises(ValueError):
            p.add_member(ident, floor, kind)
    assert p.validate() == []
    assert len(p.members) == 1


def test_corrupt_model_detected_without_guessing():
    p = sample()
    p.floors.append({"id": "۱", "name": "تکراری"})
    p.members.append({"id": "c1", "floor_id": 9, "kind": "ستون"})
    errors = p.validate()
    assert any("طبقه تکراری" in item for item in errors)
    assert any("عضو تکراری" in item for item in errors)
    assert any("طبقه عضو موجود نیست" in item for item in errors)
    with pytest.raises(ValueError):
        LiveTakeoffTracker(p)


def test_old_json_without_members_is_backward_compatible():
    p = ProjectModel(**{"project_id": "P", "name": "قدیمی", "floors": [{"id": "1", "name": "اول"}]})
    assert p.members == []
    assert p.validate() == []


def test_selection_events_and_copy_isolation():
    t = LiveTakeoffTracker(sample())
    published = []
    unsubscribe = t.subscribe(published.append)
    assert t.select_floor(1)["type"] == "floor_selected"
    event = t.select_member("۱", "c1")
    assert (event["floor_id"], event["member_id"], event["sequence"]) == ("1", "C1", 2)
    snap = t.snapshot()
    snap["last_event"]["member_id"] = "tampered"
    assert t.snapshot()["last_event"]["member_id"] == "C1"
    unsubscribe()
    t.select_floor("G")
    assert len(published) == 2


def test_wrong_floor_and_unknown_member_produce_no_event():
    t = LiveTakeoffTracker(sample())
    with pytest.raises(ValueError, match="متعلق"):
        t.select_member("G", "C1")
    with pytest.raises(ValueError, match="ناشناخته"):
        t.select_member("1", "UNKNOWN")
    assert t.snapshot()["sequence"] == 0


def reviewed_tracker(verifier=None):
    p = sample()
    t = LiveTakeoffTracker(p, boq_receipt_verifier=verifier)
    args = dict(floor_id="1", member_id="C1", task_id="CONCRETE")
    t.emit("takeoff_started", **args)
    t.emit("quantity_calculated", **args, source_id="source:1", revision="R1")
    t.emit("review_approved", **args, source_id="source:1", revision="R1")
    return p, t, args


def test_state_machine_and_source_revision_guard():
    t = LiveTakeoffTracker(sample())
    args = dict(floor_id=1, member_id="C1", task_id="CONCRETE")
    with pytest.raises(ValueError, match="ترتیب"):
        t.emit("review_approved", **args)
    t.emit("takeoff_started", **args)
    with pytest.raises(ValueError, match="مدرک"):
        t.emit("quantity_calculated", **args)
    t.emit("input_required", **args)
    t.emit("takeoff_started", **args)
    t.emit("quantity_calculated", **args, source_id="source:1", revision="R1")
    with pytest.raises(ValueError, match="مدرک"):
        t.emit("review_approved", **args, source_id="source:2", revision="R1")
    assert t.emit("review_approved", **args, source_id="source:1", revision="R1")["status"] == "reviewed"
    with pytest.raises(ValueError, match="ترتیب"):
        t.emit("takeoff_started", **args)
    assert t.snapshot()["sequence"] == 5


def test_validation_error_and_retry_never_write_boq():
    p = sample()
    t = LiveTakeoffTracker(p)
    args = dict(floor_id="1", member_id="C1", task_id="REBAR")
    t.emit("takeoff_started", **args)
    assert t.emit("validation_failed", **args)["status"] == "error"
    t.emit("takeoff_started", **args)
    assert p.boq == []


def test_forged_boq_event_and_unverified_receipt_blocked():
    p, t, args = reviewed_tracker()
    receipt = dict(project_id="P1", floor_id="1", member_id="C1", task_id="CONCRETE",
                   source_id="source:1", revision="R1", boq_row_id="B001")
    with pytest.raises(ValueError, match="احراز"):
        t.confirm_boq_transfer(**args, receipt=receipt)
    with pytest.raises(ValueError, match="پشتیبانی"):
        t.emit("boq_transfer_confirmed", **args)
    assert p.boq == []
    assert t.snapshot()["tasks"]["c1:concrete"]["status"] == "reviewed"


def test_verified_external_boq_receipt_only_updates_ui():
    p, t, args = reviewed_tracker(verifier=lambda receipt: receipt["boq_row_id"] == "B001")
    receipt = dict(project_id="P1", floor_id="1", member_id="C1", task_id="CONCRETE",
                   source_id="source:1", revision="R1", boq_row_id="B001")
    with pytest.raises(ValueError, match="مطابقت"):
        t.confirm_boq_transfer(**args, receipt=dict(receipt, revision="R2"))
    assert t.confirm_boq_transfer(**args, receipt=receipt)["status"] == "boq_transferred"
    assert p.boq == []
    with pytest.raises(ValueError, match="تأیید"):
        t.confirm_boq_transfer(**args, receipt=receipt)


def test_existing_stage_workflow_preserved():
    p = {"id": "P1", "name": "ساختمان", "takeoffs": [], "boq": []}
    assert evaluate_workflow(p)["current_stage"] == "takeoff"
    assert stage_status(p, "boq") == "blocked"
