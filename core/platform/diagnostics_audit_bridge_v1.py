"""P311-P320 privacy-safe diagnostics to tamper-evident audit bridge."""
from __future__ import annotations
from typing import Iterable, Mapping, Any
from .diagnostics import DiagnosticEvent
from .audit_integrity import seal_events, verify_chain

FORBIDDEN_KEYS=frozenset({"token","password","secret","api_key","apikey","authorization","access_token","private_key"})

def event_to_audit(event: DiagnosticEvent) -> dict[str, Any]:
    clean=event.sanitized()
    details=clean["details"]
    # Diagnostics already redact sensitive keys; reject raw sensitive names/values that could
    # accidentally cross the boundary in future changes.
    for key in details:
        if key.casefold() in FORBIDDEN_KEYS and details[key] != "<redacted>":
            raise ValueError("sensitive diagnostic detail crossed audit boundary")
    return clean

def bridge_events(events: Iterable[DiagnosticEvent]) -> list[dict[str, Any]]:
    return seal_events(event_to_audit(e) for e in events)

def verify_bridged_events(events: Iterable[Mapping[str, Any]]) -> bool:
    return verify_chain(events)
