"""Evidence-only, fail-closed audit for the 85 AEC families and eight approved phases.

This validates historical documentation, NOT product acceptance. A catalogued
family, generic form, passing synthetic test or emitted report cannot satisfy
real engineering or Windows acceptance without a separately reviewed change.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

from core.product.aec_item_inventory_audit import _FILE as INVENTORY_FILE
from core.product.aec_item_inventory_audit import _REQUIRED

_ROOT = Path(__file__).resolve().parents[2]
MATRIX_FILE = _ROOT / "docs/acceptance/aec_85_family_evidence_matrix_8phases_20261016.json"
_GATES = frozenset({
    "engineering_calculation", "manual_ui", "sqlite_history",
    "review_amendment", "boq_dedup", "report_exports",
    "drawing_takeoff", "real_engineering_case", "windows_office_acceptance",
})
_DOCUMENTED_GATES = _GATES - {
    "drawing_takeoff", "real_engineering_case", "windows_office_acceptance",
}
_REAL_WORLD_GATES = _GATES - _DOCUMENTED_GATES

# Deliberate baseline IN CODE, not derived from editable matrix or counters.
_GROUPS = (
    (("beam_schedule", "beam_reinforcement", "beam_concrete_formwork"),
     "beam_stage2_1_closure_20261014.md", ("test_beam_closure.py",)),
    (("column",), "column_stage2_2_20261014.md", ("test_column_stage22.py",)),
    (("isolated_footing", "strip_footing", "mat_footing", "tie_beam", "pile_cap"),
     "foundation_three_gaps_20261015.md", ("test_foundation_close_three.py",)),
    (("solid_slab", "joist_block", "joist_foam"),
     "roof_work2_package1_20261015.md",
     ("test_roof_specialist_work.py", "test_roof_specialist_ui.py")),
    (("waffle",), "roof_work2_package2_waffle_20261015.md",
     ("test_waffle_specialist_work.py", "test_waffle_specialist_ui.py")),
    (("hollow_core",), "roof_work2_package3_hollowcore_20261016.md",
     ("test_hollowcore_specialist_work.py", "test_hollowcore_specialist_ui.py")),
    (("waterproofing", "thermal_insulation", "acoustic_insulation"),
     "architecture_step6_package3_insulation_partial_20261016.md",
     ("test_insulation_specialist_work.py", "test_insulation_specialist_ui.py")),
)
_LIMITED_SOURCES: dict[str, tuple[list[str], list[str]]] = {
    code: (["docs/acceptance/" + doc], ["tests/" + t for t in tests])
    for codes, doc, tests in _GROUPS for code in codes
}
_FORMATS = {
    code: (["pdf", "xlsx", "docx", "csv"] if doc.startswith(("roof_", "architecture_step6_package3_"))
           else ["pdf", "xlsx"])
    for codes, doc, tests in _GROUPS for code in codes
}
_VARIANTS = {
    "waffle": ["waffle_one_way", "waffle_two_way"],
    "hollow_core": ["hollow_core_detail"],
}
_PHASE_2 = frozenset({"drawing_sources", "drawing_selection", "manual_workbench"})
_PHASE_3 = frozenset({"boq", "pricebook", "estimate", "statement", "cost_control"})


def _phase(code: str) -> int:
    if code in _PHASE_2:
        return 2
    if code in _PHASE_3:
        return 3
    return {"scheduling": 4, "audit_provenance": 5, "reporting": 7}.get(code, 1)


def verify_family_evidence(
    matrix_path: str | Path = MATRIX_FILE,
    inventory_path: str | Path = INVENTORY_FILE,
) -> dict[str, Any]:
    """Check matrix against the independent catalog and fixed evidence baseline."""
    matrix = json.loads(Path(matrix_path).read_text(encoding="utf-8"))
    source_bytes = Path(inventory_path).read_bytes()
    inventory = json.loads(source_bytes.decode("utf-8"))
    issues: list[str] = []
    git_blob = hashlib.sha1(
        b"blob " + str(len(source_bytes)).encode("ascii") + b"\0" + source_bytes
    ).hexdigest()
    if matrix.get("source_inventory_blob_sha") != git_blob:
        issues.append("اثر انگشت Git بانک مرجع با ماتریس متفاوت است")

    originals = inventory.get("items")
    rows = matrix.get("rows")
    if not isinstance(originals, list) or not isinstance(rows, list):
        raise ValueError("ساختار فهرست یا ماتریس خانواده‌ها نامعتبر است")
    if len(originals) != 85 or len(_REQUIRED) != 85:
        issues.append("تعداد مبنای ۸۵ خانواده تغییر کرده است")
    original_ids = [x.get("code") for x in originals if isinstance(x, dict)]
    source_by_code = {x["code"]: x for x in originals
                      if isinstance(x, dict) and isinstance(x.get("code"), str)}
    if any(r.get("fully_accepted") is not False or r.get("tests_verified") is not False
           for r in originals if isinstance(r, dict)):
        issues.append("بانک مرجع دارای پذیرش بدون شاهد است")
    if set(original_ids) != _REQUIRED or len(original_ids) != len(set(original_ids)):
        issues.append("شناسه‌های مرجع با قرارداد ۸۵ خانواده برابر نیستند")
    if matrix.get("schema_version") != "phase1-8phase-evidence-v1":
        issues.append("نسخه قرارداد ماتریس نامعتبر است")
    if matrix.get("source_inventory") != "docs/aec_priority_1_9_master_inventory_20261013.json":
        issues.append("مرجع ماتریس با بانک آیتم‌های واقعی یکسان نیست")
    if matrix.get("source_family_count") != 85 or matrix.get("source_subitem_mentions") != 879:
        issues.append("خط مبنای آماری ماتریس نامعتبر است")
    if sum(len(x.get("components", [])) for x in originals if isinstance(x, dict)) != 879:
        issues.append("زیرآیتم‌های بانک مرجع تغییر کرده‌اند")
    if set(matrix.get("gate_keys", [])) != _GATES or len(matrix.get("gate_keys", [])) != 9:
        issues.append("دروازه‌های پذیرش تعریف‌شده تغییر کرده‌اند")
    if len(rows) != 85:
        issues.append("ماتریس باید دقیقاً ۸۵ خانواده داشته باشد")

    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            issues.append("ردیف نامعتبر در ماتریس")
            continue
        code = row.get("code")
        if not isinstance(code, str) or not code.strip() or code in seen:
            issues.append(f"شناسه تکراری یا نامعتبر در ماتریس: {code}")
            continue
        seen.add(code)
        src = source_by_code.get(code)
        if src is None:
            issues.append(f"خانواده خارج از فهرست مرجع: {code}")
            continue
        if (row.get("title") != src.get("title")
                or row.get("legacy_priority") != src.get("priority")
                or row.get("inventory_coverage_level") != src.get("coverage_level")
                or row.get("inventory_route_file") != src.get("route_file")
                or row.get("inventory_variants") != src.get("review_contract_variants", [])
                or row.get("primary_phase") != _phase(code)):
            issues.append(f"اطلاعات هویتی/فاز خانواده تغییر کرده است: {code}")
        gates = row.get("gates")
        if not isinstance(gates, dict) or set(gates) != _GATES:
            issues.append(f"دروازه‌های خانواده ناقص‌اند: {code}")
            continue
        if row.get("fully_accepted") is not False:
            issues.append(f"پذیرش نهایی بدون مجوز و مدرک: {code}")
        if any(gates[g] != "not_verified" for g in _REAL_WORLD_GATES):
            issues.append(f"پذیرش نقشه واقعی یا Windows بدون شاهد: {code}")

        e = row.get("evidence")
        if not isinstance(e, dict):
            issues.append(f"ساختار شواهد نامعتبر: {code}")
            continue
        documented = code in _LIMITED_SOURCES
        if documented:
            expected_docs, expected_tests = _LIMITED_SOURCES[code]
            if (row.get("acceptance_status") != "limited_documented"
                    or any(gates[g] != "documented_limited" for g in _DOCUMENTED_GATES)
                    or e.get("documents") != expected_docs
                    or e.get("tests") != expected_tests
                    or e.get("input_type") != "synthetic_documented"):
                issues.append(f"شواهد تخصصی ناسازگار یا حذف‌شده: {code}")
            for path in expected_docs + expected_tests:
                if not (_ROOT / path).is_file():
                    issues.append(f"فایل شاهد در مخزن وجود ندارد: {path}")
            if e.get("formats") != _FORMATS[code]:
                issues.append(f"قالب گزارش خارج از شواهد ثبت شده است: {code}")
            if e.get("variants") != _VARIANTS.get(code, []):
                issues.append(f"گونه تخصصی غیرمستند است: {code}")
        else:
            if (row.get("acceptance_status") != "not_individually_verified"
                    or any(gates[g] != "not_verified" for g in _DOCUMENTED_GATES)
                    or e.get("documents") != []
                    or e.get("tests") != []
                    or e.get("formats") != []
                    or e.get("variants") != []
                    or e.get("input_type") != "not_verified"):
                issues.append(f"پذیرش تخصصی بدون شاهد برای خانواده: {code}")
        if not isinstance(e.get("description"), str) or not e["description"].strip():
            issues.append(f"دامنه سند خانواده ثبت نشده است: {code}")
    for missing in sorted(_REQUIRED - seen):
        issues.append(f"خانواده فاقد وضعیت پذیرش است: {missing}")

    return {
        "valid": not issues,
        "issues": issues,
        "family_count": len(rows),
        "limited_documented_count": sum(r.get("acceptance_status") == "limited_documented"
                                      for r in rows if isinstance(r, dict)),
        "unverified_count": sum(r.get("acceptance_status") == "not_individually_verified"
                                for r in rows if isinstance(r, dict)),
        "fully_accepted_count": sum(r.get("fully_accepted") is True
                                    for r in rows if isinstance(r, dict)),
        "release_ready": False,
    }


def assert_family_evidence(
    matrix_path: str | Path = MATRIX_FILE,
    inventory_path: str | Path = INVENTORY_FILE,
) -> dict[str, Any]:
    result = verify_family_evidence(matrix_path, inventory_path)
    if not result["valid"]:
        raise ValueError("حسابرسی شواهد خانواده‌ها رد شد: " + "؛ ".join(result["issues"]))
    return result
