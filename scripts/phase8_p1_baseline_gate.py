#!/usr/bin/env python3
"""Read-only Phase 8 Priority 1 source freeze gate.

This verifies repository ancestry and that no product code changed after the
last successful full Linux/Windows source-pinned suite. It does NOT establish
semantic parity with divergent historical PRs or physical release readiness.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "acceptance" / "phase8_p1" / "BASELINE_MANIFEST.json"


def git(*args: str, acceptable: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(
        ["git", *args], cwd=ROOT, encoding="utf-8", errors="replace",
        capture_output=True, check=False,
    )
    if result.returncode not in acceptable:
        raise ValueError(
            f"git {args[0]} failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def ancestor(older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=ROOT, capture_output=True, check=False,
    )
    if result.returncode not in (0, 1):
        raise ValueError(f"git merge-base exit {result.returncode}")
    return result.returncode == 0


def changed_names(older: str, newer: str) -> set[str]:
    output = git("diff", "--name-only", "--no-renames", older, newer, "--")
    return set(output.splitlines()) if output else set()


def main() -> int:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        if manifest["schema_version"] != "1.0":
            raise ValueError("unknown baseline manifest version")
        if manifest["repository"] != "Asanda021/StructuralPro-Recovery":
            raise ValueError("incorrect repository ownership")
        if manifest["priority"] != "P8-P1":
            raise ValueError("incorrect priority")
        if len(manifest["selected_pr_chain"]) != len(set(manifest["selected_pr_chain"])):
            raise ValueError("duplicate PR in selected path")
        if not (manifest["selected_pr_chain"][-1] == manifest["selected_terminal_pr"] == 40):
            raise ValueError("terminal PR is not the frozen Phase 7 source")
        if manifest["protected_actions"] != {
            "merge": False, "main_write": False, "exe": False,
            "installer": False, "release": False,
            "manual_workflow_dispatch": False,
        }:
            raise ValueError("owner's safeguards have been weakened")

        main_sha = manifest["main_sha"]
        tested = manifest["tested_source_sha"]
        baseline = manifest["selected_source_baseline_sha"]
        head = git("rev-parse", "HEAD")
        if any(len(s) != 40 or any(c not in "0123456789abcdef" for c in s)
               for s in (main_sha, tested, baseline, head)):
            raise ValueError("noncanonical Git SHA")
        for sha in (main_sha, tested, baseline):
            git("cat-file", "-e", sha + "^{commit}")
        if not all((
            ancestor(main_sha, tested),
            ancestor(tested, baseline),
            ancestor(baseline, head),
        )):
            raise ValueError("ancestry or frozen baseline broken")
        expected_baseline_changes = set(manifest["post_ci_pre_p8_paths"])
        baseline_changes = changed_names(tested, baseline)
        if baseline_changes != expected_baseline_changes:
            raise ValueError(
                "unexpected files between tested and candidate source: "
                + repr(sorted(baseline_changes ^ expected_baseline_changes))
            )
        permitted = set(manifest["allowed_post_ci_paths"])
        observed = changed_names(tested, head)
        unauthorized = observed - permitted
        if unauthorized:
            raise ValueError(
                "product or unapproved file changed after verified CI: "
                + repr(sorted(unauthorized))
            )
        if not (ROOT / "docs" / "acceptance" / "phase8_p1" / "REPORT.fa.md").is_file():
            raise ValueError("audit report absent")
        if manifest["release_status"] != "NO_GO":
            raise ValueError("source freeze alone is not release approval")
        print(json.dumps({
            "gate": "P8_P1_FROZEN_SOURCE",
            "status": "PASS_READ_ONLY_SOURCE_INTEGRITY",
            "tested_sha": tested,
            "candidate_sha": baseline,
            "audit_head_sha": head,
            "changed_paths_since_successful_ci": sorted(observed),
            "code_changes_since_successful_ci": 0,
            "release_status": "NO_GO",
            "limitations": "No physical UAT, Office, printer, divergent-PR semantic parity or merge authority.",
        }, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"P8_P1_FROZEN_SOURCE_FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
