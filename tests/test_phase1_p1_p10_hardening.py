import math
import pytest

from core.technical_office import (
    SiteMaterial, TechnicalOfficeEngine, Deduction,
)
from core.reports import ReportRequest, ReportService
from core.collaboration import (
    CollaborationWorkspace, Role, User, CollaborationObject,
    Assignment, Comment, Review, Notification,
)
from core.ai import AIOrchestrator


def test_phase1_technical_office_fails_closed_on_material_overconsumption():
    with pytest.raises(ValueError, match="consumed_quantity"):
        SiteMaterial("S1", "C", "cement", 10, 11, "kg")


def test_phase1_technical_office_payment_remains_auditable():
    result = TechnicalOfficeEngine.payment_certificate(
        1000, [Deduction("D1", "insurance", 50)],
        advance_recovery=100, adjustment=200, retention_rate=10,
    )
    assert result["gross_amount"] == 1000
    assert result["adjustment"] == 200
    assert result["retention"] == pytest.approx(120)
    assert result["net_amount"] == pytest.approx(930)


def test_phase1_reporting_rejects_nonfinite_amount():
    with pytest.raises(ValueError, match="finite"):
        ReportService.build(
            ReportRequest("boq", "Phase 1"),
            [{"description": "bad", "total": math.nan}],
        )


def test_phase1_collaboration_rejects_duplicate_identity_and_missing_review_permission():
    w = CollaborationWorkspace()
    w.add_role(Role("viewer", frozenset()))
    w.add_role(Role("engineer", frozenset({"edit", "review"})))
    w.add_user(User("U1", "Engineer", "engineer"))
    w.add_user(User("U2", "Viewer", "viewer"))
    w.create_object("O1", {"quantity": 10})

    w.assign(Assignment("A1", "U1", "O1"))
    with pytest.raises(ValueError, match="duplicate assignment_id"):
        w.assign(Assignment("A1", "U1", "O1"))

    w.comment(Comment("C1", "U1", "O1", "checked"))
    with pytest.raises(ValueError, match="duplicate comment_id"):
        w.comment(Comment("C1", "U1", "O1", "checked again"))

    w.review(Review("R1", "O1", "U1", "approved"))
    with pytest.raises(PermissionError, match="review permission"):
        w.review(Review("R2", "O1", "U2", "approved"))


def test_phase1_ai_rejects_nonfinite_context_totals():
    ai = AIOrchestrator()
    with pytest.raises(ValueError, match="finite"):
        ai.query("جمع مبلغ", {"rows": [{"total": float("inf")}]})
