"""Deterministic offline conflict resolution for project records."""
from __future__ import annotations
from copy import deepcopy
from typing import Any


def _merge_value(base: Any, local: Any, remote: Any, path: str, conflicts: list[str]) -> Any:
    if local == remote:
        return deepcopy(local)
    if local == base:
        return deepcopy(remote)
    if remote == base:
        return deepcopy(local)

    if isinstance(base, dict) and isinstance(local, dict) and isinstance(remote, dict):
        out: dict[str, Any] = {}
        for key in sorted(set(base) | set(local) | set(remote)):
            child_path = f"{path}.{key}" if path else str(key)
            out[key] = _merge_value(
                base.get(key), local.get(key), remote.get(key), child_path, conflicts
            )
        return out

    conflicts.append(path)
    return {
        "_conflict": {
            "local": deepcopy(local),
            "remote": deepcopy(remote),
            "base": deepcopy(base),
        }
    }


def merge_dict(
    base: dict[str, Any], local: dict[str, Any], remote: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    """Three-way merge with deterministic recursive conflict paths."""
    if not all(isinstance(value, dict) for value in (base, local, remote)):
        raise TypeError("base, local and remote must be dictionaries")
    conflicts: list[str] = []
    out = _merge_value(base, local, remote, "", conflicts)
    return out, conflicts


def _resolve_path(project: dict[str, Any], path: str, choice: str) -> None:
    parts = path.split(".") if path else []
    if not parts:
        raise ValueError("conflict path is required")
    current: Any = project
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            return
        current = current[part]
    if not isinstance(current, dict):
        return
    value = current.get(parts[-1])
    if not isinstance(value, dict) or "_conflict" not in value:
        return
    conflict = value["_conflict"]
    if choice not in {"local", "remote", "base"}:
        raise ValueError("choice must be local, remote or base")
    current[parts[-1]] = deepcopy(conflict[choice])


def resolve_conflicts(project: dict[str, Any], choices: dict[str, str]) -> dict[str, Any]:
    """Resolve recorded conflicts by stable dotted path without silent loss."""
    out = deepcopy(project)
    if not isinstance(out, dict):
        raise TypeError("project must be a dictionary")
    for key in sorted(choices):
        _resolve_path(out, key, choices[key])
    return out
