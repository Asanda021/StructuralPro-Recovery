"""Deterministic AI-QA boundary for evidence-first engineering workflows."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json
from typing import Mapping


ALLOWED_SEVERITIES = {"info", "warning", "error"}
ALLOWED_STATUSES = {"open", "review", "accepted", "rejected"}


@dataclass(frozen=True)
class QAInput:
    item_id: str
    source_ids: tuple[str, ...]
    claim: str
    revision: str
    status: str = "accepted"


@dataclass(frozen=True)
class QAFinding:
    finding_id: str
    item_id: str
    severity: str
    message: str
    evidence_ids: tuple[str, ...]
    status: str = "open"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_input(item: QAInput) -> None:
    if not item.item_id or not item.source_ids or not item.claim or not item.revision:
        raise ValueError("item identity, sources, claim and revision are required")
    if item.status not in ALLOWED_STATUSES:
        raise ValueError("invalid input status")


def create_finding(item: QAInput, finding_id: str, severity: str, message: str) -> QAFinding:
    validate_input(item)
    if item.status != "accepted":
        raise ValueError("only accepted evidence can create a QA finding")
    if severity not in ALLOWED_SEVERITIES or not message.strip():
        raise ValueError("invalid finding")
    return QAFinding(finding_id, item.item_id, severity, message, item.source_ids)


def validate_finding(finding: QAFinding) -> None:
    if not finding.finding_id or not finding.item_id or not finding.message:
        raise ValueError("finding identity and message are required")
    if finding.severity not in ALLOWED_SEVERITIES:
        raise ValueError("invalid severity")
    if not finding.evidence_ids:
        raise ValueError("QA finding requires evidence")
    if finding.status not in ALLOWED_STATUSES:
        raise ValueError("invalid finding status")


def fingerprint(finding: QAFinding) -> str:
    validate_finding(finding)
    return sha256(_canonical(asdict(finding)).encode("utf-8")).hexdigest()


def gate_findings(findings: tuple[QAFinding, ...]) -> str:
    for finding in findings:
        validate_finding(finding)
    if any(f.severity == "error" and f.status != "accepted" for f in findings):
        return "blocked"
    if any(f.severity == "warning" and f.status == "open" for f in findings):
        return "review"
    return "accepted"
