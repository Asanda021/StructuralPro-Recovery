"""Human-in-the-loop workflow contract for P651-P660."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Mapping

@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    action: str
    source_ids: tuple[str, ...]
    payload: Mapping[str, Any]
    confidence: float
    status: str = "pending"
    def validate(self) -> "Proposal":
        if not self.proposal_id.strip() or not self.action.strip() or not self.source_ids:
            raise ValueError("proposal identity, action and provenance are required")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if self.status not in {"pending","approved","rejected","executed"}:
            raise ValueError("invalid proposal status")
        return self

@dataclass(frozen=True)
class Approval:
    proposal_id: str
    reviewer: str
    approved: bool
    reason: str
    def validate(self) -> "Approval":
        if not self.proposal_id.strip() or not self.reviewer.strip() or not self.reason.strip():
            raise ValueError("review identity and reason are required")
        return self

@dataclass(frozen=True)
class Workflow:
    proposals: tuple[Proposal, ...]
    approvals: tuple[Approval, ...]
    fingerprint: str

    def validate(self) -> "Workflow":
        if not self.proposals:
            raise ValueError("workflow cannot be empty")
        if not self.fingerprint:
            raise ValueError("workflow fingerprint is required")
        for x in self.proposals: x.validate()
        for x in self.approvals: x.validate()
        return self

def _fp(proposals, approvals):
    raw=json.dumps({
        "proposals":[x.__dict__ for x in sorted(proposals,key=lambda x:x.proposal_id)],
        "approvals":[x.__dict__ for x in sorted(approvals,key=lambda x:(x.proposal_id,x.reviewer))]
    },ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return sha256(raw).hexdigest()

def create_workflow(proposals) -> Workflow:
    items=tuple(x.validate() for x in proposals)
    return Workflow(items,(),_fp(items,())).validate()

def review(workflow: Workflow, approvals) -> Workflow:
    approvals=tuple(x.validate() for x in approvals)
    ids={p.proposal_id for p in workflow.proposals}
    if any(a.proposal_id not in ids for a in approvals):
        raise ValueError("approval references unknown proposal")
    merged={a.proposal_id:a for a in approvals}
    updated=[]
    for p in workflow.proposals:
        a=merged.get(p.proposal_id)
        status=p.status
        if a is not None: status="approved" if a.approved else "rejected"
        updated.append(Proposal(p.proposal_id,p.action,p.source_ids,p.payload,p.confidence,status))
    return Workflow(tuple(updated),approvals,_fp(updated,approvals)).validate()

def execute_approved(workflow: Workflow, proposal_id: str) -> Mapping[str,Any]:
    proposal=next((p for p in workflow.proposals if p.proposal_id==proposal_id),None)
    if proposal is None: raise KeyError(proposal_id)
    if proposal.status!="approved":
        raise PermissionError("explicit human approval is required before execution")
    return {"proposal_id":proposal.proposal_id,"action":proposal.action,
            "payload":dict(proposal.payload),"executed":True,"source_ids":proposal.source_ids}
