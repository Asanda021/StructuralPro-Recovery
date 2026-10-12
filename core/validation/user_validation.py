"""Structured real-user validation sessions without collecting sensitive data."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
@dataclass(frozen=True)
class ValidationObservation:
    workflow: str
    outcome: str
    severity: str = "info"
    note: str = ""
@dataclass(frozen=True)
class ValidationSession:
    session_id: str
    tester_role: str
    observations: tuple[ValidationObservation, ...] = ()
    @property
    def blockers(self): return tuple(o for o in self.observations if o.severity=="blocker")
    @property
    def ready_for_beta(self): return bool(self.observations) and not self.blockers
def make_session(session_id:str,tester_role:str,observations:Iterable[ValidationObservation]=()):
    if not session_id.strip() or not tester_role.strip(): raise ValueError("session_id and tester_role are required")
    return ValidationSession(session_id.strip(),tester_role.strip(),tuple(observations))
def validation_summary(session):
    return {"session_id":session.session_id,"tester_role":session.tester_role,"observations":len(session.observations),"blockers":len(session.blockers),"ready_for_beta":session.ready_for_beta}
