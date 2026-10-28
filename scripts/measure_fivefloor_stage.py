"""Diagnostic-only staged timing for the original five-floor Qt pytest oracle.

Measures calls without editing product files, fixture, assertions or quantities.
Writes crash-survivable JSON snapshots; a missing JUnit is NEVER a pass.
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

TEST = "tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports"
TRACKED = ("catalog", "verified", "clean", "deepcopy", "evaluate_rows", "fingerprints")
_STATS = defaultdict(lambda: {"calls": 0, "total_ns": 0, "max_ns": 0, "exceptions": 0, "inflight": 0})
_ORIGINAL = {}
_LAST_FLUSH = 0.0


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


def _flush(force=False):
    global _LAST_FLUSH
    name = os.environ.get("P6_STAGE_JOURNAL")
    if not name:
        return
    now = time.monotonic()
    if not force and now - _LAST_FLUSH < 2:
        return
    _LAST_FLUSH = now
    _write_json(Path(name), {
        "kind": "instrumentation_snapshot_not_pass",
        "updated_utc": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "stats": {
            key: {**val, "total_seconds": round(val["total_ns"] / 1e9, 6),
                  "max_seconds": round(val["max_ns"] / 1e9, 6)}
            for key, val in sorted(_STATS.items())
        },
        "note": "Nested inclusive timings cannot be summed. Inflight calls do not have a completed duration.",
    })


def _wrap(name, original):
    @wraps(original)
    def measured(*args, **kwargs):
        entry = _STATS[name]
        entry["inflight"] += 1
        _flush()
        started = time.perf_counter_ns()
        try:
            return original(*args, **kwargs)
        except BaseException:
            entry["exceptions"] += 1
            raise
        finally:
            elapsed = time.perf_counter_ns() - started
            entry["inflight"] -= 1
            entry["calls"] += 1
            entry["total_ns"] += elapsed
            entry["max_ns"] = max(entry["max_ns"], elapsed)
            _flush()
    return measured


def pytest_collection_finish(session):
    """Patch references only inside the disposable pytest interpreter."""
    from core.takeoff import manual_formula_register as register
    for name in TRACKED:
        original = getattr(register, name)
        _ORIGINAL[name] = original
        setattr(register, name, _wrap(name, original))
    # Existing 'from module import symbol' bindings may have been captured
    # while pytest collected the test; preserve their linkage transparently.
    for module_name, module in tuple(sys.modules.items()):
        if not module_name.startswith(("app.", "core.")) or not hasattr(module, "__dict__"):
            continue
        for attr, value in tuple(module.__dict__.items()):
            if attr in ("catalog", "verified", "clean", "fingerprints", "evaluate_rows") and value is _ORIGINAL[attr]:
                module.__dict__[attr] = getattr(register, attr)
    _flush(force=True)


def pytest_sessionfinish(session, exitstatus):
    _flush(force=True)


def _junit(path):
    if not path.is_file():
        return None
    try:
        cases = list(ET.parse(path).getroot().iter("testcase"))
    except (ET.ParseError, OSError) as exc:
        return {"invalid": str(exc)}
    return {
        "cases": len(cases),
        "passed": sum(all(c.find(k) is None for k in ("failure", "error", "skipped")) for c in cases),
        "failed": sum(c.find("failure") is not None for c in cases),
        "errors": sum(c.find("error") is not None for c in cases),
        "skipped": sum(c.find("skipped") is not None for c in cases),
    }


def _catalog_isolated(out, calls=200):
    """Run untouched product catalog on its actual 85-family inventory."""
    from core.takeoff.manual_formula_register import catalog
    durations = []
    digest = None
    for _ in range(calls):
        began = time.perf_counter_ns()
        data = catalog()
        durations.append(time.perf_counter_ns() - began)
        if len(data) != 85:
            raise ValueError("Original catalog family count changed")
        hash_now = hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if digest is not None and digest != hash_now:
            raise ValueError("Original catalog result changed during isolated read")
        digest = hash_now
    durations.sort()
    result = {"calls": calls, "mean_ms": round(sum(durations) / calls / 1e6, 4),
              "p95_ms": round(durations[int(0.95 * (calls - 1))] / 1e6, 4),
              "max_ms": round(durations[-1] / 1e6, 4),
              "digest_sha256": digest, "result_is_original_85_family_catalog": True}
    _write_json(out, result)
    return result


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("stage-fivefloor"))
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=int, default=480)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 3 or not 30 <= args.timeout_seconds <= 600:
        parser.error("Unsafe diagnostic bounds")
    args.output.mkdir(parents=True, exist_ok=False)
    summary = {"source_test": TEST, "original_test_unmodified": True, "instrumentation": "wrappers_only_no_product_edit",
               "start_utc": datetime.now(timezone.utc).isoformat(),
               "qt_qpa": os.environ.get("QT_QPA_PLATFORM"), "runs": [], "all_passed": False}
    _write_json(args.output / "summary.json", summary)
    try:
        summary["isolated_catalog"] = _catalog_isolated(args.output / "catalog-isolated.json")
    except Exception as exc:
        summary["isolated_catalog_error"] = repr(exc)
        _write_json(args.output / "summary.json", summary)
        raise
    for i in range(1, args.repeats + 1):
        junit = args.output / f"run-{i}.xml"
        log = args.output / f"run-{i}.log"
        journal = args.output / f"run-{i}-journal.json"
        command = [sys.executable, "-m", "pytest", "-p", "scripts.measure_fivefloor_stage",
                   "-q", "--disable-warnings", "-o", "faulthandler_timeout=60", f"--junitxml={junit}", TEST]
        env = os.environ.copy()
        env["P6_STAGE_JOURNAL"] = str(journal.resolve())
        start = time.monotonic()
        with log.open("w", encoding="utf-8") as stream:
            try:
                finished = subprocess.run(command, env=env, stdout=stream, stderr=subprocess.STDOUT,
                                          check=False, timeout=args.timeout_seconds)
                rc, timed_out = finished.returncode, False
            except subprocess.TimeoutExpired:
                rc, timed_out = 124, True
        counts = _junit(junit)
        good = (rc == 0 and not timed_out and counts is not None and
                counts.get("cases") == 1 and counts.get("passed") == 1 and
                counts.get("failed") == 0 and counts.get("errors") == 0 and
                counts.get("skipped") == 0 and journal.is_file())
        entry = {"repeat": i, "wall_seconds": round(time.monotonic() - start, 3),
                 "exit_code": rc, "timed_out": timed_out, "junit": counts,
                 "valid_original_oracle_pass": good, "journal_present": journal.is_file(),
                 "files": [log.name, junit.name, journal.name]}
        summary["runs"].append(entry)
        summary["all_passed"] = all(run["valid_original_oracle_pass"] for run in summary["runs"])
        _write_json(args.output / "summary.json", summary)
        print(json.dumps(entry, ensure_ascii=False), flush=True)
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(_main())
