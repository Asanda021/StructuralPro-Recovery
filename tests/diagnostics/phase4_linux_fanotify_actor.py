"""Isolated fanotify PID-attribution proof for a disposable SQLite replacement.

No production or repository database is opened. A successful result identifies
the synthetic child process only, NEVER the historical DBMOVED actor.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import select
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import traceback

FAN_CLOEXEC = 0x00000001
FAN_NONBLOCK = 0x00000002
FAN_REPORT_DIR_FID = 0x00000400
FAN_REPORT_NAME = 0x00000800
FAN_MARK_ADD = 0x00000001
FAN_MARK_ONLYDIR = 0x00000008
FAN_MOVED_FROM = 0x00000040
FAN_MOVED_TO = 0x00000080
FAN_RENAME = 0x10000000
FAN_EVENT_ON_CHILD = 0x08000000
FAN_Q_OVERFLOW = 0x00004000
METADATA = struct.Struct("=IBBHQii")

libc = ctypes.CDLL(None, use_errno=True)
libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
libc.fanotify_init.restype = ctypes.c_int
libc.fanotify_mark.argtypes = [
    ctypes.c_int, ctypes.c_uint, ctypes.c_uint64, ctypes.c_int, ctypes.c_char_p
]
libc.fanotify_mark.restype = ctypes.c_int


def checked(fd: int) -> int:
    if fd < 0:
        err = ctypes.get_errno()
        raise OSError(err, os.strerror(err))
    return fd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="sqlite-audit-evidence")
    opts = parser.parse_args()
    evidence_dir = Path(opts.outdir).resolve()
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {
        "backend": "fanotify",
        "status": "NOT_RUN",
        "attributed": False,
        "historical_actor_identified": False,
        "scope": "disposable SQLite fixture, isolated directory, synthetic child actor only",
    }
    watchfd = -1
    try:
        with tempfile.TemporaryDirectory(prefix="sp-fanotify-actor-") as temp:
            base = Path(temp)
            db = base / "projects.db"
            replacement = base / "replacement.db"
            displaced = base / "displaced.db"
            for path, value in ((db, "active"), (replacement, "older")):
                con = sqlite3.connect(path)
                try:
                    con.execute("CREATE TABLE sample (label TEXT)")
                    con.execute("INSERT INTO sample VALUES (?)", (value,))
                    con.commit()
                finally:
                    con.close()
            original = db.stat()
            flags = FAN_CLOEXEC | FAN_NONBLOCK | FAN_REPORT_DIR_FID | FAN_REPORT_NAME
            watchfd = checked(libc.fanotify_init(flags, os.O_RDONLY | os.O_CLOEXEC))
            mask = FAN_MOVED_FROM | FAN_MOVED_TO | FAN_RENAME | FAN_EVENT_ON_CHILD
            checked(libc.fanotify_mark(
                watchfd, FAN_MARK_ADD | FAN_MARK_ONLYDIR,
                mask, -100, os.fsencode(base),
            ))
            conn = sqlite3.connect(db)
            try:
                conn.execute("SELECT COUNT(*) FROM sample").fetchone()
                actor_script = (
                    "import os,sys;"
                    "os.replace(sys.argv[1],sys.argv[2]);"
                    "os.replace(sys.argv[3],sys.argv[1])"
                )
                actor = subprocess.Popen(
                    [sys.executable, "-c", actor_script, str(db), str(displaced), str(replacement)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                stdout, stderr = actor.communicate(timeout=20)
                evidence["actor"] = {
                    "pid": actor.pid, "executable": sys.executable,
                    "exit": actor.returncode, "stdout": stdout, "stderr": stderr
                }
                evidence["inode_changed"] = (original.st_dev, original.st_ino) != (
                    db.stat().st_dev, db.stat().st_ino
                )
            finally:
                conn.close()
            events: list[dict[str, int]] = []
            until = time.monotonic() + 6.0
            while time.monotonic() < until:
                readable, _, _ = select.select([watchfd], [], [], 0.5)
                if not readable:
                    continue
                try:
                    data = os.read(watchfd, 65536)
                except BlockingIOError:
                    continue
                index = 0
                while index + METADATA.size <= len(data):
                    event_len, version, _, metadata_len, event_mask, file_fd, pid = METADATA.unpack_from(data, index)
                    if event_len < METADATA.size or index + event_len > len(data):
                        raise RuntimeError("malformed fanotify event size")
                    if version != 3:
                        raise RuntimeError("unexpected fanotify metadata version")
                    if file_fd >= 0:
                        os.close(file_fd)
                    events.append({"pid": pid, "mask": event_mask})
                    index += event_len
                if any(e["pid"] == actor.pid and e["mask"] & (FAN_MOVED_FROM | FAN_MOVED_TO | FAN_RENAME)
                       for e in events):
                    break
            evidence["events"] = events
            evidence["queue_overflow"] = any(e["mask"] & FAN_Q_OVERFLOW for e in events)
            evidence["attributed"] = (
                actor.returncode == 0 and evidence["inode_changed"]
                and not evidence["queue_overflow"]
                and any(e["pid"] == actor.pid
                        and e["mask"] & (FAN_MOVED_FROM | FAN_MOVED_TO | FAN_RENAME)
                        for e in events)
            )
            evidence["status"] = "ATTRIBUTION_CONFIRMED" if evidence["attributed"] else "NO_PID_ATTRIBUTION"
            return 0 if evidence["attributed"] else 1
    except OSError as exc:
        evidence["status"] = "FANOTIFY_UNAVAILABLE"
        evidence["errno"] = exc.errno
        evidence["exception"] = str(exc)
        return 2
    except Exception as exc:
        evidence["status"] = "PROBE_ERROR"
        evidence["exception"] = str(exc)
        evidence["traceback"] = traceback.format_exc()
        return 1
    finally:
        if watchfd >= 0:
            os.close(watchfd)
        (evidence_dir / "fanotify-result.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({
            "backend": "fanotify", "status": evidence["status"],
            "attributed": evidence["attributed"], "historical_actor_identified": False
        }, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
