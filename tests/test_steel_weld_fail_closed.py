"""Engineering regression: never infer weld mass from an undocumented default."""

import pytest

from core.engineering.domains import steel_quantities


VALID_WELD = {
    "length": 5.0,
    "count": 2,
    "weld_unit_weight": 0.25,
    "weld_unit_weight_unit": "kg/m",
    "weld_detail_ref": "WELD-DETAIL-TEST-01",
}


def test_weld_exact_mass_requires_explicit_kg_per_m_and_detail():
    result = steel_quantities("weld", **VALID_WELD)
    assert result.quantity == pytest.approx(2.5)
    assert result.unit == "kg"
    assert "WELD-DETAIL-TEST-01" in result.formula


@pytest.mark.parametrize("missing", ["weld_unit_weight", "weld_unit_weight_unit", "weld_detail_ref"])
def test_weld_rejects_missing_engineering_basis(missing):
    params = {k: v for k, v in VALID_WELD.items() if k != missing}
    with pytest.raises((KeyError, ValueError), match="weld|جوش|مرجع|واحد"):
        steel_quantities("weld", **params)


@pytest.mark.parametrize("weight", [None, 0, -0.3, float("inf"), float("nan"), True, "NaN", "non-numeric"])
def test_weld_rejects_unverified_unit_weight(weight):
    with pytest.raises((TypeError, ValueError)):
        steel_quantities("weld", **{**VALID_WELD, "weld_unit_weight": weight})


@pytest.mark.parametrize("unit", ["kg", "g/m", "kg/m3", "", None, "KG/M"])
def test_weld_rejects_missing_or_wrong_weight_unit(unit):
    with pytest.raises(ValueError, match="واحد|kg/m"):
        steel_quantities("weld", **{**VALID_WELD, "weld_unit_weight_unit": unit})


@pytest.mark.parametrize("ref", ["", "   ", None])
def test_weld_requires_nonempty_detail_reference(ref):
    with pytest.raises(ValueError, match="مرجع|دیتایل"):
        steel_quantities("weld", **{**VALID_WELD, "weld_detail_ref": ref})


@pytest.mark.parametrize("length", [-1, float("nan"), float("inf"), True])
def test_weld_rejects_non_finite_or_invalid_length(length):
    with pytest.raises((ValueError, TypeError)):
        steel_quantities("weld", **{**VALID_WELD, "length": length})


def test_weld_does_not_change_structural_steel_member_calculation():
    assert steel_quantities("beam", length=10, unit_weight=30).quantity == 300
