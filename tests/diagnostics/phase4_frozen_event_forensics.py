"""Analyze ONLY preserved historical SQLite inotify logs; never rerun workload.

The frozen worker watched the *inside* of db/, so a parent directory move
is not observable as a named projects.db event. PID is not in inotify data.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs/acceptance/phase4_p4_6/closure-20261025"
GZIP_PATH = "sqlite-runs-frozen/audited-workspace/events.jsonl.gz"
MASKS = {
    "IN_MOVED_FROM": 0x40, "IN_MOVED_TO": 0x80, "IN_CREATE": 0x100,
    "IN_DELETE": 0x200, "IN_DELETE_SELF": 0x400,
    "IN_MOVE_SELF": 0x800, "IN_Q_OVERFLOW": 0x4000,
}
FILE_NAMES = {"projects.db", "projects.db-journal", "projects.db-wal", "projects.db-shm"}


def analyze() -> dict:
    index = json.loads((EVIDENCE / "log-index.json").read_text(encoding="utf-8"))
    timeline = json.loads((EVIDENCE / "causal-timeline.json").read_text(encoding="utf-8"))
    source = EVIDENCE / GZIP_PATH
    expected = index[GZIP_PATH]
    compressed = source.read_bytes()
    assert hashlib.sha256(compressed).hexdigest() == expected["gzip_sha256"], "evidence archive hash mismatch"
    decompressed = gzip.decompress(compressed)
    assert hashlib.sha256(decompressed).hexdigest() == expected["raw_sha256"], "evidence bytes hash mismatch"
    assert len(decompressed) == expected["raw_bytes"], "evidence length mismatch"
    first = timeline["events"]["first_moved_INSERT"]["wall_ns"]
    begin = timeline["events"]["SQL_BEGIN"]["wall_ns"]
    counts = Counter()
    names = Counter()
    operations = Counter()
    relevant = []
    near_failure = []
    identity_changes = []
    overflows = []
    earlier = None
    for line_number, raw in enumerate(decompressed.splitlines(), 1):
        data = json.loads(raw)
        kind = data.get("event")
        counts[kind] += 1
        timestamp = data.get("wall_ns", 0)
        identity = data.get("identity") or {}
        if earlier and (earlier.get("inode"), earlier.get("device")) != (identity.get("inode"), identity.get("device")) and identity:
            identity_changes.append({
                "line": line_number, "at_ns": timestamp,
                "prev": earlier, "current": identity, "event": kind,
            })
        if identity:
            earlier = identity
        fs_events = data.get("filesystem_events") or []
        if abs(timestamp - first) < 1_000_000_000:
            near_failure.append({
                "line": line_number, "event": kind,
                "relative_ms": round((timestamp - first) / 1e6, 3),
                "identity": {k: identity.get(k) for k in ("device", "inode", "bytes")},
                "db_path": data.get("path"),
                "fds": [{"fd": fd.get("fd"), "target": fd.get("target")} for fd in data.get("fds", [])],
                "fs_events": fs_events[:15], "fs_event_count": len(fs_events),
                "moved": data.get("moved"),
            })
        for record in fs_events:
            name = record.get("name", "")
            try:
                mask = int(str(record.get("mask", "0")), 0)
            except ValueError:
                mask = 0
            names[name] += 1
            for label, bit in MASKS.items():
                if mask & bit:
                    operations[label] += 1
                    if label == "IN_Q_OVERFLOW":
                        overflows.append({"line": line_number, "at_ns": timestamp, "name": name})
            if mask & (0x40 | 0x80 | 0x200 | 0x400 | 0x800):
                relevant.append({
                    "line": line_number, "wall_ns": timestamp,
                    "relative_ms": round((timestamp - first) / 1e6, 3),
                    "event": kind, "mask": record.get("mask"),
                    "cookie": record.get("cookie"), "name": name,
                })

    direct = [e for e in relevant if e["name"] in FILE_NAMES]
    after_begin_before_failure = [e for e in relevant if begin <= e["wall_ns"] <= first]
    report = {
        "source": GZIP_PATH,
        "verified_sha256_compressed": expected["gzip_sha256"],
        "verified_sha256_raw": expected["raw_sha256"],
        "first_moved_utc": datetime.fromtimestamp(first/1e9, timezone.utc).isoformat(),
        "begin_to_first_moved_ms": round((first - begin) / 1e6, 3),
        "event_types": dict(counts), "inotify_operations": dict(operations),
        "observed_names_top_20": names.most_common(20),
        "inotify_rename_delete_events_total": len(relevant),
        "named_projects_db_move_delete_count": len(direct),
        "rename_delete_between_begin_and_first_moved": after_begin_before_failure[:30],
        "inotify_queue_overflows": overflows[:20],
        "inotify_identity_changes": identity_changes[-15:],
        "last_20_move_delete_events": relevant[-20:],
        "around_first_moved": near_failure[-22:],
        "watch_scope": "sqlite_worker.py Observed.__init__: inotify_add_watch(self.audit_path.parent, 0x00000fff) only",
        "parent_directory_watched": False,
        "operator_pid_available": False,
        "historical_actor": "UNRESOLVED",
        "interpretation": (
            "No target rename event does not exclude parent-directory replacement or "
            "a rename outside the observed watch. This report is forensically descriptive, "
            "NOT actor attribution and not a proof that parent directory was moved."
        ),
    }
    return report


def main() -> int:
    result = analyze()
    out = Path("phase4-frozen-event-forensics.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    condensed = {k: result[k] for k in (
        "verified_sha256_raw", "first_moved_utc", "begin_to_first_moved_ms",
        "event_types", "inotify_operations", "observed_names_top_20",
        "inotify_rename_delete_events_total", "named_projects_db_move_delete_count",
        "rename_delete_between_begin_and_first_moved",
        "inotify_queue_overflows", "historical_actor", "interpretation",
    )}
    print(json.dumps(condensed, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
