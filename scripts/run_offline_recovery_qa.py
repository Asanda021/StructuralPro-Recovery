"""Run verified StructuralPro source tests with no GitHub Actions or builds.

The default suite is intentionally *targeted*, not a claim that the full
repository or Windows GUI has passed. '--full' runs all collected pytest tests
and preserves the real nonzero exit code and failure summary.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TARGETS = (
    "tests/test_recovery_concurrent_takeoff.py",
    "tests/test_finish_recovery_pr481.py",
    "tests/test_finish_takeoff_assemblies.py",
    "tests/test_priority_37_stabilization.py",
    "tests/test_priority_68_store_concurrency.py",
)


def run(*, root: Path, full: bool = False, json_output: Path | None = None,
        log_output: Path | None = None) -> int:
    root = Path(root).resolve(strict=True)
    if not (root / "core/platform/application.py").is_file():
        raise FileNotFoundError("StructuralPro source checkout is missing")
    if not full:
        missing = [target for target in _TARGETS if not (root / target).is_file()]
        if missing:
            raise FileNotFoundError("Missing required regression tests: " + ", ".join(missing))
    args = [sys.executable, "-m", "pytest", "-q", "--disable-warnings"]
    if not full:
        args.extend(_TARGETS)
    env = {**os.environ, "PYTHONPATH": str(root)}
    proc = subprocess.run(args, cwd=root, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          check=False)
    result = {
        "run_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "full_repository" if full else "targeted_offline_concurrency_and_finishing",
        "actual_exit_code": proc.returncode,
        "success": proc.returncode == 0,
        "uses_github_actions": False,
        "build_or_release_performed": False,
        "windows_gui_validated": False,
        "tested_paths": ["all pytest-collected tests"] if full else list(_TARGETS),
        "pytest_summary_tail": proc.stdout.splitlines()[-1] if proc.stdout else "",
    }
    if log_output:
        log_output.parent.mkdir(parents=True, exist_ok=True)
        log_output.write_text(proc.stdout, encoding="utf-8")
    if json_output:
        json_output.parent.mkdir(parents=True, exist_ok=True)
        json_output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(proc.stdout[-16000:], end="")
    print("\nQA result:", json.dumps(result, ensure_ascii=False))
    return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="StructuralPro offline source verification")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--full", action="store_true", help="Run entire test suite; preserve failures")
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--log-output", type=Path)
    options = parser.parse_args()
    return run(root=options.root, full=options.full,
               json_output=options.json_output, log_output=options.log_output)


if __name__ == "__main__":
    sys.exit(main())