"""Read-only, fail-closed StructuralPro recovery audit for historical PR #462..#481.

Does not fetch, modify, or merge GitHub refs. No build/release side effects.
Usage:
    python scripts/audit_historical_recovery.py --checkout . \
      --historical-zip /path/to/StructuralPro-a07cf....zip \
      --local-bundle /path/to/recovery.bundle --output audit.json
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path

PR481_EXPECTED_TESTS = (
    "tests/test_finish_takeoff_assemblies.py",
    "tests/test_finish_takeoff_ui_runtime.py",
    "tests/test_finish_takeoff_report_contract.py",
    "tests/test_master13_phase2_manual_transaction.py",
    "tests/test_master13_phase2_manual_dialog_runtime.py",
    "tests/test_manual_takeoff_workbench.py",
    "tests/test_manual_takeoff_input.py",
    "tests/test_manual_takeoff_ui_wiring.py",
)
FINISH_13 = (
    "gypsum_scratch", "gypsum_finish", "cement_render", "wall_tile",
    "wall_paint", "waterproofing_wall", "facade_finish", "floor_tile",
    "floor_screed", "ceiling_paint", "false_ceiling", "waterproofing_floor", "skirting",
)
HISTORICAL_MAIN_SHA_REPORTED = "a268344282fc22ad3f66a0489049eb8a5d7925be"
HISTORICAL_PR462_SHA = "a07cf3376dcb57b70daba30dd8bb6b6e5c5167d9"
HISTORICAL_PR481_SHA_REPORTED = "57c1e941d8ec3e371c3332e0a0b77d21102b84a5"
HISTORICAL_MAIN_BLOB_REFERENCES = {
    ".github/workflows/p100-pricebook-archive-sync.yml": "3eb89dec5e17ebcbc7d42b3309609c7824facd8e",
    "tests/test_binary_build_security_contract.py": "6107c7790a7198fc3eb9dfa5537a7bdc5475e607",
    "core/estimate/pricebook_full_building_pricing_v2.py": "6d246cb6acba3246671c09d8fbae69be60aa31ad",
}

def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()

def _dict_keys(source: str, name: str) -> list[str]:
    module = ast.parse(source)
    for statement in module.body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in statement.targets):
            d = ast.literal_eval(statement.value)
            return sorted(d.keys())
    raise ValueError(f"required mapping {name} not found")

def audit(checkout: Path, historical_zip: Path, bundle: Path | None = None) -> dict:
    if not checkout.is_dir() or not historical_zip.is_file():
        raise FileNotFoundError("checkout directory or historical archive not found")
    with zipfile.ZipFile(historical_zip) as z:
        corrupt = z.testzip()
        if corrupt:
            raise ValueError(f"ZIP corruption: {corrupt}")
        names = [n for n in z.namelist() if not n.endswith("/")]
        prefixes = {n.split("/", 1)[0] for n in names}
        if len(prefixes) != 1 or next(iter(prefixes)) != "StructuralPro-" + HISTORICAL_PR462_SHA:
            raise ValueError("archive root does not match documented PR #462 snapshot identifier")
        prefix = next(iter(prefixes)) + "/"
        source_files = set(n[len(prefix):] for n in names)
        sample = {}
        for path, main_sha in HISTORICAL_MAIN_BLOB_REFERENCES.items():
            if path in source_files:
                blob_sha = git_blob_sha(z.read(prefix + path))
                sample[path] = {"archive_present": True, "archive_blob_sha1": blob_sha,
                                "historical_main_blob_sha1": main_sha, "matches_reported_main_blob": blob_sha == main_sha}
            else:
                sample[path] = {"archive_present": False, "historical_main_blob_sha1": main_sha,
                                "matches_reported_main_blob": None}
    expected_tests = {t: (checkout / t).is_file() for t in PR481_EXPECTED_TESTS}
    engine_path = checkout / "core/takeoff/manual_workbench.py"
    ui_path = checkout / "app/manual_takeoff.py"
    domain_codes = _dict_keys(engine_path.read_text(encoding="utf-8"), "_CODE_TO_ENGINE")
    ui_codes = _dict_keys(ui_path.read_text(encoding="utf-8"), "_ENGINE_CODES")
    quarantined = checkout / "recovery/disabled_workflows"
    active = checkout / ".github/workflows"
    results = {
        "record_type": "forensic_inventory_not_reconstruction",
        "historical_main_sha_reported_only": HISTORICAL_MAIN_SHA_REPORTED,
        "historical_pr462_snapshot_sha": HISTORICAL_PR462_SHA,
        "historical_pr481_head_sha_reported_only": HISTORICAL_PR481_SHA_REPORTED,
        "full_historical_main_tree_obtained": False,
        "full_historical_pr481_tree_obtained": False,
        "historical_archive_sha256": hashlib.sha256(historical_zip.read_bytes()).hexdigest(),
        "historical_archive_file_count": len(source_files),
        "historical_main_partial_blob_comparison": sample,
        "pr481_expected_tests_in_current_checkout": expected_tests,
        "pr481_expected_tests_present_count": sum(expected_tests.values()),
        "pr481_expected_tests_missing": [k for k, v in expected_tests.items() if not v],
        "manual_workbench_basic_code_count": len(domain_codes),
        "manual_form_basic_code_count": len(ui_codes),
        "finishing_13_not_in_old_manual_workbench_route": sorted(set(FINISH_13) - set(domain_codes)),
        "finishing_13_not_in_old_manual_dialog_route": sorted(set(FINISH_13) - set(ui_codes)),
        "historical_pr464_vs_pr468_line_conflict_verified": False,
        "historical_pr464_vs_pr468_file_overlap_reported": ["core/takeoff/manual_workbench.py"],
        "quarantined_workflow_count": len(list(quarantined.glob("*.yml"))) + len(list(quarantined.glob("*.yaml"))),
        "active_workflow_count": len(list(active.glob("*.yml"))) + len(list(active.glob("*.yaml"))),
    }
    if bundle:
        if not bundle.is_file():
            raise FileNotFoundError(bundle)
        result = subprocess.run(["git", "bundle", "list-heads", str(bundle)], capture_output=True, text=True, check=True)
        results["local_bundle_heads"] = result.stdout.strip().splitlines()
        results["local_bundle_contains_original_history_verified"] = False
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--historical-zip", type=Path, required=True)
    parser.add_argument("--local-bundle", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.checkout, args.historical_zip, args.local_bundle)
    data = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(data, encoding="utf-8")
    else:
        print(data)

if __name__ == "__main__":
    main()