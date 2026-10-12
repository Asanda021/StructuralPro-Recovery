"""P46 — deterministic UX workflow contracts for desktop/mobile/tablet."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WorkflowStep:
    step_id:str; label:str; shortcut:str|None=None
@dataclass(frozen=True)
class DashboardCard:
    card_id:str; title:str; value:str; source_id:str

def build_workflow(steps:list[WorkflowStep])->tuple[WorkflowStep,...]:
    seen=set(); out=[]
    for s in steps:
        if not all(isinstance(v,str) and v.strip() for v in (s.step_id,s.label)): raise ValueError("workflow step is incomplete")
        if s.step_id in seen: raise ValueError("duplicate workflow step")
        if s.shortcut is not None and (not isinstance(s.shortcut,str) or not s.shortcut.strip()): raise ValueError("invalid shortcut")
        seen.add(s.step_id); out.append(s)
    if not out: raise ValueError("workflow cannot be empty")
    return tuple(out)

def build_dashboard(cards:list[DashboardCard])->tuple[dict[str,str],...]:
    seen=set(); out=[]
    for c in cards:
        if not all(isinstance(v,str) and v.strip() for v in (c.card_id,c.title,c.value,c.source_id)): raise ValueError("dashboard evidence is incomplete")
        if c.card_id in seen: raise ValueError("duplicate dashboard card")
        seen.add(c.card_id); out.append(c.__dict__.copy())
    return tuple(out)

def onboarding_steps()->tuple[str,...]:
    return ("create_project","import_drawings","review_takeoff","review_estimate","export_report")
