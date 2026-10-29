"""Read-only Windows native crash reproducer for original five-floor Qt oracle.

Runs the exact original pytest test in fresh processes. No application patch,
profiling hook, artificial event-loop timer or substituted engineering fixture.
Every subprocess writes its own logs, JUnit and periodically durable samples.
On crash, attempts a *sanitized* Application Error 1000 lookup; no dumps,
memory, full event messages, credentials, or machine identifiers are saved.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import psutil

TEST = "tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports"
ACCESS_VIOLATION_UNSIGNED = 0xC0000005
ARMS = {
    "integrated": TEST,
    "core": "scripts/diagnostics/p6_native_isolation_oracles.py::test_core_sqlite_full_fivefloor_without_qapplication",
    "qt": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_qt_table_events_without_service_or_sqlite",
    "dialog_read": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_real_manual_dialog_readonly_70_rows",
    "dialog_commit": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_real_manual_dialog_review_commit_70_rows",
    "dialog_lifecycle": "scripts/diagnostics/p6_native_isolation_oracles.py::test_native_real_dialog_destroy_reopen_every_fourteen_commits",
}


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".partial")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def append_jsonl(path: Path, data: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def junit_counts(file: Path) -> dict | None:
    if not file.is_file():
        return None
    try:
        cases = list(ET.parse(file).getroot().iter("testcase"))
        return {
            "collected": len(cases),
            "passed": sum(all(c.find(t) is None for t in ("failure", "error", "skipped")) for c in cases),
            "failed": sum(c.find("failure") is not None for c in cases),
            "errors": sum(c.find("error") is not None for c in cases),
            "skipped": sum(c.find("skipped") is not None for c in cases),
        }
    except (ET.ParseError, OSError) as exc:
        return {"invalid_junit": type(exc).__name__}


def process_sample(parent: psutil.Process) -> tuple[float, float]:
    rss, cpu = 0, 0
    try:
        active = [parent, *parent.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        active = [parent]
    for proc in active:
        try:
            rss += proc.memory_info().rss
            t = proc.cpu_times()
            cpu += t.user + t.system
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return round(rss / 1024 ** 2, 3), round(cpu, 3)


def exit_hex(rc: int | None) -> str | None:
    return None if rc is None else f"0x{rc & 0xFFFFFFFF:08X}"


def sanitized_fault_events(start_local: str, end_local: str) -> dict:
    """Do not persist raw Windows event logs, paths, personal data or dumps."""
    if sys.platform != "win32":
        return {"status": "unavailable_non_windows"}
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$start = [datetimeoffset]::Parse($env:P6_EVENT_START).LocalDateTime
$end = [datetimeoffset]::Parse($env:P6_EVENT_END).LocalDateTime.AddSeconds(15)
$records = @(Get-WinEvent -FilterHashtable @{
  LogName = 'Application'; Id = 1000; StartTime = $start; EndTime = $end
} -ErrorAction SilentlyContinue | Where-Object {
  $_.ProviderName -eq 'Application Error' -and $_.Message -match '(?i)python(?:w)?\.exe'
})
$labels = @('Faulting application name','Faulting module name','Exception code','Fault offset','Faulting module version')
foreach ($e in $records | Select-Object -First 5) {
  $item = @{}
  foreach ($line in ($e.Message -split '[\r\n]+')) {
    foreach ($label in $labels) {
      if ($line -match ('^\s*' + [regex]::Escape($label) + ':\s*(.+)$')) {
        $value = (($matches[1] -split ',')[0]).Trim()
        $item[$label] = $value
      }
    }
  }
  [pscustomobject]$item | ConvertTo-Json -Compress -Depth 2
}
"""
    env = os.environ.copy()
    env["P6_EVENT_START"] = start_local
    env["P6_EVENT_END"] = end_local
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", errors="replace",
            timeout=30, check=False, env=env,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "unavailable", "reason": type(exc).__name__}
    allowed = {
        "Faulting application name", "Faulting module name", "Exception code",
        "Fault offset", "Faulting module version",
    }
    events = []
    for line in result.stdout.splitlines()[:5]:
        try:
            raw = json.loads(line)
            if isinstance(raw, dict):
                sanitized = {
                    k: re.sub(r"[^A-Za-z0-9_.+\-]", "", str(v))[:100]
                    for k, v in raw.items() if k in allowed
                }
                if sanitized:
                    events.append(sanitized)
        except (ValueError, TypeError):
            continue
    return {"status": "found" if events else "no_matching_event",
            "event_id": 1000, "events": events, "event_query_exit": result.returncode}


