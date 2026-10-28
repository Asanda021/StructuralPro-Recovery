"""Fail-closed Windows-shard union verification against full Linux JUnit."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET


def cases(path: Path):
    result = {}
    for case in ET.parse(path).getroot().findall(".//testcase"):
        key = (case.get("classname"), case.get("name"))
        if key in result:
            raise ValueError(f"Duplicate JUnit case inside {path}: {key}")
        outcome = "error" if case.find("error") is not None else (
            "failed" if case.find("failure") is not None else (
                "skipped" if case.find("skipped") is not None else "passed"))
        result[key] = outcome
    if not result:
        raise ValueError(f"No cases found in {path}")
    return result


def verify(root: Path, shard_count: int = 3):
    """No missing/extra/duplicated test cases; all shards must genuinely pass."""
    if type(shard_count) is not int or shard_count < 1:
        raise ValueError("Invalid shard count")
    linux = root / "p6-broad-current-linux"
    state = json.loads((linux / "phase6-broad-current.json").read_text(encoding="utf-8"))
    expected = cases(linux / "phase6-broad-current.xml")
    if (state.get("overall_green") is not True or
            state.get("pytest_exit_code") != 0 or
            state.get("timed_out") is not False or
            state.get("junit_report_written") is not True or
            len(expected) != state.get("stats", {}).get("collected")):
        raise ValueError("Full Linux regression has not passed with valid JUnit")
    if any(x in {"failed", "error"} for x in expected.values()):
        raise ValueError("Linux JUnit contains failures")
    manifest = state.get("current_test_manifest_sha256")
    if not isinstance(manifest, str) or len(manifest) != 64:
        raise ValueError("Linux module manifest missing")
    combined, module_total = {}, 0
    for index in range(shard_count):
        folder = root / f"p6-broad-current-windows-{index}"
        data = json.loads((folder / "phase6-broad-current-windows.json").read_text(encoding="utf-8"))
        found = cases(folder / "phase6-broad-current-windows.xml")
        if (data.get("shard_count") != shard_count or data.get("shard_index") != index or
                data.get("current_test_manifest_sha256") != manifest or
                data.get("current_test_modules_total") != state.get("current_test_modules_total") or
                data.get("overall_green") is not True or
                data.get("pytest_exit_code") != 0 or
                data.get("timed_out") is not False or
                data.get("junit_report_written") is not True or
                data.get("stats", {}).get("collected") != len(found)):
            raise ValueError(f"Windows shard {index} is not verified")
        if any(x in {"failed", "error"} for x in found.values()):
            raise ValueError(f"Windows shard {index} has test failures")
        duplicate = set(combined) & set(found)
        if duplicate:
            raise ValueError(f"Cross-shard duplicated cases: {sorted(duplicate)[:3]}")
        combined.update(found)
        module_total += data["current_test_modules_in_shard"]
    if module_total != state["current_test_modules_total"]:
        raise ValueError("Module partition incomplete")
    missing, unexpected = set(expected)-set(combined), set(combined)-set(expected)
    if missing or unexpected:
        raise ValueError(f"Cross-platform JUnit mismatch: missing={len(missing)}, unexpected={len(unexpected)}")
    return {
        "verified": True, "shards": shard_count, "modules": module_total,
        "case_count": len(combined), "module_manifest_sha256": manifest,
        "windows_passed": sum(v == "passed" for v in combined.values()),
        "windows_skipped": sum(v == "skipped" for v in combined.values()),
        "linux_passed": sum(v == "passed" for v in expected.values()),
        "linux_skipped": sum(v == "skipped" for v in expected.values()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--shard-count", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    outcome = verify(args.root, args.shard_count)
    if args.output:
        args.output.write_text(json.dumps(outcome, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("::notice title=Complete sharded broad coverage::" + json.dumps(outcome))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
