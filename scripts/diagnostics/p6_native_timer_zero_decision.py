"""Two bounded no-debugger Windows Qt lifecycle runs with no pytest traceback TIMER.

Diagnostic only. Never patches StructuralPro product or original acceptance oracle.
Records allowlisted checkpoint events; raw process output remains ephemeral.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from scripts.diagnose_windows_native_crash import atomic_json

NODE = (
    "scripts/diagnostics/p6_native_isolation_oracles.py"
    "::test_native_real_dialog_destroy_reopen_every_fourteen_commits"
)
AV = 0xC0000005
MAX_REPEATS = 2
CHILD_TIMEOUT = 345


def junit_result(path: Path):
    if not path.is_file():
        return None
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except (OSError, ET.ParseError):
        return {"valid": False, "reason": "INVALID_JUNIT"}
    counts = {"total": len(cases)}
    for kind in ("failure", "error", "skipped"):
        counts[kind] = sum(case.find(kind) is not None for case in cases)
    counts["passed"] = sum(
        all(case.find(kind) is None for kind in ("failure", "error", "skipped"))
        for case in cases
    )
    counts["valid"] = (
        counts["total"] == counts["passed"] == 1
        and counts["failure"] == counts["error"] == counts["skipped"] == 0
    )
    return counts


def read_json(path: Path):
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def integrity(temp_root: Path):
    files = list(temp_root.rglob("projects.db"))
    if len(files) != 1:
        return "NOT_VERIFIED_DB_FILE_COUNT"
    try:
        with sqlite3.connect(files[0].as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("PRAGMA integrity_check").fetchall() == [("ok",)]:
                return "VALID_PRAGMA_INTEGRITY_CHECK"
            return "INVALID_INTEGRITY_CHECK"
    except sqlite3.Error:
        return "INTEGRITY_CHECK_ERROR"


def test_run(output: Path) -> int:
    if sys.platform != "win32" or os.getenv("QT_QPA_PLATFORM") != "windows":
        raise RuntimeError("Native Windows Qt required")
    output.mkdir(parents=True, exist_ok=False)
    state = {
        "kind": "phase6_p5_bounded_no_debugger_faulthandler_timer_zero",
        "attempt_limit": MAX_REPEATS,
        "per_process_timeout_seconds": CHILD_TIMEOUT,
        "native_debugger_used": False,
        "faulthandler_enabled": True,
        "pytest_faulthandler_timeout": 0,
        "original_test_unchanged": True,
        "product_code_unchanged": True,
        "raw_logs_uploaded": False,
        "memory_dumps_saved": False,
        "root_cause_proven": False,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "attempts": [],
        "status": "RUNNING",
    }
    atomic_json(output / "summary.json", state)
    for rep in range(1, MAX_REPEATS + 1):
        checkpoints = output / ("checkpoints-" + str(rep))
        junit = output / ("attempt-" + str(rep) + ".xml")
        probe = output / ("faulthandler-" + str(rep) + ".json")
        env = os.environ.copy()
        env["PYTHONFAULTHANDLER"] = "1"
        env["P6_EXPECT_FAULTHANDLER"] = "enabled"
        env["P6_EXPECT_DUMP_TIMEOUT"] = "0"
        env["P6_FH_PROBE"] = str(probe.resolve())
        env["P6_LIFECYCLE_CHECKPOINT_DIR"] = str(checkpoints.resolve())
        command = [
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "-o", "faulthandler_timeout=0",
            "-p", "scripts.diagnostics.p6_faulthandler_probe",
            "--junitxml=" + str(junit.resolve()),
            NODE,
        ]
        start = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="p6-timer0-private-") as private:
            # All original pytest console output and private test database remain
            # transient. Artifact only receives JUnit and sanitized checkpoints.
            command.insert(-1, "--basetemp=" + str((Path(private) / "pytest").resolve()))
            with (Path(private) / "raw-output.txt").open("wb") as stream:
                try:
                    p = subprocess.run(
                        command, cwd=Path(__file__).resolve().parents[2],
                        env=env, stdout=stream, stderr=subprocess.STDOUT,
                        check=False, timeout=CHILD_TIMEOUT,
                    )
                    code, timed_out = p.returncode, False
                except subprocess.TimeoutExpired:
                    code, timed_out = 124, True
            database_status = integrity(Path(private) / "pytest")
        j = junit_result(junit)
        last = read_json(checkpoints / "last.json")
        fh = read_json(probe)
        watchdog_verified = bool(
            fh and fh.get("pytest_plugin_present") is True
            and fh.get("before_test") is True
            and fh.get("after_test") is True
            and float(fh.get("faulthandler_timeout", -1)) == 0
        )
        valid = bool(
            code == 0 and not timed_out and j and j.get("valid") is True
            and last and last.get("event") == "ALL_DONE"
            and last.get("committed_rows") == 70
            and watchdog_verified
            and database_status == "VALID_PRAGMA_INTEGRITY_CHECK"
        )
        entry = {
            "repetition": rep,
            "wall_seconds": round(time.monotonic() - start, 2),
            "process_exit_code": code,
            "exit_hex": "0x%08X" % (code & 0xffffffff),
            "access_violation_exit_code": (code & 0xffffffff) == AV,
            "timed_out": timed_out,
            "junit": j,
            "last_checkpoint": last,
            "faulthandler_probe_verified_timer_zero": watchdog_verified,
            "sqlite_integrity": database_status,
            "boq_oracle": "70_ROW_ASSERTION_PASSED" if valid else "NOT_CONFIRMED",
            "valid_pass": valid,
        }
        state["attempts"].append(entry)
        state["status"] = "PASS_LIMITED" if all(x["valid_pass"] for x in state["attempts"]) else "RED_OR_INCOMPLETE"
        atomic_json(output / "summary.json", state)
        print(json.dumps({
            "attempt": rep, "exit": entry["exit_hex"],
            "junit_valid": bool(j and j.get("valid")),
            "checkpoint": last["event"] if last else None,
            "sqlite": database_status,
            "timer_zero_verified": watchdog_verified,
            "valid_pass": valid,
        }), flush=True)
        if not valid:
            state["status"] = "RED_STOP_AFTER_FIRST_FAILURE"
            atomic_json(output / "summary.json", state)
            break
    state["finished_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_json(output / "summary.json", state)
    return 0 if len(state["attempts"]) == MAX_REPEATS and state["status"] == "PASS_LIMITED" else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(test_run(args.output))
