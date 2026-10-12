"""Deterministic unified AEC project-twin identity/link contract."""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json


ALLOWED_DOMAINS = {"structural", "architectural", "mechanical", "electrical", "civil", "general"}
ALLOWED_STATUSES = {"draft", "linked", "review", "accepted"}


@dataclass(frozen=True)
class TwinLink:
    link_id: str
    project_id: str
    revision: str
    domain: str
    source_id: str
    element_id: str
    quantity_id: str
    bo_q_id: str
    status: str = "draft"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_link(link: TwinLink) -> None:
    if not all((link.link_id, link.project_id, link.revision, link.source_id, link.element_id, link.quantity_id, link.bo_q_id)):
        raise ValueError("twin link identity and traceability fields are required")
    if link.domain not in ALLOWED_DOMAINS:
        raise ValueError("invalid AEC domain")
    if link.status not in ALLOWED_STATUSES:
        raise ValueError("invalid twin link status")


def link_element(link: TwinLink) -> TwinLink:
    validate_link(link)
    return TwinLink(**{**asdict(link), "status": "linked"})


def fingerprint(link: TwinLink) -> str:
    validate_link(link)
    return sha256(_canonical(asdict(link)).encode("utf-8")).hexdigest()
