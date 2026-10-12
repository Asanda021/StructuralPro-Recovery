"""Phase 4 BOQ and estimating regression tests."""
from pathlib import Path

import pytest

from core.pricing.catalog import PriceCatalog, PriceItem
from core.takeoff.boq import build_boq
from core.takeoff.estimating import (
    build_professional_estimate,
    find_cross_source_duplicates,
    map_prices,
)
from core.revisions.compare import compare_rows


def catalog():
    return PriceCatalog([
        PriceItem(1405, "ابنیه", "بتن", "B-001", "بتن مگر", "m3", 2500000),
        PriceItem(1405, "ابنیه", "آرماتور", "R-001", "میلگرد", "kg", 30000),
    ])


def test_waste_and_allowance_are_explicit_and_costed():
    boq = build_boq([{
        "source": "takeoff:1",
        "price_code": "B-001",
        "description": "بتن مگر",
        "quantity": 10,
        "unit": "m3",
        "unit_price": 100,
        "waste_percent": 5,
        "allowance_quantity": 0.5,
    }])
    assert boq[0]["quantity"] == 10
    assert boq[0]["effective_quantity"] == pytest.approx(11)
    assert boq[0]["total"] == pytest.approx(1100)


def test_price_mapping_preserves_provenance_and_rejects_unit_guessing():
    result = map_prices([{
        "source": "drawing:1",
        "price_code": "B-001",
        "description": "بتن",
        "quantity": 2,
        "unit": "m3",
    }], catalog(), year=1405)
    row = result["rows"][0]
    assert result["unresolved"] == []
    assert row["unit_price"] == 2500000
    assert row["price_source"]["year"] == 1405
    assert row["price_source"]["code"] == "B-001"

    mismatch = map_prices([{
        "source": "drawing:2",
        "price_code": "B-001",
        "description": "بتن",
        "quantity": 2,
        "unit": "kg",
    }], catalog(), year=1405)
    assert mismatch["unresolved"][0]["status"] == "unit_mismatch"


def test_cross_source_duplicates_are_reported_not_deleted():
    rows = [
        {"source": "ifc:C1", "source_type": "bim", "object_id": "C1", "unit": "m3", "quantity": 3},
        {"source": "cad:C1", "source_type": "cad", "object_id": "C1", "unit": "m3", "quantity": 3},
    ]
    duplicates = find_cross_source_duplicates(rows)
    assert len(duplicates) == 1
    assert duplicates[0]["status"] == "needs_confirmation"
    assert len(rows) == 2


def test_final_estimate_requires_duplicate_review():
    rows = [
        {"source": "ifc:C1", "source_type": "bim", "object_id": "C1",
         "price_code": "B-001", "description": "بتن", "quantity": 3, "unit": "m3"},
        {"source": "cad:C1", "source_type": "cad", "object_id": "C1",
         "price_code": "B-001", "description": "بتن", "quantity": 3, "unit": "m3"},
    ]
    with pytest.raises(ValueError, match="duplicate review"):
        build_professional_estimate(rows, catalog=catalog(), year=1405)


def test_estimate_is_finalizable_after_duplicate_and_price_review_are_clear():
    result = build_professional_estimate([{
        "source": "takeoff:1",
        "source_type": "manual",
        "price_code": "B-001",
        "description": "بتن مگر",
        "quantity": 10,
        "unit": "m3",
        "waste_percent": 5,
        "allowance_quantity": 0.5,
    }], catalog=catalog(), year=1405)
    assert result["finalizable"] is True
    assert result["boq"][0]["effective_quantity"] == pytest.approx(11)
    assert result["cost"]["grand_total"] == pytest.approx(27500000)


def test_revision_compare_keeps_quantity_and_cost_deltas():
    old = [{"price_code": "B-001", "quantity": 10, "total": 25}]
    new = [{"price_code": "B-001", "quantity": 12, "total": 30}]
    changes = compare_rows(old, new)
    assert changes[0]["status"] == "changed"
    assert changes[0]["quantity_delta"] == 2
    assert changes[0]["total_delta"] == 5
