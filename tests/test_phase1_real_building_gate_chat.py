"""14 isolated real-building evidence-gate regressions (synthetic fixtures only).

A structurally complete mock bundle can *never* claim engineering acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256

import pytest

from scripts.phase1_real_building_gate import audit_real_building


def fake_bundle(root):
    drawings = []
    for discipline in ("structure", "architecture"):
        source = root / (discipline + ".txt")
        source.write_text("TEST-ONLY-DRAWING:" + discipline)
        drawings.append({"id": discipline, "path": source.name,
                         "sha256": sha256(source.read_bytes()).hexdigest(),
                         "revision": "R1", "discipline": discipline})
    certificate = root / "mock_review.txt"
    certificate.write_text("FAKE-REVIEW-FOR-TESTS-ONLY")
    return {
        "mode": "real_approved_drawings", "building_id": "TEST-ONLY",
        "floors": [{"id": str(i)} for i in range(1, 6)],
        "drawings": drawings,
        "independent_oracles": [
            {"floor_id": str(i), "physical_id": f"P{i}", "drawing_id": "structure",
             "source_revision": "R1", "unit": "m3",
             "independent_quantity": "1.25", "software_quantity": "1.25"}
            for i in range(1, 6)],
        "external_review_documents": [
            {"path": certificate.name,
             "sha256": sha256(certificate.read_bytes()).hexdigest()}],
    }


def test_no_real_drawings_never_passes(tmp_path):
    result = audit_real_building({"mode": "synthetic", "floors": [], "drawings": []}, tmp_path)
    assert not result["candidate_ready_for_external_review"]
    assert result["engineering_accepted"] is False


def test_structurally_complete_mock_remains_professionally_unapproved(tmp_path):
    result = audit_real_building(fake_bundle(tmp_path), tmp_path)
    assert result["candidate_ready_for_external_review"]
    assert result["engineering_accepted"] is False
    assert result["financially_approved"] is False


@pytest.mark.parametrize("case", [
    "hash_changed", "revision_wrong", "physical_repeated", "quantity_changed",
    "drawing_missing", "one_floor_absent", "review_missing",
    "source_bytes_missing", "unsafe_parent_path", "discipline_missing",
    "some_floor_oracles_missing", "negative_reference_quantity",
])
def test_real_building_gate_fails_closed_on_missing_or_corrupted_proof(tmp_path, case):
    bundle = deepcopy(fake_bundle(tmp_path))
    if case == "hash_changed":
        bundle["drawings"][0]["sha256"] = "0" * 64
    elif case == "revision_wrong":
        bundle["independent_oracles"][0]["source_revision"] = "R2"
    elif case == "physical_repeated":
        bundle["independent_oracles"][1]["floor_id"] = "1"
        bundle["independent_oracles"][1]["physical_id"] = "P1"
    elif case == "quantity_changed":
        bundle["independent_oracles"][0]["software_quantity"] = "1.251"
    elif case == "drawing_missing":
        bundle["independent_oracles"][0]["drawing_id"] = "missing-drawing"
    elif case == "one_floor_absent":
        bundle["floors"].pop()
    elif case == "review_missing":
        bundle["external_review_documents"] = []
    elif case == "source_bytes_missing":
        bundle["drawings"][0]["path"] = "not-present.pdf"
    elif case == "unsafe_parent_path":
        bundle["drawings"][0]["path"] = "../escape.pdf"
    elif case == "discipline_missing":
        bundle["drawings"][0]["discipline"] = "mechanical"
    elif case == "some_floor_oracles_missing":
        bundle["independent_oracles"] = bundle["independent_oracles"][:3]
    elif case == "negative_reference_quantity":
        bundle["independent_oracles"][0]["independent_quantity"] = "-1"
    result = audit_real_building(bundle, tmp_path)
    assert result["candidate_ready_for_external_review"] is False
    assert result["engineering_accepted"] is False


def test_persian_digit_aliases_do_not_create_a_new_floor(tmp_path):
    bundle = fake_bundle(tmp_path)
    bundle["floors"][1]["id"] = "۱"  # already represented by ASCII '1'
    result = audit_real_building(bundle, tmp_path)
    assert not result["candidate_ready_for_external_review"]
    assert result["engineering_accepted"] is False


def test_persian_member_aliases_do_not_allow_double_payment(tmp_path):
    bundle = fake_bundle(tmp_path)
    bundle["independent_oracles"][1].update(floor_id="۱", physical_id="p1")
    result = audit_real_building(bundle, tmp_path)
    assert not result["candidate_ready_for_external_review"]
    assert result["engineering_accepted"] is False
