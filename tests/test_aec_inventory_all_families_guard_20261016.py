"""Fail-closed regression tests for all 85 historical AEC family identities.

Tests deliberately change the catalog counters along with corrupted rows so
self-consistent but tampered JSON cannot bypass the fixed code baseline.
No engineering production acceptance is implied by inventory validity.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.product.aec_item_inventory_audit import (
    _FILE, _REQUIRED, assert_priority_inventory, verify_priority_inventory
)


def _catalog():
    return json.loads(Path(_FILE).read_text(encoding="utf-8"))


def _check(tmp_path, inventory):
    path = tmp_path / "modified_aec_inventory.json"
    path.write_text(json.dumps(inventory, ensure_ascii=False), encoding="utf-8")
    return verify_priority_inventory(path)


def _sync_mutable_counters(inventory):
    inventory["priority_family_count"] = len(inventory["items"])
    inventory["component_mentions_count"] = sum(
        len(row["components"]) for row in inventory["items"]
    )


def test_fixed_baseline_covers_all_85_current_families():
    catalog = _catalog()
    codes = [row["code"] for row in catalog["items"]]
    assert len(codes) == 85
    assert len(_REQUIRED) == 85
    assert len(set(codes)) == 85
    assert set(codes) == _REQUIRED
    report = assert_priority_inventory()
    assert report["valid"]
    assert report["family_count"] == 85
    assert report["subitem_mentions"] == 879
    assert report["production_items_verified"] == 0
    assert report["release_ready"] is False


@pytest.mark.parametrize("removed_code", sorted(_REQUIRED))
def test_deleting_any_required_family_still_fails_after_counter_tampering(tmp_path, removed_code):
    catalog = _catalog()
    catalog["items"] = [r for r in catalog["items"] if r["code"] != removed_code]
    _sync_mutable_counters(catalog)
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any(removed_code in issue and "خانواده الزامی" in issue for issue in result["issues"])


def test_replacing_unrouted_family_with_unknown_code_is_rejected_even_if_counts_match(tmp_path):
    catalog = _catalog()
    row = next(r for r in catalog["items"] if r["code"] == "column_joint")
    row["code"] = "fake_unknown_joint"
    _sync_mutable_counters(catalog)
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any("column_joint" in s for s in result["issues"])
    assert any("fake_unknown_joint" in s for s in result["issues"])


def test_adding_unknown_family_with_adjusted_counters_is_rejected(tmp_path):
    catalog = _catalog()
    row = copy.deepcopy(next(r for r in catalog["items"] if r["code"] == "column_joint"))
    row["code"] = "new_unapproved_family"
    catalog["items"].append(row)
    _sync_mutable_counters(catalog)
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any("new_unapproved_family" in s for s in result["issues"])


def test_duplicate_family_id_does_not_pass_with_unchanged_counters(tmp_path):
    catalog = _catalog()
    next(r for r in catalog["items"] if r["code"] == "column_joint")["code"] = "cost_control"
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any("تکراری" in s for s in result["issues"])


def test_trailing_whitespace_in_family_id_is_not_silently_normalized(tmp_path):
    catalog = _catalog()
    next(r for r in catalog["items"] if r["code"] == "column_joint")["code"] += " "
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any("شناسه نامعتبر" in s for s in result["issues"])


@pytest.mark.parametrize("field", ("tests_verified", "fully_accepted"))
def test_inventory_guard_never_promotes_untested_family_to_accepted(tmp_path, field):
    catalog = _catalog()
    catalog["items"][0][field] = True
    result = _check(tmp_path, catalog)
    assert not result["valid"]
    assert any("پذیرش بدون شاهد" in s for s in result["issues"])
