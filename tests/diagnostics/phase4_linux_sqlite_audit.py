"""Isolated Linux audit attribution smoke test; uses ONLY disposable SQLite fixtures.

Success means a controlled rename/replacement was attributed to a known PID on
this runner. It does NOT identify the actor in the historical DBMOVED incident.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback


def run(*argv: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def msg_id(line: str) -> str | None:
    match = re.search(r"msg=audit\(([^)]+)\)", line)
    return match.group(1) if match else None


def find_attribution(log: str, expected_pid: int, filename: str) -> list[dict[str, str]]:
    """Require a SYSCALL PID and matching PATH in the SAME audit event."""
    lines = log.splitlines()
    paths: dict[str, list[str]] = {}
    for line in lines:
        if "type=PATH" in line and (event_id := msg_id(line)):
            paths.setdefault(event_id, []).append(line)
    found = []
    for line in lines:
        if "type=SYSCALL" not in line or not re.search(rf"\bpid={expected_pid}\b", line):
            continue
        event_id = msg_id(line)
        if event_id and any(filename in p for p in paths.get(event_id, [])):
            executable = re.search(r'\bexe="([^"]+)"', line)
            comm = re.search(r'\bcomm="([^"]+)"', line)
            found.append({
                "event": event_id,
                "pid": str(expected_pid),
                "exe": executable.group(1) if executable else "unavailable",
                "comm": comm.group(1) if comm else "unavailable",
            })
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--outdir", default="sqlite-audit-evidence")
    opts = parser.parse_args()
    outdir = Path(opts.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    evidence: dict[str, object] = {
        "status": "NOT_RUN",
        "attributed": False,
        "historical_actor_identified": False,
        "scope": "disposable local fixture only; no production database",
        "python": sys.version,
    }
    audit_output = ""
    rule: list[str] | None = None
    try:
        with tempfile.TemporaryDirectory(prefix="sp-sqlite-actor-") as tmp:
            directory = Path(tmp)
            database = directory / "projects.db"
            replacement = directory / "replacement.db"
            displaced = directory / "displaced.db"
            for p, marker in ((database, "active"), (replacement, "older")):
                with sqlite3.connect(p) as con:
                    con.execute("CREATE TABLE sample (value TEXT NOT NULL)")
                    con.execute("INSERT INTO sample VALUES (?)", (marker,))
                    con.commit()

            original_stat = database.stat()
            key = f"sp_sqlite_{os.getpid()}"
            check = run("sudo", "-n", "auditctl", "-s")
            evidence["auditctl_status"] = {"exit": check.returncode, "stdout": check.stdout, "stderr": check.stderr}
            if check.returncode:
                evidence["status"] = "UNAVAILABLE_AUDIT_CONTROL"
                return 2

            # Host-level auditing is needed to attribute an unrelated process.
            # Restrict the rule to the disposable directory and relevant syscalls.
            rule_args = [
                "-F", "arch=b64", "-S", "rename", "-S", "renameat",
                "-S", "renameat2", "-S", "unlink", "-S", "unlinkat",
                "-F", f"dir={directory}", "-k", key,
            ]
            add = run("sudo", "-n", "auditctl", "-a", "always,exit", *rule_args)
            evidence["rule_install"] = {"exit": add.returncode, "stdout": add.stdout, "stderr": add.stderr}
            if add.returncode:
                evidence["status"] = "UNAVAILABLE_AUDIT_RULE"
                return 2
            rule = rule_args

            # Keep SQLite's old inode open while an independent child replaces
            # the directory entry, mirroring only the DBMOVED file-identity fact.
            conn = sqlite3.connect(database)
            try:
                conn.execute("SELECT COUNT(*) FROM sample").fetchone()
                actor_code = (
                    "import os,sys;"
                    "os.replace(sys.argv[1],sys.argv[2]);"
                    "os.replace(sys.argv[3],sys.argv[1])"
                )
                proc = subprocess.Popen(
                    [sys.executable, "-c", actor_code, str(database), str(displaced), str(replacement)],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                stdout, stderr = proc.communicate(timeout=20)
                evidence["actor"] = {
                    "pid": proc.pid, "expected_executable": sys.executable,
                    "exit": proc.returncode, "stdout": stdout, "stderr": stderr,
                }
                evidence["inode_changed"] = (original_stat.st_dev, original_stat.st_ino) != (
                    database.stat().st_dev, database.stat().st_ino
                )
            finally:
                conn.close()
            if proc.returncode or not evidence["inode_changed"]:
                evidence["status"] = "FIXTURE_FAILED"
                return 1

            # Audit records can take a moment to reach the daemon's logfile.
            matches: list[dict[str, str]] = []
            for _ in range(8):
                query = run("sudo", "-n", "ausearch", "-k", key, "-ts", "recent", "--raw")
                audit_output = query.stdout + "\n" + query.stderr
                if query.returncode == 0:
                    matches = find_attribution(query.stdout, proc.pid, database.name)
                if matches:
                    break
                time.sleep(1)
            evidence["audit_query_exit"] = query.returncode
            evidence["attributed_events"] = matches
            evidence["attributed"] = bool(matches)
            evidence["status"] = "ATTRIBUTION_CONFIRMED" if matches else "NO_PID_ATTRIBUTION"
            return 0 if matches else 1
    except Exception as exc:
        evidence["status"] = "PROBE_ERROR"
        evidence["exception"] = repr(exc)
        evidence["traceback"] = traceback.format_exc()
        return 1
    finally:
        if rule is not None:
            deletion = run("sudo", "-n", "auditctl", "-d", "always,exit", *rule)
            evidence["rule_cleanup_exit"] = deletion.returncode
            evidence["rule_cleanup_stderr"] = deletion.stderr
        (outdir / "audit-events.txt").write_text(audit_output, encoding="utf-8")
        (outdir / "result.json").write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps({
            "status": evidence["status"],
            "attributed": evidence["attributed"],
            "historical_actor_identified": False,
            "result": str(outdir / "result.json"),
        }, ensure_ascii=False))


if __name__ == "__main__":
    raise SystemExit(main())
