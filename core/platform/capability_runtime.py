"""Executable routing for the benchmark capability surface.

A capability is only reported as implemented when a real callable is attached.
Contract-only entries are deliberately reported separately so the product never
claims support that has not been wired into the runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class CapabilityBinding:
    capability_id: str
    handler: Callable[..., Any] | None
    state: str  # implemented | contract | planned


class CapabilityRuntime:
    def __init__(self):
        self._bindings: dict[str, CapabilityBinding] = {}

    def bind(self, capability_id: str, handler: Callable[..., Any]):
        self._bindings[capability_id] = CapabilityBinding(
            capability_id, handler, "implemented"
        )

    def contract(self, capability_id: str):
        self._bindings[capability_id] = CapabilityBinding(
            capability_id, None, "contract"
        )

    def planned(self, capability_id: str):
        self._bindings[capability_id] = CapabilityBinding(
            capability_id, None, "planned"
        )

    def run(self, capability_id: str, *args, **kwargs):
        binding = self._bindings[capability_id]
        if binding.handler is None:
            raise NotImplementedError(
                f"قابلیت {capability_id} در وضعیت {binding.state} است و "
                "هنوز آداپتور اجرایی ندارد."
            )
        return binding.handler(*args, **kwargs)

    def audit(self) -> dict[str, Any]:
        values = list(self._bindings.values())
        total = len(values)
        implemented = sum(x.state == "implemented" for x in values)
        contract = sum(x.state == "contract" for x in values)
        planned = sum(x.state == "planned" for x in values)
        return {
            "total": total,
            "implemented": implemented,
            "contract": contract,
            "planned": planned,
            "implemented_percent": round(implemented * 100 / total, 1) if total else 0.0,
            "coverage_percent": round((implemented + contract) * 100 / total, 1) if total else 0.0,
        }
