"""Observe the actual phase-4 five-floor SQLite workload using Linux fanotify.

Strictly QA-only: runs isolated fixtures, captures kernel PID + FID filename
records and live file identity. Never attributes an old failure to a new run.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
import traceback

FAN_CLOEXEC = 0x1
FAN_NONBLOCK = 0x2
FAN_REPORT_DIR_FID = 0x400
FAN_REPORT_NAME = 0x800
FAN_MARK_ADD = 0x1
FAN_MARK_ONLYDIR = 0x8
FAN_MOVED_FROM = 0x40
FAN_MOVED_TO = 0x80
FAN_CREATE = 0x100
FAN_DELETE = 0x200
FAN_RENAME = 0x10000000
FAN_EVENT_ON_CHILD = 0x08000000
FAN_ONDIR = 0x40000000  # Required: renaming an ancestor directory is a directory event.
FAN_Q_OVERFLOW = 0x4000
INTEREST = FAN_RENAME | FAN_MOVED_FROM | FAN_MOVED_TO | FAN_DELETE | FAN_CREATE
HEADER = struct.Struct("=IBBHQii")
INFO = struct.Struct("=BBH")
HANDLE = struct.Struct("=Ii")

libc = ctypes.CDLL(None, use_errno=True)
libc.fanotify_init.argtypes = [ctypes.c_uint, ctypes.c_uint]
libc.fanotify_init.restype = ctypes.c_int
libc.fanotify_mark.argtypes = [
    ctypes.c_int, ctypes.c_uint, ctypes.c_uint64, ctypes.c_int, ctypes.c_char_p
]
libc.fanotify_mark.restype = ctypes.c_int


def stat(path: Path) -> dict:
    try:
        s = path.stat()
        return {"dev": s.st_dev, "inode": s.st_ino, "size": s.st_size}
    except OSError:
        return {"missing": True}


def proc_info(pid: int) -> dict:
    result = {"pid": pid}
    try:
        result["exe"] = os.readlink(f"/proc/{pid}/exe")
        result["cmdline"] = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")[:300]
    except (OSError, ValueError):
        result["process_exited_before_lookup"] = True
    return result


class Watch:
    def __init__(self, directory: Path, scope_root: Path | None = None):
        self.directory = directory
        flags = FAN_CLOEXEC | FAN_NONBLOCK | FAN_REPORT_DIR_FID | FAN_REPORT_NAME
        self.fd = libc.fanotify_init(flags, os.O_RDONLY | os.O_CLOEXEC)
        if self.fd < 0:
            err = ctypes.get_errno()
            raise OSError(err, os.strerror(err))
        # Watching db/ alone misses rename/unlink of db/, engineering/, etc.
        # Mark each existing ancestor up to the isolated fixture parent.
        stop = (scope_root or directory).resolve()
        cur = directory.resolve()
        watch_paths = []
        while True:
            watch_paths.append(cur)
            if cur == stop:
                break
            if cur == cur.parent or stop not in cur.parents:
                os.close(self.fd)
                raise ValueError("scope_root must be this directory or an ancestor")
            cur = cur.parent
        mask = INTEREST | FAN_EVENT_ON_CHILD | FAN_ONDIR
        try:
            for watched in watch_paths:
                rc = libc.fanotify_mark(
                    self.fd, FAN_MARK_ADD | FAN_MARK_ONLYDIR, mask, -100,
                    os.fsencode(watched))
                if rc < 0:
                    err = ctypes.get_errno()
                    raise OSError(err, os.strerror(err), str(watched))
        except Exception:
            os.close(self.fd)
            raise
        self.watch_paths = watch_paths
        self.last_topology = {str(p): stat(p) for p in watch_paths}
        self.topology_changes = []
        self.events = []
        self.overflow = False

    def close(self):
        os.close(self.fd)

    def drain(self):
        current = {str(p): stat(p) for p in self.watch_paths}
        if current != self.last_topology:
            self.topology_changes.append({
                "wall_ns": time.time_ns(), "before": self.last_topology,
                "after": current})
            self.last_topology = current
        while select.select([self.fd], [], [], 0)[0]:
            try:
                data = os.read(self.fd, 131072)
            except BlockingIOError:
                break
            offset = 0
            while offset + HEADER.size <= len(data):
                length, version, _, meta_length, mask, file_fd, pid = HEADER.unpack_from(data, offset)
                if length < HEADER.size or version != 3 or meta_length < HEADER.size or offset + length > len(data):
                    raise RuntimeError("invalid fanotify event header")
                if file_fd >= 0:
                    os.close(file_fd)
                names = []
                info_types = []
                cur = offset + meta_length
                end = offset + length
                while cur + INFO.size <= end:
                    type_id, _, size = INFO.unpack_from(data, cur)
                    if size < INFO.size or cur + size > end:
                        raise RuntimeError("invalid fanotify fid info")
                    info_types.append(type_id)
                    if type_id in (2, 10, 12):
                        # fanotify_event_info_fid: 4-byte info header, 8-byte
                        # fsid, 8-byte file_handle header and handle_bytes.
                        h = cur + INFO.size + 8
                        if h + HANDLE.size <= cur + size:
                            handle_size, _ = HANDLE.unpack_from(data, h)
                            begin = h + HANDLE.size + handle_size
                            if begin < cur + size:
                                name = data[begin:cur + size].split(b"\0", 1)[0].decode(errors="replace")
                                if name:
                                    names.append({"kind":type_id, "name":name})
                    cur += size
                event = {
                    "wall_ns": time.time_ns(), "pid": pid, "mask": mask,
                    "names": names, "info_types": info_types, "process": proc_info(pid)
                }
                self.events.append(event)
                if mask & FAN_Q_OVERFLOW:
                    self.overflow = True
                offset += length


def run_child(watch: Watch, argv: list[str], env: dict, outfile: Path, timeout: int) -> dict:
    started = time.monotonic()
    with outfile.open("w", encoding="utf-8") as out:
        child = subprocess.Popen(argv, stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        while child.poll() is None:
            watch.drain()
            if time.monotonic() - started > timeout:
                import signal
                os.killpg(child.pid, signal.SIGTERM)
                child.wait(timeout=8)
                watch.drain()
                return {"exit": child.returncode, "timeout": True, "pid": child.pid}
            time.sleep(0.025)
        watch.drain()
    return {"exit": child.returncode, "timeout": False, "pid": child.pid}


def pilot(watch: Watch, dbdir: Path, out: Path):
    """Known child rename, verified by both PID and filename, not just a PID."""
    source = dbdir / "projects.db"
    newer = dbdir / "replacement.db"
    for path, value in ((source, "first"), (newer, "second")):
        with sqlite3.connect(path) as con:
            con.execute("CREATE TABLE sample (value TEXT)")
            con.execute("INSERT INTO sample VALUES (?)", (value,))
    old = stat(source)
    code = "import os,sys;os.replace(sys.argv[1],sys.argv[2]);os.replace(sys.argv[3],sys.argv[1])"
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(source), str(dbdir / "displaced.db"), str(newer)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    while child.poll() is None:
        watch.drain()
        time.sleep(0.005)
    stdout, stderr = child.communicate(timeout=5)
    watch.drain()
    matching = [e for e in watch.events if e["pid"] == child.pid
                and e["mask"] & (FAN_RENAME | FAN_MOVED_FROM | FAN_MOVED_TO)
                and any(n["name"] == "projects.db" for n in e["names"])]
    result = {
        "pid": child.pid, "exit": child.returncode, "stderr": stderr[:300],
        "old_inode": old, "new_inode": stat(source),
        "matching_named_pid_events": len(matching), "event_names": [e["names"] for e in matching],
        "pass": child.returncode == 0 and old["inode"] != stat(source)["inode"] and bool(matching)
    }
    for path in (source, dbdir / "displaced.db", newer):
        path.unlink(missing_ok=True)
    for suffix in ("-journal", "-wal", "-shm"):
        (dbdir / ("projects.db" + suffix)).unlink(missing_ok=True)
    watch.drain()
    watch.events.clear()
    (out / "pilot.json").write_text(json.dumps(result, indent=2))
    return result



def pilot_parent_directory(watch: Watch, dbdir: Path, out: Path) -> dict:
    """Reproduce real SQLite 1032 via replacing a parent *directory*.

    Directory events may have kernel pid=0. Never infer actor attribution
    from the subprocess we deliberately created or from timing alone.
    """
    parent = dbdir.parent
    source = dbdir / "projects.db"
    candidate = parent / "db-candidate"
    displaced = parent / "db-held"
    replacement_held = parent / "db-swap-inspection"
    candidate.mkdir()
    for filename, value in ((source, "original"), (candidate / "projects.db", "replacement")):
        with sqlite3.connect(filename) as connection:
            connection.execute("CREATE TABLE marker(value TEXT)")
            connection.execute("INSERT INTO marker VALUES(?)", (value,))
    live = sqlite3.connect(source)
    result = {"pass": False, "native_code": None, "event_pids": []}
    try:
        assert live.execute("SELECT value FROM marker").fetchone()[0] == "original"
        old = stat(source)
        code = "import os,sys;os.rename(sys.argv[1],sys.argv[2]);os.rename(sys.argv[3],sys.argv[1])"
        child = subprocess.Popen(
            [sys.executable, "-c", code, str(dbdir), str(displaced), str(candidate)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while child.poll() is None:
            watch.drain()
            time.sleep(0.005)
        _, stderr = child.communicate(timeout=5)
        watch.drain()
        now = stat(source)
        error_name, error_code = None, None
        try:
            live.execute("INSERT INTO marker VALUES ('unacknowledged')")
            live.commit()
        except sqlite3.DatabaseError as exc:
            error_name = getattr(exc, "sqlite_errorname", None)
            error_code = getattr(exc, "sqlite_errorcode", None)
        # A directory rename is named db in the *engineering/* watch,
        # not projects.db in the old db/* watch.
        named = [e for e in watch.events
                 if e["mask"] & (FAN_RENAME | FAN_MOVED_FROM | FAN_MOVED_TO)
                 and any(n["name"] == "db" for n in e["names"])]
        result = {
            "pass": (child.returncode == 0 and old["inode"] != now.get("inode")
                     and error_code == 1032 and bool(named) and not watch.overflow),
            "child_exit": child.returncode, "child_stderr": stderr[:300],
            "old_db_inode": old.get("inode"), "new_db_inode": now.get("inode"),
            "native_code": error_code, "native_name": error_name,
            "parent_events": named, "event_pids": [e["pid"] for e in named],
            "historical_actor_identified": False,
            "attribution_note": ("pid=0 is NOT an attributable process; "
                                 "a deliberately created pilot child is NOT the historical actor"),
        }
    finally:
        live.close()
        # Restore only the disposable pilot. Do not touch a real project file.
        if displaced.exists():
            if dbdir.exists():
                dbdir.rename(replacement_held)
            displaced.rename(dbdir)
        if replacement_held.exists():
            shutil.rmtree(replacement_held)
        if candidate.exists():
            shutil.rmtree(candidate)
        for suffix in ("", "-journal", "-wal", "-shm"):
            (dbdir / ("projects.db" + suffix)).unlink(missing_ok=True)
        watch.drain()
        watch.events.clear()
        watch.topology_changes.clear()
        watch.last_topology = {str(p): stat(p) for p in watch.watch_paths}
    (out / "parent-pilot.json").write_text(json.dumps(result, indent=2))
    return result


def observe(round_no: int, base: Path, dest: Path, timeout: int) -> dict:
    root = base / "scenario"
    dbdir = root / "prior" / "engineering" / "db"
    dbdir.mkdir(parents=True, exist_ok=False)
    out = dest / f"round-{round_no}"
    out.mkdir(parents=True, exist_ok=False)
    watcher = Watch(dbdir, root.parent)
    try:
        proof = pilot(watcher, dbdir, out)
        parent_proof = pilot_parent_directory(watcher, dbdir, out) if proof["pass"] else {"pass": False}
        if not proof["pass"] or not parent_proof["pass"] or watcher.overflow:
            return {"round": round_no, "status": "WATCHER_PILOT_FAILED",
                    "pilot": proof, "parent_pilot": parent_proof,
                    "overflow": watcher.overflow}
        worker_out = out / "worker"
        env = dict(os.environ)
        env.update({
            "SP_SQLITE_ROOT": str(root),
            "SP_SQLITE_OUT": str(worker_out),
            "SP_SQLITE_MODE": "audited",
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONPATH": str(Path.cwd()) + os.pathsep + str(Path.cwd() / "tests"),
        })
        target = "docs/acceptance/phase4_p4_6/closure-20261025/sqlite_worker.py::test_independent_original_scenario"
        child_result = run_child(watcher,
            [sys.executable, "-m", "pytest", "-q", "-s", target],
            env, out / "pytest.log", timeout)
        target_events = [e for e in watcher.events
                         if e["mask"] & (FAN_RENAME | FAN_MOVED_FROM | FAN_MOVED_TO | FAN_DELETE)
                         and any(n["name"] == "projects.db" for n in e["names"])]
        all_move_events = [e for e in watcher.events
                           if e["mask"] & (FAN_RENAME | FAN_MOVED_FROM | FAN_MOVED_TO | FAN_DELETE)]
        ancestor_names = {p.name for p in watcher.watch_paths if p != dbdir}
        ancestor_events = [e for e in all_move_events
                           if any(n["name"] in ancestor_names for n in e["names"])]
        worker_result = worker_out / "result.json"
        worker_data = json.loads(worker_result.read_text()) if worker_result.exists() else {}
        sqlite_file = dbdir / "projects.db"
        stat_result = stat(sqlite_file)
        events_file = worker_out / "events.jsonl"
        dbmoved = False
        sqlite_errors = []
        event_sha = None
        if events_file.exists():
            h = hashlib.sha256()
            with events_file.open("rb") as file:
                for line in file:
                    h.update(line)
                    if b"DBMOVED" in line or b"\"moved\": true" in line:
                        dbmoved = True
            event_sha = h.hexdigest()
        for state in worker_out.glob("failure-*/state.json") if worker_out.exists() else []:
            s = json.loads(state.read_text())
            sqlite_errors.append({"stage": s.get("stage"),
                                  "code": s.get("sqlite_errorcode"),
                                  "name": s.get("sqlite_errorname")})
            if s.get("sqlite_errorname") == "SQLITE_READONLY_DBMOVED":
                dbmoved = True
        integrity = None
        if sqlite_file.exists():
            try:
                conn = sqlite3.connect(sqlite_file.as_uri() + "?mode=ro", uri=True)
                try:
                    integrity = conn.execute("PRAGMA integrity_check").fetchall()
                finally:
                    conn.close()
            except sqlite3.Error as e:
                integrity = [{"error": str(e)}]
        result = {
            "round": round_no,
            "root": str(root), "pilot": proof, "parent_pilot": parent_proof,
            "worker": child_result,
            "worker_status": worker_data.get("status", "NO_RESULT"),
            "sqlite_errors": sqlite_errors, "dbmoved_detected": dbmoved,
            "db_identity": stat_result, "integrity": integrity,
            "kernel_events_count": len(watcher.events),
            "kernel_move_delete_count": len(all_move_events),
            "projects_db_rename_delete": target_events,
            "ancestor_directory_rename_delete": ancestor_events,
            "ancestor_topology_changes": watcher.topology_changes,
            "watched_ancestor_paths": [str(p) for p in watcher.watch_paths],
            "events_sha256": event_sha,
            "lost_kernel_events": watcher.overflow,
            "scope": "isolated synthetic workload; a fresh run cannot identify the historical actor"
        }
        (out / "fanotify-events.json").write_text(json.dumps(watcher.events, indent=2))
        (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        # Do not turn a successful rerun into a claim of historical resolution.
        result["status"] = ("WORKLOAD_FAILURE_OBSERVED" if child_result["exit"]
                            else "WORKLOAD_PASS_NO_HISTORICAL_ATTRIBUTION")
        if (target_events or ancestor_events) and dbmoved:
            result["status"] = "FRESH_DBMOVED_KERNEL_EVENT_NEEDS_PID_REVIEW"
            # With directory FAN_RENAME the kernel may return pid=0.
            # Do not claim a perpetrator unless an event has a real PID and
            # that process can be independently tied to the target operation.
        (out / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    finally:
        watcher.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--outdir", required=True)
    p.add_argument("--workspace", required=True)
    p.add_argument("--timeout", type=int, default=190)
    a = p.parse_args()
    out = Path(a.outdir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    outcome = {"final": "UNRESOLVED", "historical_actor_identified": False, "rounds": []}
    try:
        locations = [
            Path(a.workspace).resolve() / "sqlite-workload-disposable",
            Path("/tmp") / f"structuralpro-workload-{os.getpid()}"
        ]
        for i, base in enumerate(locations, 1):
            if base.exists():
                raise RuntimeError(f"refusing non-empty fixture path: {base}")
            base.mkdir(parents=True)
            result = observe(i, base, out, a.timeout)
            outcome["rounds"].append({
                k: result.get(k) for k in ("round", "status", "worker", "worker_status",
                                         "sqlite_errors", "dbmoved_detected",
                                         "kernel_move_delete_count", "projects_db_rename_delete",
                                         "ancestor_directory_rename_delete", "ancestor_topology_changes",
                                         "watched_ancestor_paths", "parent_pilot",
                                         "lost_kernel_events", "integrity", "pilot", "db_identity")
            })
            print(json.dumps(outcome["rounds"][-1], ensure_ascii=False), flush=True)
            if result.get("status") in ("FRESH_DBMOVED_KERNEL_EVENT_NEEDS_PID_REVIEW",
                                        "WATCHER_PILOT_FAILED", "WORKLOAD_FAILURE_OBSERVED"):
                break
        if outcome["rounds"] and all(r.get("worker", {}).get("exit") == 0
                                      and r.get("pilot", {}).get("pass")
                                      for r in outcome["rounds"]):
            outcome["final"] = "TWO_FRESH_RUNS_HEALTHY_ROOT_CAUSE_STILL_UNRESOLVED"
        elif outcome["rounds"][-1].get("status") == "FRESH_DBMOVED_KERNEL_EVENT_NEEDS_PID_REVIEW":
            outcome["final"] = "FRESH_DBMOVED_KERNEL_EVENT_ACTOR_NOT_PROVEN"
        else:
            outcome["final"] = "INVESTIGATION_BLOCKED_OR_FAILURE_NEEDS_REVIEW"
    except Exception as e:
        outcome["final"] = "DIAGNOSTIC_ERROR"
        outcome["error"] = repr(e)
        outcome["traceback"] = traceback.format_exc()
    finally:
        (out / "summary.json").write_text(json.dumps(outcome, indent=2, ensure_ascii=False))
        print("FINAL " + json.dumps(outcome, ensure_ascii=False), flush=True)
    return 0 if outcome["final"] in (
        "TWO_FRESH_RUNS_HEALTHY_ROOT_CAUSE_STILL_UNRESOLVED",
        "FRESH_DBMOVED_KERNEL_EVENT_ACTOR_NOT_PROVEN") else 1


if __name__ == "__main__":
    raise SystemExit(main())
