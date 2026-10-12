"""Tests for P34 — Final Product Acceptance."""
from __future__ import annotations

from core.platform.p34_final_product_acceptance import (
    REQUIRED_SURFACES,
    run_p34_gate,
)

def test_p34_accepts_complete_repository_evidence():
    result = run_p34_gate()
    assert result.accepted, result.blockers
    assert result.surfaces == REQUIRED_SURFACES
    assert result.phase_artifacts == 27
    assert result.fingerprint

def test_p34_is_deterministic():
    first = run_p34_gate()
    second = run_p34_gate()
    assert first == second

def test_p34_has_all_required_acceptance_surfaces():
    result = run_p34_gate()
    expected = {
        "functional", "ui_ux", "persian_rtl", "takeoff", "cad", "bim", "ai",
        "estimate", "commercial", "reports", "performance", "security",
        "regression", "competitive_parity",
    }
    assert set(result.surfaces) == expected

def test_p34_does_not_claim_p35():
    result = run_p34_gate()
    assert result.accepted
    # P34 is acceptance only; FINAL SIGN-OFF remains a separate gate.
    assert "p35_not_claimed" not in result.blockers
