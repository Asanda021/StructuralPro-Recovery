import copy

import pytest

from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.platform.application import StructuralProApp


def _proposal(session_id, revision, session, item, *, meters_per_pixel=0.1):
    return {
        "drawing_id": session_id,
        "revision_id": str(revision),
        "candidates": [{
            "source_id": "page-1:line-1",
            "session_item_id": item.id,
            "page": 1,
            "kind": "length",
            "unit": "m",
            "quantity": item.quantity,
            "confidence": 0.98,
            "label": "طول دیوار محور A",
            "formula": "طول هندسی × مقیاس صفحه",
            "evidence": {
                "source_ref": item.source_ref,
                "scale_ref": "calibration:page-1:rev-1",
                "meters_per_pixel": meters_per_pixel,
            },
        }],
    }


def test_ai_takeoff_requires_human_confirmation_and_saved_drawing_evidence(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه متره هوشمند", "ai-project")
    session = DrawingTakeoffSession("golden://project/A101.pdf")
    session.calibrate(1, 100, 10)
    session.add_length([Point(0, 0), Point(100, 0)], page=1, label="خط مرجع")
    saved = app.save_drawing_takeoff_session("ai-project", session)
    proposal = _proposal(saved["session_id"], saved["revision"], session, session.items[0])

    with pytest.raises(PermissionError, match="تأیید صریح"):
        app.commit_ai_takeoff_proposal("ai-project", proposal, user_confirmed=False)
    assert app.open_project("ai-project")["takeoffs"] == []

    committed = app.commit_ai_takeoff_proposal("ai-project", proposal, user_confirmed=True)
    assert committed["approved"] is True
    assert len(committed["takeoffs_added"]) == 1
    project = app.open_project("ai-project")
    assert len(project["takeoffs"]) == 1
    assert len(project["boq"]) == 1
    assert project["takeoffs"][0]["ai_generated"] is True
    refreshed = app.load_drawing_takeoff_session("ai-project", saved["session_id"])
    with pytest.raises(ValueError, match="هوشمند"):
        app.commit_drawing_takeoff_to_boq(
            "ai-project", saved["session_id"], [session.items[0].id],
            expected_session_revision=refreshed["revision"],
        )
    assert len(app.open_project("ai-project")["takeoffs"]) == 1


def test_ai_takeoff_rejects_stale_revision_wrong_scale_and_duplicate_sources(tmp_path):
    app = StructuralProApp(tmp_path)
    app.create_project("پروژه کنترل شواهد", "ai-evidence-project")
    session = DrawingTakeoffSession("golden://project/A102.pdf")
    session.calibrate(1, 100, 10)
    session.add_length([Point(0, 0), Point(100, 0)], page=1, label="خط مرجع")
    saved = app.save_drawing_takeoff_session("ai-evidence-project", session)
    sid, revision = saved["session_id"], saved["revision"]

    wrong_scale = _proposal(sid, revision, session, session.items[0], meters_per_pixel=0.5)
    with pytest.raises(ValueError, match="مطابقت ندارد"):
        app.commit_ai_takeoff_proposal("ai-evidence-project", wrong_scale, user_confirmed=True)
    assert app.open_project("ai-evidence-project")["takeoffs"] == []

    wrong_quantity = _proposal(sid, revision, session, session.items[0])
    wrong_quantity["candidates"][0]["quantity"] += 1.0
    with pytest.raises(ValueError, match="مقدار پیشنهاد"):
        app.commit_ai_takeoff_proposal("ai-evidence-project", wrong_quantity, user_confirmed=True)
    assert app.open_project("ai-evidence-project")["takeoffs"] == []

    stale = _proposal(sid, revision + 1, session, session.items[0])
    with pytest.raises(RuntimeError, match="نسخه"):
        app.commit_ai_takeoff_proposal("ai-evidence-project", stale, user_confirmed=True)
    assert app.open_project("ai-evidence-project")["takeoffs"] == []

    proposal = _proposal(sid, revision, session, session.items[0])
    app.commit_ai_takeoff_proposal("ai-evidence-project", proposal, user_confirmed=True)
    with pytest.raises(ValueError, match="دوباره‌شماری"):
        app.commit_ai_takeoff_proposal("ai-evidence-project", copy.deepcopy(proposal), user_confirmed=True)
    assert len(app.open_project("ai-evidence-project")["takeoffs"]) == 1
