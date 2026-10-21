"""Fail-closed *documentation* integrity gate for phase-one engineering triage.

A zero exit code validates the 37-row audit's consistency only; it NEVER means
engineering acceptance or authorizes a specialist BOQ route, Windows or Merge.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from typing import Any

FILES = {
    "source": "docs/acceptance/phase1_closure_37_family_review_20261020.json",
    "triage": "docs/acceptance/phase1_37_family_actionable_triage_20261021.json",
    "matrix": "docs/acceptance/phase1_package1_74_family_evidence_20261019.json",
    "inventory": "docs/aec_priority_1_9_master_inventory_20261013.json",
    "ledger": "docs/acceptance/phase1_cloud_execution_20261021.json",
}


def _by_code(rows: list[dict[str, Any]], scope: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("code"), str) or not row["code"]:
            errors.append(f"{scope}: invalid record or code")
            continue
        if row["code"] in lookup:
            errors.append(f"{scope}: duplicated identifier {row['code']}")
        lookup[row["code"]] = row
    return lookup


def validate_documents(source: dict[str, Any], triage: dict[str, Any],
                       matrix: dict[str, Any], inventory: dict[str, Any],
                       ledger: dict[str, Any]) -> list[str]:
    """Validate completeness without inferring any missing engineering evidence."""
    errors: list[str] = []
    source_rows = source.get("families", [])
    triage_rows = triage.get("families", [])
    matrix_rows = matrix.get("rows", [])
    inventory_rows = inventory.get("items", [])
    ledger_rows = ledger.get("engineering_dependencies", [])
    if not all(isinstance(rows, list) for rows in
               (source_rows, triage_rows, matrix_rows, inventory_rows, ledger_rows)):
        return ["invalid registry type (families/rows/items)"]
    sr = _by_code(source_rows, "source", errors)
    tr = _by_code(triage_rows, "triage", errors)
    mr = _by_code(matrix_rows, "matrix", errors)
    ir = _by_code(inventory_rows, "inventory", errors)
    lr = _by_code(ledger_rows, "cloud ledger", errors)
    if len(sr) != 37 or len(tr) != 37:
        errors.append(f"37-family source/triage count mismatch: {len(sr)}/{len(tr)}")
    if len(mr) != 74 or len(ir) != 85:
        errors.append(f"inventory/matrix count mismatch: {len(ir)}/{len(mr)}")
    if set(sr) != set(tr) or set(sr) != set(lr):
        errors.append("triage and ledger identifiers differ from source")
    if not set(sr).issubset(mr) or not set(sr).issubset(ir):
        errors.append("triage includes IDs not contained in 74-family matrix or 85-bank inventory")
    if triage.get("schema") != "phase1_nonwindows_37_family_blocker_triage_v1":
        errors.append("unexpected triage schema")
    expected_categories = Counter(row.get("category") for row in source_rows)
    summary = triage.get("summary", {})
    if (summary.get("total_families") != 37
            or summary.get("fully_accepted") != 0
            or summary.get("missing_independent_evidence") != 37
            or summary.get("software_defect_proven_by_this_audit") != 0
            or summary.get("categories") != dict(expected_categories)):
        errors.append("triage summary has unsupported acceptance/count claims")
    if ledger.get("acceptance", {}).get("phase_one_closed") is not False:
        errors.append("source cloud ledger no longer reports an open phase-one gate")
    for code, family in sr.items():
        audit = tr.get(code)
        if audit is None:
            continue
        dependency = family.get("dependency") or {}
        expected = {
            "title": family.get("title"),
            "category": family.get("category"),
            "existing_engine": family.get("existing_engine"),
            "software_scope_observed": family.get("new_test_scope"),
            "software_acceptance_gap": family.get("dedicated_whole_family_algorithm_gap"),
            "external_required_documents": dependency.get("needed_documents"),
            "external_provider_reviewer": dependency.get("responsible_provider_reviewer"),
        }
        for field, required in expected.items():
            if audit.get(field) != required:
                errors.append(f"{code}: stale or mismatched {field}")
        if (family.get("independent_engineering_evidence") != "missing"
                or family.get("full_family_engineering_acceptance") is not False
                or dependency.get("status") != "blocked_engineering_dependency"
                or not isinstance(dependency.get("needed_documents"), list)
                or not dependency["needed_documents"]):
            errors.append(f"{code}: source no longer justifies missing-evidence status")
        if (audit.get("independent_evidence_status") != "missing"
                or audit.get("record_status") != "blocked_engineering_dependency"
                or audit.get("full_family_engineering_accepted") is not False):
            errors.append(f"{code}: audit claims unjustified engineering acceptance")
        if not isinstance(audit.get("software_work_after_authoritative_inputs"), str) or not audit["software_work_after_authoritative_inputs"].strip():
            errors.append(f"{code}: missing software verification plan")
        if not isinstance(audit.get("existing_test_references"), list):
            errors.append(f"{code}: existing test references must be a list")
    return errors


def validate_repository(root: Path) -> list[str]:
    docs = {name: json.loads((root / relative).read_text(encoding="utf-8"))
            for name, relative in FILES.items()}
    return validate_documents(docs["source"], docs["triage"], docs["matrix"],
                              docs["inventory"], docs["ledger"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify 37-family triage integrity, NOT approval")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        problems = validate_repository(args.root)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"TRIAGE SOURCE ERROR: {exc}")
        return 2
    if problems:
        for problem in problems:
            print(f"TRIAGE ERROR: {problem}")
        return 1
    print("TRIAGE INTEGRITY PASS: 37 mapped, 37 externally blocked, 0 specialist acceptances. Phase 1 remains OPEN.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
