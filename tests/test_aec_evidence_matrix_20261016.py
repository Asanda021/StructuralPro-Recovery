"""Negative regressions for the independent eight-phase acceptance evidence ledger.

These tests validate truthful evidence accounting; they are NOT Windows or
engineering acceptance tests and must not be counted as such.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from core.product.aec_item_inventory_audit import _REQUIRED
from core.product.aec_evidence_matrix import (
    MATRIX_FILE, _GATES, _LIMITED_SOURCES, assert_family_evidence,
    verify_family_evidence,
)


def _matrix():
    return json.loads(Path(MATRIX_FILE).read_text(encoding="utf-8"))


def _check(tmp_path, document):
    p = tmp_path / "evidence.json"
    p.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return verify_family_evidence(p)


def test_current_matrix_is_conservative_and_matches_all_85_families():
    result = assert_family_evidence()
    assert result["valid"]
    assert result["family_count"] == 85
    assert result["limited_documented_count"] == 17
    assert result["unverified_count"] == 68
    assert result["fully_accepted_count"] == 0
    assert result["release_ready"] is False
    rows = _matrix()["rows"]
    assert {row["code"] for row in rows} == _REQUIRED
    assert len(_GATES) == 9
    assert {row["primary_phase"] for row in rows} <= set(range(1, 9))
    assert all(row["gates"]["windows_office_acceptance"] == "not_verified"
               and row["gates"]["real_engineering_case"] == "not_verified"
               and row["gates"]["drawing_takeoff"] == "not_verified"
               for row in rows)


@pytest.mark.parametrize("removed_code", sorted(_REQUIRED))
def test_cannot_lose_an_acceptance_row_even_if_mutable_count_changes(tmp_path, removed_code):
    document = _matrix()
    document["rows"] = [r for r in document["rows"] if r["code"] != removed_code]
    document["source_family_count"] = len(document["rows"])
    result = _check(tmp_path, document)
    assert not result["valid"]
    assert any(removed_code in s for s in result["issues"])


def test_cannot_duplicate_a_family(tmp_path):
    document = _matrix()
    document["rows"].append(copy.deepcopy(document["rows"][0]))
    assert not _check(tmp_path, document)["valid"]


def test_cannot_substitute_a_family_with_an_unapproved_one(tmp_path):
    document = _matrix()
    next(r for r in document["rows"] if r["code"] == "column_joint")["code"] = "fake_joint"
    assert not _check(tmp_path, document)["valid"]


@pytest.mark.parametrize("gate", sorted(_GATES))
def test_unverified_family_cannot_gain_a_gate_without_evidence(tmp_path, gate):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == "cobiax")
    row["gates"][gate] = "documented_limited"
    assert not _check(tmp_path, document)["valid"]


@pytest.mark.parametrize("code", sorted(_LIMITED_SOURCES))
def test_documented_family_cannot_lose_its_provenance(tmp_path, code):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == code)
    row["evidence"]["documents"] = []
    assert not _check(tmp_path, document)["valid"]


@pytest.mark.parametrize("code", sorted(_LIMITED_SOURCES))
def test_documented_family_cannot_claim_windows_acceptance(tmp_path, code):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == code)
    row["gates"]["windows_office_acceptance"] = "documented_limited"
    assert not _check(tmp_path, document)["valid"]


@pytest.mark.parametrize("field,value", (
    ("fully_accepted", True), ("primary_phase", 8), ("acceptance_status", "complete"),
))
def test_false_completion_phase_change_or_unsupported_status_is_rejected(tmp_path, field, value):
    document = _matrix()
    document["rows"][0][field] = value
    assert not _check(tmp_path, document)["valid"]


def test_unknown_gate_cannot_replace_approved_gate(tmp_path):
    document = _matrix()
    gates = document["rows"][0]["gates"]
    gates["unverified_miracle"] = gates.pop("engineering_calculation")
    assert not _check(tmp_path, document)["valid"]


def test_missing_evidence_test_file_is_rejected(tmp_path):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == "solid_slab")
    row["evidence"]["tests"] = ["tests/not_real.py"]
    assert not _check(tmp_path, document)["valid"]


def test_unmodified_source_is_not_auto_promoted_to_product_acceptance():
    document = _matrix()
    assert all(r["fully_accepted"] is False for r in document["rows"])
    assert all(r["evidence"]["input_type"] in {"synthetic_documented", "not_verified"}
               for r in document["rows"])


@pytest.mark.parametrize("code", sorted(_LIMITED_SOURCES))
def test_documented_families_cannot_claim_unverified_report_formats(tmp_path, code):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == code)
    row["evidence"]["formats"].append("unverified-format")
    assert not _check(tmp_path, document)["valid"]


@pytest.mark.parametrize("code,extra_variant", (
    ("waffle", "waffle_unverified_3d"),
    ("hollow_core", "hollow_core_unverified_panels"),
))
def test_specialist_variant_requires_documented_parent_and_evidence(tmp_path, code, extra_variant):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == code)
    row["evidence"]["variants"].append(extra_variant)
    assert not _check(tmp_path, document)["valid"]


def test_source_catalog_blob_sha_cannot_be_replaced_by_a_claim(tmp_path):
    document = _matrix()
    document["source_inventory_blob_sha"] = "0" * 40
    result = _check(tmp_path, document)
    assert not result["valid"]
    assert any("اثر انگشت" in s for s in result["issues"])


def test_uncorroborated_family_cannot_invent_report_format(tmp_path):
    document = _matrix()
    row = next(r for r in document["rows"] if r["code"] == "cobiax")
    row["evidence"]["formats"] = ["pdf"]
    assert not _check(tmp_path, document)["valid"]