def run_repeats(output: Path, repetitions: int, timeout_seconds: int, sample_seconds: float, test_node: str = TEST, faulthandler_timeout: int = 0) -> int:
    output.mkdir(parents=True, exist_ok=False)
    state = {
        "kind": "original_fivefloor_windows_native_crash_diagnostic",
        "source_test": test_node,
        "diagnostic_arm": next((k for k, v in ARMS.items() if v == test_node), "unknown"),
        "original_test_unmodified": True,
        "product_unchanged": True,
        "cprofile_or_pytest_instrumentation": False,
        "application_windows_event_id": 1000,
        "samples_not_true_peak_memory": True,
        "captured_memory_or_dumps": False,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "qt_qpa": os.environ.get("QT_QPA_PLATFORM"),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runs": [],
        "overall_green": False,
        "native_root_cause_proven": False,
        "pytest_faulthandler_timeout": faulthandler_timeout,
        "safety_note": "Timer zero is the safe native Windows diagnostic default. Legacy timer45 requires explicit opt-in and can reproduce a CDB second-chance Python exit fault; product root cause is not proven.",
    }
    summary = output / "summary.json"
    atomic_json(summary, state)
    for i in range(1, repetitions + 1):
        log = output / f"run-{i}.log"
        junit = output / f"run-{i}.xml"
        samples = output / f"run-{i}-samples.jsonl"
        start_at = datetime.now().astimezone().isoformat()
        start = time.monotonic()
        command = [
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "-o", f"faulthandler_timeout={faulthandler_timeout}", f"--junitxml={junit}", test_node,
        ]
        env = os.environ.copy()
        env["PYTHONFAULTHANDLER"] = "1"
        if test_node == ARMS["dialog_lifecycle"] and os.environ.get("P6_LIFECYCLE_CHECKPOINTS") == "1":
            env["P6_LIFECYCLE_CHECKPOINT_DIR"] = str(output / f"checkpoints-{i}")
        else:
            env.pop("P6_LIFECYCLE_CHECKPOINT_DIR", None)
        timed_out = False
        max_observed_rss = 0.0
        last_cpu = 0.0
        with log.open("w", encoding="utf-8") as stream:
            child = subprocess.Popen(
                command, stdout=stream, stderr=subprocess.STDOUT, env=env,
            )
            parent = psutil.Process(child.pid)
            while child.poll() is None:
                elapsed = time.monotonic() - start
                rss, cpu = process_sample(parent)
                max_observed_rss = max(max_observed_rss, rss)
                last_cpu = max(last_cpu, cpu)
                append_jsonl(samples, {
                    "elapsed_seconds": round(elapsed, 2),
                    "observed_tree_rss_mib": rss,
                    "observed_tree_cpu_seconds": cpu,
                })
                if elapsed >= timeout_seconds:
                    timed_out = True
                    try:
                        for descendant in parent.children(recursive=True):
                            descendant.kill()
                        child.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    break
                time.sleep(sample_seconds)
            try:
                rc = child.wait(timeout=12)
            except subprocess.TimeoutExpired:
                child.kill()
                rc = child.wait(timeout=12)
                timed_out = True

        end_at = datetime.now().astimezone().isoformat()
        counts = junit_counts(junit)
        success = (
            rc == 0 and not timed_out and counts is not None and
            counts.get("collected") == 1 and counts.get("passed") == 1 and
            counts.get("failed") == counts.get("errors") == counts.get("skipped") == 0
        )
        crash = exit_hex(rc) == "0xC0000005"
        entry = {
            "attempt": i,
            "started_local": start_at,
            "ended_local": end_at,
            "wall_seconds": round(time.monotonic() - start, 2),
            "exit_code": rc, "exit_hex": exit_hex(rc),
            "access_violation": crash,
            "timed_out": timed_out, "junit": counts,
            "valid_original_test_pass": success,
            "max_observed_sampled_rss_mib": max_observed_rss,
            "last_sampled_cpu_seconds": last_cpu,
            "event": {"status": "not_queried"},
            "files": [log.name, junit.name if counts is not None else None, samples.name],
        }
        # Capture only after the test exits, not while it is running.
        if sys.platform == "win32" and (not success):
            time.sleep(3)
            entry["event"] = sanitized_fault_events(start_at, datetime.now().astimezone().isoformat())
        state["runs"].append(entry)
        state["overall_green"] = all(x["valid_original_test_pass"] for x in state["runs"])
        atomic_json(summary, state)
        print(json.dumps({"attempt": i, "exit_hex": entry["exit_hex"],
                          "valid_pass": success, "access_violation": crash,
                          "windows_fault_event": entry["event"]}, ensure_ascii=False), flush=True)

    state["finished_utc"] = datetime.now(timezone.utc).isoformat()
    atomic_json(summary, state)
    return 0 if state["overall_green"] and len(state["runs"]) == repetitions else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("windows-native-evidence"))
    parser.add_argument("--repeats", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=360)
    parser.add_argument("--sample-seconds", type=float, default=5)
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--arm", choices=tuple(ARMS), default="integrated")
    parser.add_argument("--faulthandler-timeout", type=int, choices=(0,45), default=0)
    args = parser.parse_args()
    if args.self_check:
        assert exit_hex(3221225477) == "0xC0000005"
        assert exit_hex(-1073741819) == "0xC0000005"
        assert exit_hex(-11) == "0xFFFFFFF5"
        assert junit_counts(Path("this-junit-does-not-exist.xml")) is None
        print("Diagnostic safety gate PASS")
        return 0
    if not 1 <= args.repeats <= 5 or not 60 <= args.timeout_seconds <= 480 or not 2 <= args.sample_seconds <= 15:
        parser.error("Diagnostic bounds exceeded")
    if sys.platform != "win32":
        parser.error("Windows native diagnostic requires win32")
    if os.environ.get("QT_QPA_PLATFORM") != "windows":
        parser.error("Qt must use native windows platform; offscreen is not accepted")
    return run_repeats(args.output, args.repeats, args.timeout_seconds, args.sample_seconds,
                       test_node=ARMS[args.arm], faulthandler_timeout=args.faulthandler_timeout)


if __name__ == "__main__":
    sys.exit(main())
