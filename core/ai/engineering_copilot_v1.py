"""Deterministic, evidence-first Engineering AI Copilot boundary.

The copilot proposes explanations/actions from supplied evidence only.
It never invents engineering values and never mutates project data implicitly.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Mapping, Sequence


ALLOWED_ACTIONS = {"explain", "propose", "review"}
ALLOWED_STATUSES = {"draft", "review", "accepted", "rejected"}


@dataclass(frozen=True)
class CopilotEvidence:
    evidence_id: str
    source_ids: tuple[str, ...]
    claim: str
    revision: str
    status: str = "accepted"


@dataclass(frozen=True)
class CopilotRequest:
    request_id: str
    intent: str
    context_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    action: str


@dataclass(frozen=True)
class CopilotResponse:
    request_id: str
    action: str
    evidence_ids: tuple[str, ...]
    proposal: str
    status: str


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_evidence(evidence: CopilotEvidence) -> None:
    if not evidence.evidence_id or not evidence.source_ids or not evidence.claim:
        raise ValueError("evidence identity, sources and claim are required")
    if not evidence.revision:
        raise ValueError("revision is required")
    if evidence.status not in ALLOWED_STATUSES:
        raise ValueError("invalid evidence status")


def validate_request(request: CopilotRequest, evidence: Mapping[str, CopilotEvidence]) -> None:
    if not request.request_id or not request.intent or not request.action:
        raise ValueError("request identity, intent and action are required")
    if request.action not in ALLOWED_ACTIONS:
        raise ValueError("unsupported action")
    if not request.evidence_ids:
        raise ValueError("evidence is required")
    for evidence_id in request.evidence_ids:
        if evidence_id not in evidence:
            raise ValueError("missing evidence")
        validate_evidence(evidence[evidence_id])
        if evidence[evidence_id].status != "accepted":
            raise ValueError("only accepted evidence can drive copilot output")


def respond(request: CopilotRequest, evidence: Mapping[str, CopilotEvidence], proposal: str) -> CopilotResponse:
    validate_request(request, evidence)
    if not proposal.strip():
        raise ValueError("proposal is required")
    return CopilotResponse(
        request_id=request.request_id,
        action=request.action,
        evidence_ids=tuple(request.evidence_ids),
        proposal=proposal,
        status="review",
    )


def fingerprint(response: CopilotResponse) -> str:
    payload = asdict(response)
    return sha256(_canonical(payload).encode("utf-8")).hexdigest()
