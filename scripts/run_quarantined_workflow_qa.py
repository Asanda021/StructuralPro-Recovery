"""Run historical GitHub Actions contract tests in a disposable offline checkout.

Never creates .github/workflows in the actual repository and never dispatches
Actions, builds binaries, or creates releases. Any failures remain failures.
"""
from __future__ import annotations
import argparse
from contextlib import nullcontext
import hashlib
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


def _quarantined_paths(root: Path) -> list[Path]:
    root = root.resolve(strict=True)
    if (root / "recovery").is_symlink():
        raise RuntimeError("Linked workflow policy parent directory")
    quarantined = root / "recovery" / "disabled_workflows"
    if not quarantined.is_dir() or quarantined.is_symlink():
        raise RuntimeError("Quarantined workflows directory unavailable or linked")
    children = list(quarantined.iterdir())
    if any(f.is_symlink() or not f.is_file() or f.suffix.lower() not in {".yml", ".yaml"} for f in children):
        raise RuntimeError("Unexpected file type or symbolic link in quarantine")
    if len(children) != _WORKFLOW_COUNT:
        raise RuntimeError(f"Unexpected historical workflow count: {len(children)} != {_WORKFLOW_COUNT}")
    return sorted(children)


def workflow_paths(root: Path) -> list[Path]:
    root = root.resolve(strict=True)
    if (root / ".github").is_symlink():
        raise RuntimeError("Linked workflow policy parent directory")
    live = root / ".github" / "workflows"
    if live.exists() or live.is_symlink():
        raise RuntimeError("Active or linked GitHub Actions path detected: refusing test checkout")
    return _quarantined_paths(root)


def quarantine_policy(root: Path) -> dict:
    """Verify original archived bytes freshly, independently of active Actions.

    This is not zero-active source authorization; current_policy remains strict.
    """
    root = root.resolve(strict=True)
    workflows = _quarantined_paths(root)
    manifest = root / "recovery/workflow_sha256.json"
    if manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError("Reviewed quarantine SHA-256 manifest is missing or linked")
    try:
        expected = json.loads(manifest.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise RuntimeError("Invalid quarantine manifest") from exc
    actual = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in workflows}
    if expected != actual:
        raise RuntimeError("Quarantined workflow integrity mismatch")
    return {"verified_quarantined_workflows": len(workflows)}


def current_policy(root: Path) -> dict:
    """Require zero active Actions and the exact reviewed quarantine bytes.

    This is local source policy, never proof of GitHub settings or authorization.
    """
    workflow_paths(root)
    return {"active_workflows": 0, **quarantine_policy(root)}


def prepare_source(root: Path, disposable: Path) -> Path:
    """Stage offline source, excluding active Actions and all Git metadata.

    Acceptance branches may contain active workflows. They are never copied or
    executed; strict current_policy still applies to the staged zero-active tree.
    Symbolic links are rejected, never followed into an external checkout.
    """
    root = root.resolve(strict=True)
    disposable = disposable.resolve(strict=True)
    if disposable == root or root in disposable.parents or disposable in root.parents:
        raise RuntimeError("Disposable source must not overlap the original checkout")
    for path in (root / ".github", root / ".github/workflows"):
        if path.is_symlink():
            raise RuntimeError("Linked active workflow path")
    quarantine_policy(root)
    checkout = disposable / "source"
    if checkout.exists() or checkout.is_symlink():
        raise RuntimeError("Temporary source already exists")

    def ignored(folder, names):
        excluded = {x for x in names if x in _IGNORED}
        if Path(folder) == root / ".github":
            excluded.add("workflows")
        return excluded

    # Preserve links without dereferencing, then reject them before any tests.
    shutil.copytree(root, checkout, ignore=ignored, symlinks=True)
    if any(p.is_symlink() for p in checkout.rglob("*")):
        raise RuntimeError("Linked source path in disposable checkout")
    current_policy(checkout)
    return checkout


