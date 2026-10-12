"""P125 UX contract: RTL-safe actions, predictable keyboard navigation and validation."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Action:
    id: str
    label_fa: str
    label_en: str
    order: int
    enabled: bool = True

def action_menu(actions: list[Action]) -> list[dict]:
    if len({a.id for a in actions}) != len(actions):
        raise ValueError("duplicate action id")
    return [
        {"id": a.id, "label_fa": a.label_fa, "label_en": a.label_en,
         "order": a.order, "enabled": a.enabled}
        for a in sorted(actions, key=lambda a: a.order)
    ]

def validate_input(value: str, required: bool = True, max_length: int = 500) -> str:
    value = "" if value is None else str(value).strip()
    if required and not value:
        raise ValueError("input is required")
    if len(value) > max_length:
        raise ValueError("input exceeds maximum length")
    return value
