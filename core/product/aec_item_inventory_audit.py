"""Review-only acceptance matrix for StructuralPro priorities 1–9.

This audit prevents quietly losing a named system/item in source control.
It NEVER promotes catalogued or reviewed-contract data to production acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.takeoff.reviewed_aec import SPECS
from core.takeoff.reviewed_structural import KINDS

_FILE = (Path(__file__).resolve().parents[2] / "docs" /
         "aec_priority_1_9_master_inventory_20261013.json")
_REQUIRED = frozenset({
    # Immutable family IDs: never derive this guard from editable inventory counters.
    # Legacy inventory group 1 (not the approved eight project phases).
    "beam_schedule", "drawing_selection", "drawing_sources",
    # Legacy inventory group 2 (not the approved eight project phases).
    "beam_reinforcement",
    # Legacy inventory group 3 (not the approved eight project phases).
    "beam_concrete_formwork",
    # Legacy inventory group 4 (not the approved eight project phases).
    "column", "column_joint",
    # Legacy inventory group 5 (not the approved eight project phases).
    "bored_pile", "isolated_footing", "mat_footing",
    "pile_cap", "pile_foundation", "strip_footing",
    "tie_beam",
    # Legacy inventory group 6 (not the approved eight project phases).
    "shear_wall", "stair", "stair_metal",
    # Legacy inventory group 7 (not the approved eight project phases).
    "cobiax", "composite_roof", "hollow_core",
    "joist_block", "joist_foam", "kromit_roof",
    "precast_roof", "sandwich_roof", "solid_slab",
    "steel_deck", "timber_roof", "uboot",
    "waffle",
    # Legacy inventory group 8 (not the approved eight project phases).
    "acoustic_insulation", "blinding_concrete", "block_wall",
    "brick_wall", "cement_render", "ceramic_finish",
    "composite_frame", "concrete_repair", "data_network",
    "demolition", "door_window", "electrical_power",
    "elevator", "emergency_power", "external_earthwork",
    "external_works", "facade_cladding", "fire_alarm",
    "fire_protection", "floor_finish", "glass_curtain_wall",
    "gypsum_partition", "handrails_metalwork", "historic_restoration",
    "hvac", "lighting", "low_voltage",
    "mechanical_ventilation", "natural_gas", "paint_finish",
    "plantroom", "plaster_finish", "plumbing",
    "retaining_structures", "sanitary_drainage", "security_systems",
    "seismic_retrofit", "site_drains", "steel_frame",
    "stone_cladding", "stone_floor", "suspended_ceiling",
    "thermal_insulation", "timber_frame", "upvc_aluminium_windows",
    "waterproofing",
    # Legacy inventory group 9 (not the approved eight project phases).
    "audit_provenance", "boq", "cost_control",
    "estimate", "manual_workbench", "pricebook",
    "reporting", "scheduling", "statement",
})
_ROUTES = frozenset({
    "review_contract", "structural_review_contract",
    "beam_feature_path", "requires_dedicated_acceptance",
})
_SPECIALIST_PARENTS = {"waffle_one_way": "waffle", "waffle_two_way": "waffle", "hollow_core_detail": "hollow_core"}
_PRIORITY_SET = frozenset(range(1, 10))


def verify_priority_inventory(path: str | Path = _FILE) -> dict[str, Any]:
    """Validate the independent master ledger against actual code registries."""
    inventory = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = inventory.get("items")
    if not isinstance(rows, list) or not rows:
        raise ValueError("فهرست آیتم‌های AEC خالی یا نامعتبر است")
    ids, seen_priorities = set(), set()
    variants: dict[str, str] = {}
    subitems = 0
    issues: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            issues.append("ساختار یکی از خانواده‌ها نامعتبر است")
            continue
        p = row.get("priority")
        key = row.get("code")
        names = row.get("components")
        route = row.get("coverage_level")
        if type(p) is not int or p not in _PRIORITY_SET:
            issues.append(f"اولویت خارج از محدوده: {key}")
        else:
            seen_priorities.add(p)
        if not isinstance(key, str) or not key.strip() or key != key.strip() or key in ids:
            issues.append(f"شناسه نامعتبر یا تکراری: {key}")
        else:
            ids.add(key)
        if not isinstance(row.get("title"), str) or not row["title"].strip():
            issues.append(f"عنوان فارسی خالی: {key}")
        if not isinstance(names, list) or not names or any(
                not isinstance(x, str) or not x.strip() for x in names):
            issues.append(f"ریزآیتم‌های الزامی ناقص: {key}")
        else:
            if len(names) != len(set(names)):
                issues.append(f"ریزآیتم تکراری در خانواده: {key}")
            subitems += len(names)
        if route not in _ROUTES:
            issues.append(f"نوع پوشش ناشناخته: {key}")
        declared = row.get("review_contract_variants", [])
        if not isinstance(declared, list):
            issues.append(f"فهرست قراردادهای تخصصی خانواده نامعتبر است: {key}")
            declared = []
        for variant in declared:
            if (not isinstance(variant, str) or variant not in SPECS
                    or _SPECIALIST_PARENTS.get(variant) != key
                    or route != "review_contract"):
                issues.append(f"قرارداد تخصصی یا والد نامعتبر: {key}/{variant}")
                continue
            if variant in variants:
                issues.append(f"قرارداد تخصصی تکراری: {variant}")
            variants[variant] = key
        if row.get("fully_accepted") is not False or row.get("tests_verified") is not False:
            # Explicit acceptance must be proven by a separate audited process.
            issues.append(f"پذیرش بدون شاهد یا آزمون: {key}")
    missing_family_ids = sorted(_REQUIRED - ids)
    unexpected_family_ids = sorted(ids - _REQUIRED)
    if set(variants) & ids:
        issues.append("قرارداد تخصصی هم‌زمان به‌عنوان خانواده مستقل تکرار شده است")
    missing_aec_contracts = sorted(set(SPECS) - ids - set(variants))
    missing_structure_contracts = sorted(set(KINDS) - ids)
    missing_priorities = sorted(_PRIORITY_SET - seen_priorities)
    for label, missing in (("خانواده الزامی", missing_family_ids),
                           ("خانواده اضافی یا ناشناخته", unexpected_family_ids),
                           ("قرارداد AEC", missing_aec_contracts),
                           ("عضو سازه‌ای", missing_structure_contracts),
                           ("اولویت", missing_priorities)):
        if missing:
            issues.append(f"{label} در حسابرسی موجود نیست: {', '.join(map(str, missing))}")
    if len(rows) != inventory.get("priority_family_count"):
        issues.append("تعداد خانواده‌ها با فهرست مرجع برابر نیست")
    if subitems != inventory.get("component_mentions_count"):
        issues.append("تعداد ریزآیتم‌ها با فهرست مرجع برابر نیست")
    for record in rows:
        if not isinstance(record, dict):
            continue
        key, route = record.get("code"), record.get("coverage_level")
        if key in SPECS and route != "review_contract":
            issues.append(f"وضعیت قرارداد AEC نادرست: {key}")
        if key in KINDS and route != "structural_review_contract":
            issues.append(f"وضعیت عضو بتنی نادرست: {key}")
        if route == "review_contract" and key not in SPECS:
            issues.append(f"قرارداد AEC ثبت‌شده در کد وجود ندارد: {key}")
        if route == "structural_review_contract" and key not in KINDS:
            issues.append(f"عضو سازه‌ای ثبت‌شده در کد وجود ندارد: {key}")
    return {
        "valid": not issues,
        "issues": issues,
        "family_count": len(rows),
        "subitem_mentions": subitems,
        "reviewed_aec_contracts": len(SPECS),
        "reviewed_structural_contracts": len(KINDS),
        "priority_counts": {str(i): sum(r.get("priority") == i for r in rows) for i in range(1, 10)},
        "production_items_verified": 0,
        "release_ready": False,
        "message": "ثبت قلم در فهرست، اثبات صحت متره، نقشه، رابط، گزارش و آزمون نیست",
    }


def assert_priority_inventory(path: str | Path = _FILE) -> dict[str, Any]:
    output = verify_priority_inventory(path)
    if not output["valid"]:
        raise ValueError("خطا در فهرست جامع: " + "؛ ".join(output["issues"]))
    return output
