from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Mapping


@dataclass(frozen=True)
class ReadinessItem:
    key: str
    required: bool
    satisfied: bool
    evidence: str


@dataclass(frozen=True)
class ReleaseReadiness:
    items: tuple[ReadinessItem, ...]

    @property
    def required_satisfied(self) -> bool:
        return all(i.satisfied for i in self.items if i.required)

    @property
    def status(self) -> str:
        return "ready" if self.required_satisfied else "blocked"

    def manifest(self) -> dict:
        return {
            "status": self.status,
            "release_ready": self.required_satisfied,
            "items": [asdict(i) for i in self.items],
        }


DEFAULT_REQUIREMENTS = (
    ("customer_artifact", True, "real customer installer/artifact evidence"),
    ("entitlement_authorization", True, "verified customer entitlement authorization"),
    ("installation_evidence", True, "real Windows install/run/uninstall evidence"),
    ("pricebook_provenance", True, "verified licensed/source pricebook evidence"),
    ("third_party_licenses", True, "release-environment dependency/license evidence"),
    ("code_signing", False, "Windows signing certificate and signing evidence"),
    ("bundled_gguf", False, "redistributable GGUF license/checksum evidence"),
    ("dwg_runtime_terms", False, "approved DWG converter redistribution/runtime evidence"),
)


def evaluate(evidence: Mapping[str, bool]) -> ReleaseReadiness:
    items = tuple(
        ReadinessItem(key, required, bool(evidence.get(key, False)), description)
        for key, required, description in DEFAULT_REQUIREMENTS
    )
    return ReleaseReadiness(items)
