"""Bounded no-profiler baseline of the original five-floor Qt acceptance test.

Only process-level polling, not sys.setprofile or cProfile. One original pytest
test per fresh Python interpreter, separate SQLite/tmp fixtures and real JUnit.
No original test, assertion, application file, timeout or fixture is edited.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

import psutil

TEST = "tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_sample(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def process_stats(parent: psutil.Process) -> tuple[float, float]:
    rss, cpu = 0, 0
    try:
        processes = [parent, *parent.children(recursive=True)]
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        processes = [parent]
    for proc in processes:
        try:
            rss += proc.memory_info().rss
            times = proc.cpu_times()
            cpu += times.user + times.system
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return round(rss / 1024**2, 3), round(cpu, 3)


def parse_junit(path: Path) -> dict | None:
    if not path.is_file():
        return None
    cases = list(ET.parse(path).getroot().iter("testcase"))
    return {
        "case_count": len(cases),
        "failed": sum(node.find("failure") is not None for node in cases),
        "errors": sum(node.find("error") is not None for node in cases),
        "skipped": sum(node.find("skipped") is not None for node in cases),
        "passed": sum(all(node.find(key) is None for key in ("failure", "error", "skipped"))
                      for node in cases),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=480)
    parser.add_argument("--interval-seconds", type=float, default=5)
    parser.add_argument("--output", type=Path, default=Path("baseline-fivefloor"))
    args = parser.parse_args()
    if not 1 <= args.repeats <= 3 or not 30 <= args.timeout_seconds <= 600:
        parser.error("Unsafe diagnostic repeat/timeout bounds")
    if not 1 <= args.interval_seconds <= 15:
        parser.error("Unsafe sampling interval")
    out = args.output
    out.mkdir(parents=True, exist_ok=False)
    summary = {
        "policy": "no_cprofile_original_pytest_three_fresh_processes_v1",
        "source_test": TEST, "python": sys.version,
        "platform": sys.platform, "qt_qpa": os.environ.get("QT_QPA_PLATFORM"),
        "samples_are_instantaneous_not_true_peak_memory": True,
        "test_is_original_unmodified": True,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "runs": [],
    }
    write_json(out / "summary.json", summary)
    any_bad = False
    for repeat in range(1, args.repeats + 1):
        junit = out / f"run-{repeat}.xml"
        log = out / f"run-{repeat}.log"
        snapshots = out / f"run-{repeat}-samples.jsonl"
        cmd = [
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "-o", "faulthandler_timeout=60",
            f"--junitxml={junit}", TEST,
        ]
        started = time.monotonic()
        with log.open("w", encoding="utf-8") as stream:
            proc = subprocess.Popen(
                cmd, stdout=stream, stderr=subprocess.STDOUT,
                env=os.environ.copy(),
            )
            parent = psutil.Process(proc.pid)
            max_sample_rss = 0.0
            last_cpu = 0.0
            did_timeout = False
            while proc.poll() is None:
                elapsed = time.monotonic() - started
                rss, cpu = process_stats(parent)
                max_sample_rss = max(rss, max_sample_rss)
                last_cpu = max(cpu, last_cpu)
                append_sample(snapshots, {
                    "repeat": repeat, "elapsed_seconds": round(elapsed, 2),
                    "sampled_process_tree_rss_mib": rss,
                    "sampled_process_tree_cpu_seconds": cpu,
                })
                if elapsed >= args.timeout_seconds:
                    did_timeout = True
                    try:
                        for child in parent.children(recursive=True):
                            child.kill()
                        proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                    break
                time.sleep(args.interval_seconds)
            try:
                exit_code = proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill()
                exit_code = proc.wait(timeout=8)
                did_timeout = True
        duration = round(time.monotonic() - started, 2)
        try:
            counts = parse_junit(junit)
        except (ET.ParseError, OSError) as exc:
            counts = {"malformed_junit": str(exc)}
        valid = (exit_code == 0 and not did_timeout and counts is not None
                 and counts.get("case_count") == 1 and counts.get("passed") == 1
                 and counts.get("failed") == 0 and counts.get("errors") == 0
                 and counts.get("skipped") == 0)
        entry = {
            "repeat": repeat, "exit_code": exit_code, "timed_out": did_timeout,
            "wall_seconds": duration,
            "maximum_observed_sampled_rss_mib": round(max_sample_rss, 3),
            "last_sampled_process_tree_cpu_seconds": last_cpu,
            "junit": counts, "valid_original_oracle_pass": valid,
            "files": {"log": log.name, "junit": junit.name, "samples": snapshots.name},
        }
        summary["runs"].append(entry)
        summary["all_passed"] = all(x["valid_original_oracle_pass"] for x in summary["runs"])
        write_json(out / "summary.json", summary)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
        any_bad = any_bad or not valid
        if any_bad:
            break
    summary["completed_utc"] = datetime.now(timezone.utc).isoformat()
    write_json(out / "summary.json", summary)
    return 1 if any_bad or len(summary["runs"]) != args.repeats else 0


if __name__ == "__main__":
    raise SystemExit(main())
