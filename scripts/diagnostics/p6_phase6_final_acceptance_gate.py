"""Fail-closed evidence gate for the existing Phase-6 P1-P5 functional tests.

The gate owns NO new business logic. It accepts only valid pytest XML from
the same checked-out source commit, with every planned test module represented.
It cannot certify final release or resolve the previously observed native AV.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

SHELL_AND_VIEWS = (
    "test_phase6_p1_shell",
    "test_phase6_p2_source_mesh3d",
    "test_phase6_p2_real_ifc_3d",
    "test_phase6_p2_e2_restore",
    "test_phase6_p3_four_view_final",
    "test_phase6_p3_full_verified_boq",
    "test_phase6_p3_real_project_bridge",
    "test_phase6_p5_e5_docks",
)
OPERATIONS = (
    "test_phase6_p4_contextual_takeoff",
    "test_phase6_p4_model_isolation",
    "test_phase6_p5_e3_templates",
    "test_phase6_p5_e3_ui",
    "test_phase6_p5_e4_sessions",
    "test_phase6_p5_e4_snapshot_race",
    "test_phase6_p5_e6_ifc_transfer_history",
    "test_phase6_p5_e6_live_context",
)
PERSISTENCE_REPORTS = (
    "test_phase5_backup_recovery",
    "test_phase4_sqlite_open_integrity",
    "test_phase4_sqlite_rescue",
    "test_phase1_manual_report_formats",
    "test_manual_formula_reports",
    "test_recovery_office_export_contract",
)
WINDOWS_ONLY = ("test_phase4_sqlite_windows_native",)
DPI = ("test_phase6_p5_e5_docks", "test_phase6_p1_shell")

SUITES = {
    "views": SHELL_AND_VIEWS,
    "operations": OPERATIONS,
    "persistence": PERSISTENCE_REPORTS,
    "win-db": WINDOWS_ONLY,
    "win-dpi150": DPI,
    "win-dpi200": DPI,
}
MIN_CASES = {"views": 10, "operations": 15, "persistence": 9,
             "win-db": 2, "win-dpi150": 3, "win-dpi200": 3}


def check_xml(path: Path, required: tuple[str, ...], floor: int) -> dict:
    info = {"file": path.name, "present": path.is_file(), "valid": False}
    if not path.is_file():
        info["blocker"] = "MISSING_JUNIT"
        return info
    try:
        raw = path.read_bytes()
        root = ET.fromstring(raw)
        cases = list(root.iter("testcase"))
    except (ET.ParseError, OSError, ValueError):
        info["blocker"] = "INVALID_JUNIT"
        return info
    names = [str(x.attrib.get("classname", "")) + "::" +
             str(x.attrib.get("name", "")) for x in cases]
    failures = sum(x.find("failure") is not None for x in cases)
    errors = sum(x.find("error") is not None for x in cases)
    skips = sum(x.find("skipped") is not None for x in cases)
    missing = [stem for stem in required if not any(stem in n for n in names)]
    info.update({
        "sha256": hashlib.sha256(raw).hexdigest(),
        "tests": len(cases), "passed": len(cases)-failures-errors-skips,
        "failed": failures, "errors": errors, "skipped": skips,
        "missing_modules": missing,
        "valid": not missing and len(cases) >= floor
                 and not any((failures,errors,skips)),
    })
    if not info["valid"]:
        info["blocker"] = "INCOMPLETE_OR_RED_TEST_COVERAGE"
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=("windows", "linux"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    needed = ("views", "operations", "persistence")
    if args.platform == "windows":
        needed += ("win-db", "win-dpi150", "win-dpi200")
    results = {key: check_xml(Path(f"p6-final-{key}.xml"),
                              SUITES[key], MIN_CASES[key]) for key in needed}
    commit = subprocess.check_output(["git","rev-parse","HEAD"], text=True).strip()
    state = {
        "kind": "phase6_p1_p5_targeted_acceptance_evidence_v1",
        "source_sha": commit,
        "platform": args.platform,
        "native_qt": args.platform == "windows",
        "python": platform.python_version(),
        "suites": results,
        "total_cases": sum(x.get("tests",0) for x in results.values()),
        "total_passed": sum(x.get("passed",0) for x in results.values()),
        "missing_junit_count": sum(not x["present"] for x in results.values()),
        "all_required_suites_pass": all(x["valid"] for x in results.values()),
        "historical_native_windows_crash_closed": False,
        "office_desktop_automation_tested": False,
        "physical_windows_uat_tested": False,
        "phase6_final_release_gate_complete": False,
    }
    args.output.write_text(json.dumps(state, indent=2, ensure_ascii=False),encoding="utf-8")
    print(json.dumps({
        "platform": args.platform, "source_sha":commit,
        "total_cases":state["total_cases"], "total_passed":state["total_passed"],
        "all_required_suites_pass":state["all_required_suites_pass"],
        "suites":{k:{"tests":v.get("tests"),"passed":v.get("passed"),
                      "blocker":v.get("blocker"),"missing_modules":v.get("missing_modules")}
                  for k,v in results.items()},
    },ensure_ascii=False), flush=True)
    return 0 if state["all_required_suites_pass"] else 1


if __name__=="__main__":
    raise SystemExit(main())