def prepare_fixture(root: Path, disposable: Path) -> Path:
    """Copy source and historical workflows into temp path, never original."""
    root = root.resolve(strict=True)
    current_policy(root)
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
    results = []
    for case in cases:
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        if problem is not None:
            failed.append({"name": case.get("classname", "") + "::" + case.get("name", ""),
                           "reason": (problem.get("message", "") + " " + (problem.text or ""))[-2000:]})
        is_skipped = case.find("skipped") is not None
        if is_skipped:
            skipped.append(case.get("name", ""))
        results.append({"name": case.get("classname", "") + "::" + case.get("name", ""),
                        "outcome": "failed" if problem is not None else "skipped" if is_skipped else "passed"})
    pdf = [x for x in failed if "arabic_reshaper" in x["reason"] or "موتور شکل" in x["reason"]]
    qt = [x for x in failed if "PySide6" in x["reason"]]
    unrelated = [x for x in failed if x not in pdf and x not in qt]
    return {"collected": len(cases), "passed": len(cases)-len(failed)-len(skipped),
            "failed": len(failed), "skipped": len(skipped),
            "blocked_pdf_dependency": len(pdf), "blocked_pyside6_dependency": len(qt),
            "unexpected_failures": unrelated, "failures": failed, "results": results}


HISTORICAL_TESTS = ('tests/test_binary_build_security_contract.py', 'tests/test_owner_approved_binary_build_workflows.py', 'tests/test_p37_real_product_deployment.py', 'tests/test_p37_release_gate_separation.py', 'tests/test_p61_p70_release_delivery.py', 'tests/test_priority_10_compliance.py', 'tests/test_priority_10_release.py', 'tests/test_priority_10_release_integrity.py', 'tests/test_priority_17_reports_excel_pdf.py', 'tests/test_priority_38_pre_release_freeze.py', 'tests/test_priority_41_ci_dependency_parity.py', 'tests/test_priority_42_windows_runtime_smoke.py', 'tests/test_priority_43_release_artifact_integrity.py', 'tests/test_priority_49_windows_installer_acceptance.py', 'tests/test_priority_9_qa.py')



def current_test_modules(root: Path, *, shard_count: int = 1, shard_index: int = 0):
    """Partition every active pytest module exactly once, without skipping tests."""
    if (type(shard_count) is not int or shard_count < 1 or
            type(shard_index) is not int or not 0 <= shard_index < shard_count):
        raise ValueError("Invalid current regression shard selection")
    tests = root / "tests"
    if not tests.is_dir():
        raise RuntimeError("Current tests directory unavailable")
    archived = set(HISTORICAL_TESTS)
    active = sorted(
        p.relative_to(root).as_posix() for p in tests.rglob("test_*.py")
        if p.is_file() and p.relative_to(root).as_posix() not in archived
    )
    if not active or shard_count > len(active):
        raise RuntimeError("Missing active test modules or too many shards")
    assigned = active[shard_index::shard_count]
    manifest_sha = hashlib.sha256(("\n".join(active) + "\n").encode("utf-8")).hexdigest()
    return active, assigned, manifest_sha


