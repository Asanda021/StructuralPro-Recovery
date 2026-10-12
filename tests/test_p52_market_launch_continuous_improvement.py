import pytest
from core.market.continuous_improvement_v2 import (ContinuousImprovementError, FeedbackItem, ImprovementCycle, ImprovementProposal, ReleaseRecord, UserSignal, build_improvement_backlog, evaluate_cycle, lifecycle_fingerprint)

def feedback(fid="f1", disposition="accepted"): return FeedbackItem(fid, "reviewer", "2026-10-04", "Improve takeoff review", disposition)
def proposal(pid="p1", status="approved", ids=("f1",)): return ImprovementProposal(pid, "ux", ids, "Feedback identifies review friction", status=status)
def cycle(**kwargs):
    base = dict(current_release=ReleaseRecord("2.0.0", "release-ci", "2026-10-04"), signals=(UserSignal("feedback", "beta", "2026-10-04", "review signal"),), feedback=(feedback(),), proposals=(proposal(),), next_release_version="2.0.1")
    base.update(kwargs); return ImprovementCycle(**base)

def test_complete_cycle_is_go(): assert evaluate_cycle(cycle()) == "go"
def test_missing_feedback_needs_evidence(): assert evaluate_cycle(cycle(feedback=(), proposals=())) == "needs_evidence"
def test_unapproved_proposal_needs_evidence(): assert evaluate_cycle(cycle(proposals=(proposal(status="proposed"),))) == "needs_evidence"
def test_rejected_proposal_is_no_go(): assert evaluate_cycle(cycle(proposals=(proposal(status="rejected"),))) == "no_go"
def test_unreleased_current_version_fails_closed(): assert evaluate_cycle(cycle(current_release=ReleaseRecord("2.0.0", "release-ci", "2026-10-04", "planned"))) == "no_go"
def test_missing_feedback_reference_fails_closed():
    with pytest.raises(ContinuousImprovementError): build_improvement_backlog((feedback("f1"),), (proposal(ids=("missing",)),))
def test_fingerprint_is_deterministic():
    assert lifecycle_fingerprint(cycle()) == lifecycle_fingerprint(cycle()); assert len(lifecycle_fingerprint(cycle())) == 64
def test_invalid_signal_fails_closed():
    with pytest.raises(ContinuousImprovementError): lifecycle_fingerprint(cycle(signals=(UserSignal("feedback", "", "2026-10-04", "x"),)))