"""Strict offline P13–P15 acceptance; never invokes CI, Windows packaging or release."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess
import sys

TESTS = (
    "tests/test_p13_p15_reviewed_engineering.py",
    "tests/test_p13_p15_ui_and_guard_wiring.py",
    "tests/test_assembly_engine.py",
    "tests/test_assembly_takeoff_persistence.py",
    "tests/test_assembly_template_expansion.py",
    "tests/test_manual_takeoff_input.py",
    "tests/test_manual_takeoff_workbench.py",
    "tests/test_reviewed_structural_five_priorities.py",
    "tests/test_reviewed_aec_priorities_6_9.py",
    "tests/test_priority_1_9_item_coverage_audit.py",
    "tests/test_stabilize_cross_workflow.py",
    "tests/test_stabilize_application_service.py",
)


def verify(out: Path | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    missing = [x for x in TESTS if not (root / x).is_file()]
    result = {
        "scope": "structuralpro-group2-P13-P15",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "test_files": list(TESTS),
        "missing": missing,
        "command": None, "exit_code": 2 if missing else None,
        "passed": None, "skipped": None, "failed": None,
        "success": False,
        "stdout": "", "stderr": "",
        "source_commit": None,
        "note": "No GUI/Windows acceptance; local Python core tests only.",
    }
    try:
        git = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                             capture_output=True, text=True, timeout=5)
        if git.returncode == 0:
            result["source_commit"] = git.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    if not missing:
        argv = [sys.executable, "-m", "pytest", "-q", "-ra",
                "-p", "no:cacheprovider", *TESTS]
        result["command"] = argv
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONPATH"] = str(root) + os.pathsep + env.get("PYTHONPATH", "")
        try:
            completed = subprocess.run(argv, cwd=root, env=env,
                                       capture_output=True, text=True,
                                       check=False, timeout=300)
            result["exit_code"] = completed.returncode
            result["stdout"] = completed.stdout[-40000:]
            result["stderr"] = completed.stderr[-20000:]
            for field in ("passed", "failed", "skipped", "xfailed", "xpassed", "error", "errors"):
                tokens = re.findall(r"\b([0-9]+)\s+" + field + r"\b",
                                    completed.stdout)
                result[field] = max((int(x) for x in tokens), default=0)
            result["success"] = (completed.returncode == 0 and
                                 result["passed"] > 0 and
                                 not any(result.get(key) for key in (
                                     "failed","skipped","xfailed","xpassed","errors","error")))
        except (OSError, subprocess.TimeoutExpired) as exc:
            result["exit_code"] = 124
            result["stderr"] = str(exc)
    else:
        result["stderr"] = "Missing required test files"
    if out is not None:
        out = out if out.is_absolute() else root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    print(result["stdout"])
    print(result["stderr"], file=sys.stderr)
    if not result["success"]:
        print("FAIL-CLOSED: گروه دوم هنوز گواه پذیرش کامل ندارد.", file=sys.stderr)
    return 0 if result["success"] else (result["exit_code"] or 3)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Offline P13-P15 core tests")
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args()
    raise SystemExit(verify(args.report))
