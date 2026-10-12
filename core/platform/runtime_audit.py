"""Deterministic runtime audit for the installed StructuralPro Python surface."""
from __future__ import annotations
import importlib
import pkgutil
import core

def discover_core_modules() -> list[str]:
    names = ["core"]
    for module in pkgutil.walk_packages(core.__path__, core.__name__ + "."):
        if not module.ispkg:
            names.append(module.name)
    return sorted(set(names))

def audit_core_runtime() -> dict[str, object]:
    failures: list[dict[str, str]] = []
    for name in discover_core_modules():
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures.append({"module": name, "error": f"{type(exc).__name__}: {exc}"})
    try:
        importlib.import_module("app.main")
    except Exception as exc:
        failures.append({"module": "app.main", "error": f"{type(exc).__name__}: {exc}"})
    return {
        "valid": not failures,
        "module_count": len(discover_core_modules()),
        "failures": failures,
    }
