import json
from pathlib import Path

import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_bridge import session_to_boq_rows, validate_session_payload
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp


FIXTURE = Path(__file__).parent / "fixtures" / "golden_drawing_takeoff_v1.json"


def _golden_session():
    cases = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]
    session = DrawingTakeoffSession("golden://five-storey-building/drawing-A101.pdf")
    items = {}
    for case in cases:
        page = case["page"]
        session.set_page(page)
        calibration = case.get("calibration")
        if calibration:
            session.calibrate(page, calibration["reference_pixels"], calibration["reference_meters"])
        if case["kind"] == "length":
            item = session.add_length(
                [Point(float(x), float(y)) for x, y in case["geometry"]],
                page=page, label=case["id"], takeoff_code=case["id"].upper(),
            )
        elif case["kind"] == "area":
            item = session.add_area(
                [Point(float(x), float(y)) for x, y in case["geometry"]],
                page=page, label=case["id"], takeoff_code=case["id"].upper(),
            )
        else:
            item = session.add_count(case["count"], page=page, label=case["id"],
                                     takeoff_code=case["id"].upper())
        items[case["id"]] = item
    return cases, session, items


def test_golden_drawing_dataset_matches_expected_quantities():
    cases, session, items = _golden_session()
    assert session.validate()["valid"] is True
    for case in cases:
        item = items[case["id"]]
        assert item.unit == case["unit"]
        assert item.quantity == pytest.approx(case["expected_quantity"], abs=case["tolerance"])
        assert item.page == case["page"]


def test_drawing_session_persists_and_selected_items_enter_boq_once(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("ساختمان مرجع پنج طبقه", "golden-project")
    _, session, items = _golden_session()
    saved = app.save_drawing_takeoff_session("golden-project", session)
    sid, revision = saved["session_id"], saved["revision"]
    assert revision == 1
    restored = app.load_drawing_takeoff_session("golden-project", sid)
    assert restored["session"]["drawing_source"] == session.drawing_source
    assert len(restored["session"]["items"]) == len(items)

    chosen = [items["line-10m"].id, items["rectangle-50m2"].id]
    committed = app.commit_drawing_takeoff_to_boq(
        "golden-project", sid, chosen, expected_session_revision=revision
    )
    assert committed["takeoffs_added"] and len(committed["takeoffs_added"]) == 2
    assert committed["revision"] == 2
    project = app.open_project("golden-project")
    assert len(project["takeoffs"]) == 2
    assert len(project["boq"]) == 2
    amounts = {row["source_id"]: row["quantities"][0]["amount"] for row in project["takeoffs"]}
    assert amounts[f"drawing:{sid}:{items['line-10m'].id}"] == pytest.approx(10.0)
    assert amounts[f"drawing:{sid}:{items['rectangle-50m2'].id}"] == pytest.approx(50.0)
    with pytest.raises(ValueError, match="انتقال تکراری رد شد"):
        app.commit_drawing_takeoff_to_boq(
            "golden-project", sid, chosen, expected_session_revision=2
        )
    assert len(app.open_project("golden-project")["takeoffs"]) == 2


def test_drawing_session_revision_conflict_and_unknown_selection_fail_closed(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("تعارض نسخه", "revision-project")
    _, session, items = _golden_session()
    saved = app.save_drawing_takeoff_session("revision-project", session)
    sid = saved["session_id"]
    with pytest.raises(RuntimeError, match="تعارض نسخه"):
        app.save_drawing_takeoff_session(
            "revision-project", session, session_id=sid, expected_revision=99
        )
    with pytest.raises(ValueError, match="شناسه متره"):
        app.commit_drawing_takeoff_to_boq(
            "revision-project", sid, ["TO-UNKNOWN"], expected_session_revision=1
        )
    assert app.open_project("revision-project")["takeoffs"] == []


def test_bridge_requires_explicit_selection_and_valid_session():
    _, session, items = _golden_session()
    payload = session.to_dict()
    assert validate_session_payload(payload)["valid"] is True
    with pytest.raises(ValueError, match="صریحاً انتخاب"):
        session_to_boq_rows(payload, session_id="session-1", selected_item_ids=[])
    rows = session_to_boq_rows(payload, session_id="session-1",
                                selected_item_ids=[items["count-12"].id])
    assert len(rows) == 1
    assert rows[0]["quantity"] == pytest.approx(12.0)
    assert rows[0]["unit"] == "عدد"


def test_saving_new_session_edits_preserves_commit_ledger(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("دفتر ثبت متره", "commit-ledger-project")
    session = DrawingTakeoffSession("golden://project/A103.pdf")
    session.calibrate(1, 100, 10)
    first = session.add_length([Point(0, 0), Point(100, 0)], page=1,
                               label="طول اول", takeoff_code="LINE-1")
    saved = app.save_drawing_takeoff_session("commit-ledger-project", session)
    committed = app.commit_drawing_takeoff_to_boq(
        "commit-ledger-project", saved["session_id"], [first.id],
        expected_session_revision=saved["revision"],
    )
    session.add_length([Point(0, 0), Point(50, 0)], page=1,
                       label="طول دوم", takeoff_code="LINE-2")
    resaved = app.save_drawing_takeoff_session(
        "commit-ledger-project", session, session_id=saved["session_id"],
        expected_revision=committed["revision"],
    )
    assert resaved["revision"] == committed["revision"] + 1
    assert first.id in resaved["committed_item_ids"]
    with pytest.raises(ValueError, match="قبلاً"):
        app.commit_drawing_takeoff_to_boq(
            "commit-ledger-project", saved["session_id"], [first.id],
            expected_session_revision=resaved["revision"],
        )
    assert len(app.open_project("commit-ledger-project")["takeoffs"]) == 1
