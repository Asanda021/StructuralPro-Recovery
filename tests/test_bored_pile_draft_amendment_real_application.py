"""Production StructuralProApp/ProjectStore tests for documented pile draft corrections.

These tests must run in the complete repository. They do not grant pile BOQ
approval, migrate legacy records, or certify an engineering design.
"""
from copy import deepcopy
import pytest

from app.bored_pile_draft_controller import PileDraftController
from core.platform.application import StructuralProApp
from test_bored_pile_real_application_controller import _setup, _document, _ownership


def _changed_document(document):
    revised = deepcopy(document)
    pile = revised["piles"][0]
    pile["concrete"]["mix_ref"] = "synthetic-mix-revision-2"
    pile["concrete"]["approved_by"] = "IndependentConcreteReviser"
    return revised


def test_real_projectstore_amendment_journal_retains_pile_and_no_finance(tmp_path):
    app, controller, data = _setup(tmp_path)
    controller.attach_ownership(
        _document(tmp_path / "owner.json", _ownership(data)),
        reference="Synthetic original ownership",
    )
    controller.save()
    assert controller.revision == 1
    original = deepcopy(controller.data)
    revised = _changed_document(data)
    updated = controller.amend_input(
        _document(tmp_path / "revised.json", revised),
        reason="اصلاح مستند نوع بتن شمع",
    )
    assert controller.revision == 2
    assert not controller.dirty
    assert updated["pile_detail"]["input"] == revised
    assert updated["pile_detail"]["ownership_document"]["path"] == ""
    assert updated["pile_detail"]["joint_document"]["path"] == ""
    project = app.open_project("P")
    events = [event for event in project["structural_member_history"]
              if "اصلاحیه پیش‌نویس شمع:" in event["reason"]]
    assert len(events) == 1
    assert "اصلاح مستند نوع بتن شمع" in events[0]["reason"]
    assert events[0]["previous"]["data"] == original
    assert project["takeoffs"] == project["boq"] == []
    report = controller.preview()
    assert report["engineering_ready"] is True
    assert report["commit_allowed"] is False
    assert report["ready"] is False and report["rows"] == []
    with pytest.raises(ValueError):
        app.commit_structural_member("P", "bored_pile", "FND", "PG1",
                                     expected_revision=2)
    app.store.close()


def test_real_projectstore_two_connections_reject_stale_amendment(tmp_path):
    app, controller, data = _setup(tmp_path)
    controller.save()
    second_service = StructuralProApp(tmp_path / "db")
    second = PileDraftController(second_service, "P")
    second.load("FND", "PG1")
    controller.set_preflight(reviewer="ReviewerUpdated",
                             ownership_reference="Revised audit")
    controller.save()
    assert controller.revision == 2
    with pytest.raises(RuntimeError):
        second.amend_input(
            _document(tmp_path / "revised.json", _changed_document(data)),
            reason="اصلاح روی نسخه منقضی‌شده",
        )
    assert second.revision == 1 and not second.dirty
    current = PileDraftController(second_service, "P")
    current.load("FND", "PG1")
    assert current.revision == 2
    assert current.data["pile_detail"]["input"] == data
    assert second_service.open_project("P")["boq"] == []
    second_service.store.close()
    app.store.close()


def test_real_projectstore_tampered_prior_evidence_blocks_revision(tmp_path):
    app, controller, data = _setup(tmp_path)
    controller.save()
    original = controller.data["pile_detail"]["input_document"]["path"]
    with open(original, "ab") as stream:
        stream.write(b"\n")
    with pytest.raises(ValueError, match="مدرک قبلی"):
        controller.amend_input(
            _document(tmp_path / "revised.json", _changed_document(data)),
            reason="اصلاح مستند",
        )
    assert controller.revision == 1 and not controller.dirty
    assert len(app.open_project("P").get("structural_member_history", [])) == 0
    assert app.open_project("P")["takeoffs"] == app.open_project("P")["boq"] == []
    app.store.close()
