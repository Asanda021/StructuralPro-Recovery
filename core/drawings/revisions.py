from __future__ import annotations
from typing import Any, Iterable

def _key(x: Any) -> str:
    if hasattr(x, "handle"):
        return str(x.handle)
    if isinstance(x, dict):
        return str(x.get("handle") or x.get("id") or x.get("description") or x)
    return str(x)

def _value(x: Any) -> Any:
    if isinstance(x, dict):
        return {k: v for k, v in x.items() if k not in {"handle", "id"}}
    if hasattr(x, "__dict__"):
        return dict(x.__dict__)
    return x

def compare(old: Iterable[Any], new: Iterable[Any]) -> dict[str, Any]:
    a = {_key(x): x for x in old}
    b = {_key(x): x for x in new}
    added_keys = b.keys() - a.keys()
    removed_keys = a.keys() - b.keys()
    common = a.keys() & b.keys()
    changed_keys = {k for k in common if _value(a[k]) != _value(b[k])}
    unchanged_keys = common - changed_keys
    return {
        "added": [b[k] for k in added_keys],
        "removed": [a[k] for k in removed_keys],
        "changed": [{"old": a[k], "new": b[k]} for k in changed_keys],
        "unchanged": [b[k] for k in unchanged_keys],
        "summary": {
            "added": len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed_keys),
            "unchanged": len(unchanged_keys),
        },
    }

def quantity_delta(old: Iterable[dict[str, Any]], new: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(row: dict[str, Any]) -> tuple[str, str]:
        return (str(row.get("price_code") or row.get("description") or ""), str(row.get("unit") or ""))
    a = {key(r): r for r in old}
    b = {key(r): r for r in new}
    out: list[dict[str, Any]] = []
    for k in sorted(a.keys() | b.keys()):
        old_q = float(a.get(k, {}).get("quantity", 0) or 0)
        new_q = float(b.get(k, {}).get("quantity", 0) or 0)
        out.append({
            "key": k,
            "description": b.get(k, a.get(k, {})).get("description", ""),
            "unit": b.get(k, a.get(k, {})).get("unit", ""),
            "old_quantity": old_q,
            "new_quantity": new_q,
            "delta": new_q - old_q,
        })
    return out
