"""Independent synthetic second-chance AV to validate CDB capture, never product code.

Deliberately crashes only an isolated throwaway Python child under Microsoft CDB.
Private debugger stdout exists temporarily and is never archived. The GitHub
artifact contains only allowlisted exception details and module!symbol strings.
"""
from __future__ import annotations
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from p6_native_cdb_trace import debugger, sanitize, persist, MARKER


def control(output: Path) -> int:
    output.mkdir(parents=True, exist_ok=False)
    exe = debugger()
    state = {
        "kind": "synthetic_second_chance_access_violation_cdb_control",
        "synthetic_only": True,
        "production_source_executed": False,
        "debugger_available": bool(exe),
        "expected_code": "0xC0000005",
        "memory_dump_written": False,
        "raw_debugger_logs_uploaded": False,
        "test_control_passed": False,
        "started_utc":datetime.now(timezone.utc).isoformat(),
    }
    persist(output/"control.json", state)
    if not exe:
        state["status"]="BLOCKED_CDB_ABSENT"
        persist(output/"control.json",state)
        return 2
    # A deliberately unhandled, NONCONTINUABLE Windows SEH access violation.
    # ctypes makes the documented kernel32 RaiseException call; the process
    # is isolated under the debugger, never in the active CI Python process.
    code = ("import ctypes; "
            "ctypes.windll.kernel32.RaiseException("
            "ctypes.c_ulong(0xC0000005), ctypes.c_ulong(1), "
            "ctypes.c_ulong(0), None); "
            "raise SystemExit('control did not fault')")
    command = f'sxd -c2 ".echo {MARKER}; .lastevent; .ecxr; kn 32; q" av; g'
    cmd = [str(exe), "-G", "-c", command, sys.executable, "-c", code]
    with tempfile.TemporaryDirectory(prefix="p6-cdb-control-private-") as private:
        raw = Path(private)/"private.txt"
        with raw.open("wb") as stream:
            child = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT)
            try:
                exit_code=child.wait(timeout=65)
                timed_out=False
            except subprocess.TimeoutExpired:
                child.kill()
                exit_code=child.wait(timeout=10)
                timed_out=True
        parsed=sanitize(raw.read_bytes()[:5_000_000].decode("utf8", errors="replace"))
    state.update({
        "debugger_exit_code":exit_code,
        "timed_out":timed_out,
        "control_second_chance_marked":parsed["second_chance_marker"],
        "exception_code_verified":parsed["exception_codes"]==["0xC0000005"],
        "stack_symbols":parsed["native_stack_symbols"][:20],
        "native_stack_available":parsed["native_stack_available"],
        "root_cause_proven_for_product":False,
        "finished_utc":datetime.now(timezone.utc).isoformat(),
    })
    state["test_control_passed"]=bool(
        not timed_out and state["control_second_chance_marked"]
        and state["exception_code_verified"] and state["native_stack_available"]
    )
    state["status"]="CONTROL_PASS" if state["test_control_passed"] else "CONTROL_FAIL"
    persist(output/"control.json",state)
    print(json.dumps({
        "control_status":state["status"],
        "observed_native":state["control_second_chance_marked"],
        "observed_0xc0000005":state["exception_code_verified"],
        "stack_available":state["native_stack_available"],
        "symbols":state["stack_symbols"][:8],
    }),flush=True)
    return 0 if state["test_control_passed"] else 1


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    if sys.platform!="win32" or os.environ.get("QT_QPA_PLATFORM")!="windows":
        parser.error("Windows native Qt CI is required")
    raise SystemExit(control(args.output))
