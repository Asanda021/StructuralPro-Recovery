"""Opt-in, bounded, data-free durable markers for P6-5 real Qt dialog lifetime.

Diagnostic ONLY. No product changes, raw inputs, row IDs, SQL, PIDs, dump,
address or stack capture. Process-side journal preserves the last completed
boundary if the Windows native process crashes without pytest/JUnit output.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import time

from scripts.diagnose_windows_native_crash import atomic_json, append_jsonl

EVENTS = frozenset((
    "SELECT_ENTER", "SELECT_EXIT", "REVIEW_CLICK_ENTER", "REVIEW_CLICK_EXIT",
    "COMMIT_CLICK_ENTER", "COMMIT_CLICK_EXIT", "EVENTS_ENTER", "EVENTS_EXIT",
    "DEFERRED_ENTER", "DEFERRED_EXIT", "CONSTRUCT_ENTER", "CONSTRUCT_EXIT",
    "CASE_READY", "DIALOG_ENTER", "DIALOG_READY",
    "BATCH_COMMITTED", "SORT_FILTER_ENTER", "SORT_FILTER_EXIT",
    "REFRESH_ENTER", "REFRESH_EXIT",
    "DIALOG_DELETE_ENTER", "DIALOG_DELETE_EXIT",
    "STORE_CLOSE_ENTER", "STORE_CLOSE_EXIT",
    "REOPEN_ENTER", "REOPEN_EXIT", "ALL_DONE",
))
_counter = 0


def mark(event: str, *, cycle: int = -1, committed: int = 0) -> None:
    """No-op unless the diagnostic CI explicitly opts in."""
    folder = os.environ.get("P6_LIFECYCLE_CHECKPOINT_DIR")
    if not folder:
        return
    expected=os.environ.get("P6_EXPECT_FAULTHANDLER")
    if expected in ("enabled","disabled"):
        import faulthandler
        if faulthandler.is_enabled() != (expected=="enabled"):
            raise RuntimeError("FAULTHANDLER_STATE_CHANGED_DURING_CASE")
    if event not in EVENTS or not -1 <= cycle < 5 or not 0 <= committed <= 70:
        raise ValueError("Invalid bounded diagnostic checkpoint")
    global _counter
    _counter += 1
    output = Path(folder)
    output.mkdir(parents=True, exist_ok=True)
    item = {
        "sequence": _counter, "event": event, "cycle": cycle,
        "committed_rows": committed, "monotonic_ns": time.monotonic_ns(),
        "data_values_logged": False, "memory_dump_saved": False,
    }
    append_jsonl(output / "events.jsonl", item)
    atomic_json(output / "last.json", item)


def validate(folder: Path) -> dict:
    """Read-only finite journal check; never infer a PASS without original JUnit."""
    events_file = folder / "events.jsonl"
    last_file = folder / "last.json"
    if not events_file.is_file() or not last_file.is_file():
        return {"status": "MISSING", "entries": 0, "last": None}
    events = [json.loads(s) for s in events_file.read_text(encoding="utf-8").splitlines()]
    if not events:
        return {"status": "EMPTY", "entries": 0, "last": None}
    valid = all(
        item["event"] in EVENTS
        and item["sequence"] == i
        and -1 <= item["cycle"] < 5
        and 0 <= item["committed_rows"] <= 70
        and not item["data_values_logged"]
        and not item["memory_dump_saved"]
        for i, item in enumerate(events, 1)
    )
    last = json.loads(last_file.read_text(encoding="utf-8"))
    if last != events[-1]:
        valid = False
    return {
        "status": "VALID" if valid else "CORRUPT_OR_NONMONOTONIC",
        "entries": len(events),
        "last": last if valid else None,
        "completed": bool(valid and last["event"] == "ALL_DONE"),
    }


def self_check() -> None:
    import tempfile
    with tempfile.TemporaryDirectory(prefix="p6-marker-check-") as root:
        previous = os.environ.get("P6_LIFECYCLE_CHECKPOINT_DIR")
        try:
            os.environ["P6_LIFECYCLE_CHECKPOINT_DIR"] = root
            mark("CASE_READY")
            mark("DIALOG_READY", cycle=0)
            result = validate(Path(root))
            assert result["status"] == "VALID" and result["entries"] == 2
            assert not result["completed"]
            assert not any(x in json.dumps(result) for x in ("source_id", "variables", "sql"))
        finally:
            if previous is None:
                os.environ.pop("P6_LIFECYCLE_CHECKPOINT_DIR", None)
            else:
                os.environ["P6_LIFECYCLE_CHECKPOINT_DIR"] = previous


if __name__ == "__main__":
    self_check()
    print("P6 checkpoint sanitizer and durable ordering SELF_CHECK PASS")
