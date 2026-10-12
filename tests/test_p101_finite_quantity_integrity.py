import math

import pytest

from core.estimate.pricebook_full_building_pricing_v2 import (
    ProductionRow,
    normalize_rows,
    price_full_building,
    price_full_building_project,
)


def row(unit_price=10.0):
    return ProductionRow(
        1404, "ابنیه", "1001", "Concrete", "m3", unit_price, "sha", "official.xlsx"
    )


def takeoff(quantity):
    return [{
        "takeoff_id": "Q1",
        "discipline": "ابنیه",
        "item_code": "1001",
        "unit": "m3",
        "quantity": quantity,
    }]


@pytest.mark.parametrize("invalid", [math.nan, math.inf, -math.inf])
def test_nonfinite_or_negative_inputs_are_rejected(invalid):
    with pytest.raises(ValueError, match="unit price must be finite"):
        normalize_rows([row(invalid)])
    for price_function, rows in (
        (price_full_building, [row()]),
        (price_full_building_project, [row()]),
    ):
        with pytest.raises(ValueError, match="takeoff quantity must be finite"):
            if price_function is price_full_building:
                price_function(takeoff(invalid), rows, 1404, "ابنیه")
            else:
                price_function(takeoff(invalid), rows, 1404)


def test_nonfinite_computed_total_is_rejected():
    huge = row(1e308)
    with pytest.raises(ValueError, match="price total must be finite"):
        price_full_building(takeoff(1e308), [huge], 1404, "ابنیه")
    with pytest.raises(ValueError, match="price total must be finite"):
        price_full_building_project(takeoff(1e308), [huge], 1404)
