from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Iterable, Literal

SignalType = Literal["usage", "error", "performance", "support", "feedback"]
FeedbackDisposition = Literal["new", "triaged", "accepted", "rejected", "implemented"]
ImprovementType = Literal["bugfix", "ux", "accuracy", "performance", "feature", "documentation"]
ReleaseStatus = Literal["planned", "released", "rolled_back"]

class ContinuousImprovementError(ValueError):
    pass

@dataclass(frozen=True)
class ReleaseRecord:
    version: str
    source: str
    observed: str
    status: ReleaseStatus = "released"

@dataclass(frozen=True)
class UserSignal:
    signal_type: SignalType
    source: str
    observed: str
    summary: str
    project_id: str = ""

@dataclass(frozen=True)
class FeedbackItem:
    feedback_id: str
    source: str
    observed: str
    summary: str
    disposition: FeedbackDisposition = "new"

@dataclass(frozen=True)
class ImprovementProposal:
    proposal_id: str
    improvement_type: ImprovementType
    source_feedback_ids: tuple[str, ...]
    rationale: str
    owner: str = ""
    status: Literal["proposed", "approved", "implemented", "rejected"] = "proposed"

@dataclass(frozen=True)
class ImprovementCycle:
    current_release: ReleaseRecord
    signals: tuple[UserSignal, ...]
    feedback: tuple[FeedbackItem, ...]
    proposals: tuple[ImprovementProposal, ...]
    next_release_version: str = ""

def _require(value: str, field: str) -> None:
    if not value or not value.strip():
        raise ContinuousImprovementError(f"{field} is required")

def validate_release(release: ReleaseRecord) -> None:
    for value, field in ((release.version, "release.version"), (release.source, "release.source"), (release.observed, "release.observed")):
        _require(value, field)

def validate_signal(signal: UserSignal) -> None:
    for value, field in ((signal.signal_type, "signal.signal_type"), (signal.source, "signal.source"), (signal.observed, "signal.observed"), (signal.summary, "signal.summary")):
        _require(value, field)

def validate_feedback(item: FeedbackItem) -> None:
    for value, field in ((item.feedback_id, "feedback.feedback_id"), (item.source, "feedback.source"), (item.observed, "feedback.observed"), (item.summary, "feedback.summary")):
        _require(value, field)

def validate_proposal(proposal: ImprovementProposal) -> None:
    for value, field in ((proposal.proposal_id, "proposal.proposal_id"), (proposal.improvement_type, "proposal.improvement_type"), (proposal.rationale, "proposal.rationale")):
        _require(value, field)
    if not proposal.source_feedback_ids:
        raise ContinuousImprovementError("proposal requires feedback evidence")

def lifecycle_fingerprint(cycle: ImprovementCycle) -> str:
    validate_release(cycle.current_release)
    for item in cycle.signals: validate_signal(item)
    for item in cycle.feedback: validate_feedback(item)
    for item in cycle.proposals: validate_proposal(item)
    payload = {
        "release": cycle.current_release.__dict__,
        "signals": [x.__dict__ for x in cycle.signals],
        "feedback": [x.__dict__ for x in cycle.feedback],
        "proposals": [{**x.__dict__, "source_feedback_ids": list(x.source_feedback_ids)} for x in cycle.proposals],
        "next_release_version": cycle.next_release_version,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()

def build_improvement_backlog(feedback: Iterable[FeedbackItem], proposals: Iterable[ImprovementProposal]) -> tuple[ImprovementProposal, ...]:
    feedback = tuple(feedback); proposals = tuple(proposals)
    for item in feedback: validate_feedback(item)
    feedback_ids = {item.feedback_id for item in feedback}
    for proposal in proposals:
        validate_proposal(proposal)
        missing = set(proposal.source_feedback_ids) - feedback_ids
        if missing: raise ContinuousImprovementError(f"proposal references missing feedback: {sorted(missing)}")
    return tuple(sorted(proposals, key=lambda x: x.proposal_id))

def evaluate_cycle(cycle: ImprovementCycle) -> str:
    validate_release(cycle.current_release)
    if cycle.current_release.status != "released": return "no_go"
    if not cycle.feedback: return "needs_evidence"
    backlog = build_improvement_backlog(cycle.feedback, cycle.proposals)
    if not backlog: return "needs_evidence"
    if any(p.status == "rejected" for p in backlog): return "no_go"
    if any(p.status not in ("approved", "implemented") for p in backlog): return "needs_evidence"
    if not cycle.next_release_version: return "needs_evidence"
    return "go"