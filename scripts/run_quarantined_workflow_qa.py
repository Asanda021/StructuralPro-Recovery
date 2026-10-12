"""Run historical GitHub Actions contract tests in a disposable offline checkout.

Never creates .github/workflows in the actual repository and never dispatches
Actions, builds binaries, or creates releases. Any failures remain failures.
"""
from __future__ import annotations
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

_WORKFLOW_COUNT = 193
_IGNORED = {".git", ".pytest_cache", "__pycache__", ".venv", "venv", "dist", "build"}


def workflow_paths(root: Path) -> list[Path]:
    root = root.resolve(strict=True)
    live = root / ".github" / "workflows"
    if live.exists() or live.is_symlink():
        raise RuntimeError("Active or linked GitHub Actions path detected: refusing test checkout")
    quarantined = root / "recovery" / "disabled_workflows"
    if not quarantined.is_dir() or quarantined.is_symlink():
        raise RuntimeError("Quarantined workflows directory unavailable or linked")
    children = list(quarantined.iterdir())
    if any(f.is_symlink() or not f.is_file() or f.suffix.lower() not in {".yml", ".yaml"} for f in children):
        raise RuntimeError("Unexpected file type or symbolic link in quarantine")
    if len(children) != _WORKFLOW_COUNT:
        raise RuntimeError(f"Unexpected historical workflow count: {len(children)} != {_WORKFLOW_COUNT}")
    return sorted(children)


def prepare_fixture(root: Path, disposable: Path) -> Path:
    """Copy source and historical workflows into temp path, never original."""
    root = root.resolve(strict=True)
    workflows = workflow_paths(root)
    disposable = disposable.resolve(strict=True)
    if disposable == root or root in disposable.parents or disposable in root.parents:
        raise RuntimeError("Disposable fixture must not overlap the original checkout")
    checkout = disposable / "fixture"
    if checkout.exists():
        raise RuntimeError("Temporary checkout already exists")
    shutil.copytree(root, checkout, ignore=lambda folder,names: [x for x in names if x in _IGNORED], symlinks=False)
    fake = checkout / ".github" / "workflows"
    if fake.exists() or fake.is_symlink():
        raise RuntimeError("Unexpected active workflow surface in copied checkout")
    fake.mkdir(parents=True, exist_ok=False)
    for source in workflows:
        shutil.copy2(source, fake / source.name)
    if len(list(fake.iterdir())) != _WORKFLOW_COUNT:
        raise RuntimeError("Incomplete legacy contract fixture")
    return checkout


def junit_summary(report: Path) -> dict:
    root = ET.parse(report).getroot()
    cases = root.findall(".//testcase")
    failed = []
    skipped = []
    for case in cases:
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is not None:
            failed.append({"name": case.get("classname", "") + "::" + case.get("name", ""),
                           "reason": (problem.get("message", "") + " " + (problem.text or ""))[-2000:]})
        if case.find("skipped") is not None:
            skipped.append(case.get("name", ""))
    pdf = [x for x in failed if "arabic_reshaper" in x["reason"] or "موتور شکل" in x["reason"]]
    qt = [x for x in failed if "PySide6" in x["reason"]]
    unrelated = [x for x in failed if x not in pdf and x not in qt]
    return {"collected": len(cases), "passed": len(cases)-len(failed)-len(skipped),
            "failed": len(failed), "skipped": len(skipped),
            "blocked_pdf_dependency": len(pdf), "blocked_pyside6_dependency": len(qt),
            "unexpected_failures": unrelated, "failures": failed}


def run(root: Path, output: Path | None = None, log: Path | None = None) -> int:
    root = root.resolve(strict=True)
    workflow_paths(root)
    with tempfile.TemporaryDirectory(prefix="structuralpro_legacy_contract_") as d:
        checkout = prepare_fixture(root, Path(d))
        junit = Path(d) / "result.xml"
        command = [sys.executable, "-m", "pytest", "-q", "--disable-warnings", "--junitxml", str(junit)]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(checkout)
        environment.setdefault("QT_QPA_PLATFORM", "offscreen")
        proc = subprocess.run(command, cwd=checkout, env=environment, capture_output=True,
                              text=True, check=False)
        stats = junit_summary(junit) if junit.exists() else {"error": "JUnit report missing"}
        result = {"execution": "disposable_local_legacy_workflow_contract_fixture",
                  "run_utc": datetime.now(timezone.utc).isoformat(),
                  "source_checkout": str(root),
                  "source_active_workflows": 0,
                  "historical_workflows_copied_to_temp_only": _WORKFLOW_COUNT,
                  "github_actions_used": False, "build_or_release_performed": False,
                  "windows_gui_validated": False,
                  "pytest_exit_code": proc.returncode, "stats": stats,
                  "overall_green": proc.returncode == 0 and stats.get("failed") == 0}
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        if log:
            log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(proc.stdout+"\n"+proc.stderr,encoding="utf-8")
        print(f"{stats.get('passed')} passed, {stats.get('failed')} failed, {stats.get('skipped')} skipped")
        print(f"Environment blocked: PDF={stats.get('blocked_pdf_dependency')}, PySide6={stats.get('blocked_pyside6_dependency')}; unexpected={len(stats.get('unexpected_failures',[]))}")
        print("Original source .github/workflows: absent; temporary legacy fixture destroyed on exit")
        return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()
    return run(args.root,args.json,args.log)

if __name__ == "__main__":
    sys.exit(main())
