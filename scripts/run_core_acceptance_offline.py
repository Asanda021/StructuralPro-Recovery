"""Offline acceptance gate for StructuralPro priorities 10–12.

Usage:
    python scripts/run_core_acceptance_offline.py
    python scripts/run_core_acceptance_offline.py --report artifacts/core-acceptance.json

Does not install packages, access the network, start GitHub Actions, create a
Windows executable, package a release or modify any repository branch.
An unavailable test module is FAIL, never SKIP/PASS.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

TEST_FILES = (
    "tests/test_stabilize_integrate_priorities_10_12.py",
    "tests/test_stabilize_cross_workflow.py",
    "tests/test_stabilize_backup_integrity.py",
    "tests/test_stabilize_application_service.py",
    "tests/test_reviewed_structural_five_priorities.py",
    "tests/test_reviewed_aec_priorities_6_9.py",
    "tests/test_priority_1_9_item_coverage_audit.py",
    "tests/test_beam_detail_workflow.py",
    "tests/test_stirrup_zones.py",
)


def run(report_path: Path | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [path for path in TEST_FILES if not (root / path).is_file()]
    result = {
        "project": "StructuralPro-Recovery",
        "scope": "priorities 10 to 12; core regression, no GUI/build",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "runner": sys.version.split()[0],
        "tests": list(TEST_FILES),
        "missing_files": missing,
        "command": [],
        "return_code": None,
        "stdout": "",
        "stderr": "",
        "passed": None,
    }
    if missing:
        result["return_code"] = 2
        result["stderr"] = "Required tests are missing; acceptance is blocked."
    else:
        command = [sys.executable, "-m", "pytest", "-q", "-ra",
                   "-p", "no:cacheprovider", "--disable-warnings", *TEST_FILES]
        result["command"] = command
        environment = dict(os.environ)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PYTHONPATH"] = str(root) + os.pathsep + environment.get("PYTHONPATH", "")
        try:
            completed = subprocess.run(
                command, cwd=root, env=environment, capture_output=True,
                text=True, timeout=240, check=False,
            )
            result["return_code"] = completed.returncode
            result["stdout"] = completed.stdout[-25000:]
            result["stderr"] = completed.stderr[-12000:]
            # pytest exit 0 allows skipped/xfail tests; engineering acceptance
            # requires a positive PASS count and zero not-executed cases.
            if completed.returncode == 0:
                has_passed = re.search(r"(?m)\b[1-9][0-9]* passed\b", completed.stdout)
                incomplete = re.search(
                    r"(?m)\b[1-9][0-9]* (?:skipped|xfailed|xpassed)\b",
                    completed.stdout,
                )
                if not has_passed or incomplete:
                    result["return_code"] = 3
                    result["stderr"] += (
                        "\nEngineering acceptance requires >=1 PASS and "
                        "no SKIP/XFAIL/XPASS, even when pytest exit code is 0."
                    )
        except subprocess.TimeoutExpired as exc:
            result["return_code"] = 124
            result["stderr"] = f"Acceptance timed out: {exc}"
        except OSError as exc:
            result["return_code"] = 125
            result["stderr"] = f"Cannot run Python tests: {exc}"
    result["passed"] = result["return_code"] == 0
    if report_path is not None:
        output = (root / report_path).resolve() if not report_path.is_absolute() else report_path
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"نتیجه آزمون در {output} ثبت شد.")
    if result["stdout"]:
        print(result["stdout"])
    if result["stderr"]:
        print(result["stderr"], file=sys.stderr)
    if not result["passed"]:
        print("BLOCKED: group 10–12 acceptance is not complete.", file=sys.stderr)
    return int(result["return_code"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Strict offline P10–12 acceptance")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    raise SystemExit(run(args.report))