def run(root: Path, output: Path | None = None, log: Path | None = None,
        mode: str = "historical", timeout: float = 300,
        junit_output: Path | None = None, *, shard_count: int = 1,
        shard_index: int = 0) -> int:
    root = root.resolve(strict=True)
    if mode not in {"historical", "current"}:
        raise ValueError("Unknown verification mode")
    # Historical modules explicitly use tests.historical_contracts, which
    # creates and destroys one isolated checkout outside this source tree.
    # No YAML is executed and current source is never given live workflows.
    with tempfile.TemporaryDirectory(prefix="structuralpro_qa_result_") as d:
        staged = prepare_source(root, Path(d))
        policy = current_policy(staged)
        junit = Path(d) / "result.xml"
        if junit_output is not None:
            junit_output.parent.mkdir(parents=True, exist_ok=True)
            junit_output.unlink(missing_ok=True)
        command = [sys.executable, "-m", "pytest", "-vv", "--disable-warnings", "--junitxml", str(junit)]
        active_modules = selected_modules = []
        module_manifest_sha = None
        if mode == "historical":
            if shard_count != 1 or shard_index != 0:
                raise ValueError("Historical contracts cannot be sharded")
            command.extend(HISTORICAL_TESTS)
        else:
            active_modules, selected_modules, module_manifest_sha = current_test_modules(
                staged, shard_count=shard_count, shard_index=shard_index)
            command.extend(selected_modules)
        command.extend(["-o", "faulthandler_timeout=60"])
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(staged)
        environment.setdefault("QT_QPA_PLATFORM", "offscreen")
        timed_out = False
        if log is not None:
            log.parent.mkdir(parents=True, exist_ok=True)
        with (log.open("w", encoding="utf-8") if log is not None else nullcontext(None)) as live_log:
            try:
                proc = subprocess.run(command, cwd=staged, env=environment,
                                      stdout=live_log if live_log is not None else subprocess.PIPE,
                                      stderr=subprocess.STDOUT if live_log is not None else subprocess.PIPE,
                                      text=True, check=False, timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                def decoded(value):
                    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value or ""
                proc = subprocess.CompletedProcess(command, 124, decoded(exc.stdout),
                                                   decoded(exc.stderr) + f"\nQA timeout after {timeout} seconds\n")
                if live_log is not None:
                    live_log.write(proc.stderr)
                    live_log.flush()
        stats = junit_summary(junit) if junit.exists() else {"error": "JUnit report missing"}
        junit_written = junit_output is not None and junit.is_file()
        if junit_written:
            shutil.copyfile(junit, junit_output)
        result = {"execution": mode, "run_utc": datetime.now(timezone.utc).isoformat(),
                  "source_checkout": str(root), "disposable_source_policy": policy,
                  "historical_modules_excluded_from_current": list(HISTORICAL_TESTS) if mode == "current" else [],
                  "source_active_workflows": len(list((root / ".github/workflows").glob("*"))),
                  "source_active_workflows_copied": 0,
                  "historical_workflows_copied_to_temp_only": _WORKFLOW_COUNT if mode == "historical" else 0,
                  "github_actions_used": False, "build_or_release_performed": False,
                  "windows_gui_validated": False,
                  "junit_report_written": junit_written,
                  "shard_count": shard_count, "shard_index": shard_index,
                  "current_test_modules_total": len(active_modules),
                  "current_test_modules_in_shard": len(selected_modules),
                  "current_test_manifest_sha256": module_manifest_sha,
                  "pytest_exit_code": proc.returncode, "timed_out": timed_out, "timeout_seconds": timeout, "stats": stats,
                  "overall_green": proc.returncode == 0 and stats.get("failed") == 0}
        if output:
            output.parent.mkdir(parents=True,exist_ok=True)
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{stats.get('passed')} passed, {stats.get('failed')} failed, {stats.get('skipped')} skipped")
        print("Active source workflows excluded; historical YAML is static-only in disposable fixture")
        return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--junit", type=Path, help="Persist the actual pytest JUnit XML, when produced")
    parser.add_argument("--mode", choices=("current", "historical"), default="historical")
    parser.add_argument("--timeout", type=float, default=300, help="Maximum pytest wall time in seconds")
    parser.add_argument("--shard-count", type=int, default=1)
    parser.add_argument("--shard-index", type=int, default=0)
    args = parser.parse_args()
    try:
        return run(args.root,args.json,args.log,args.mode,args.timeout,args.junit,
                   shard_count=args.shard_count, shard_index=args.shard_index)
    except Exception as exc:
        # Setup errors happen before pytest/JUnit; keep them visible without
        # weakening policy, inventing test results or retaining stale XML.
        import traceback
        details=traceback.format_exc()
        if args.junit is not None:args.junit.unlink(missing_ok=True)
        if args.log is not None:
            args.log.parent.mkdir(parents=True,exist_ok=True)
            args.log.write_text(details,encoding='utf-8')
        if args.json is not None:
            args.json.parent.mkdir(parents=True,exist_ok=True)
            args.json.write_text(json.dumps({'execution':args.mode,'source_checkout':str(args.root),
                'pytest_exit_code':None,'setup_error':str(exc),'overall_green':False,
                'junit_report_written':False,'github_actions_used':False,
                'build_or_release_performed':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        annotation=str(exc)[:1600].replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error title=Quarantined QA setup::'+annotation,flush=True)
        print(details,file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
