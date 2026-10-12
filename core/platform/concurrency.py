"""Optimistic concurrency guard for safe project writes."""
from __future__ import annotations
from typing import Any, Mapping
from .revisions import snapshot_digest

def begin_write(payload: Mapping[str, Any]) -> str:
    return snapshot_digest(payload)

def assert_unchanged(payload: Mapping[str, Any], expected_digest: str) -> None:
    if snapshot_digest(payload) != expected_digest:
        raise RuntimeError("project changed since write began")

def guarded_update(current: Mapping[str, Any], expected_digest: str, updated: Mapping[str, Any]) -> dict[str, Any]:
    assert_unchanged(current, expected_digest)
    return dict(updated)
