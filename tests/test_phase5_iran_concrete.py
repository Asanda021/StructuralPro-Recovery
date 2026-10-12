"""Phase 5 Iran concrete specialization regression tests."""
import pytest

from core.iran.concrete import (
    ROOF_CONCRETE_COEFFICIENTS,
    RebarLine,
    build_concrete_takeoff,
    concrete_volume,
)
from core.iran.boq import concrete_to_boq, member_catalog


def test_common_member_volume_is_explicit_geometry():
    assert concrete_volume("پی منفرد", length=2, width=2, height=0.5) == pytest.approx(2.0)
    assert concrete_volume("دال بتنی", area=120, thickness=0.15) == pytest.approx(18.0)


def test_roof_coefficients_are_explicit_not_hidden():
    assert ROOF_CONCRETE_COEFFICIENTS["تیرچه تک"] == pytest.approx(0.18)
    assert ROOF_CONCRETE_COEFFICIENTS["تیرچه دوبل"] == pytest.approx(0.23)
    assert concrete_volume("تیرچه تک", roof_area=100) == pytest.approx(18.0)


def test_rebar_weight_cut_length_and_12m_stock_count():
    line = RebarLine(
        diameter_mm=16, length_m=10, quantity=20,
        splice_length_m=1, waste_percent=5,
        role="main",
    )
    assert line.total_cut_length_m == pytest.approx(220)
    assert line.gross_length_m == pytest.approx(231)
    assert line.stock_bar_count == 20
    assert line.weight_kg == pytest.approx(231 * 16 * 16 / 162)


def test_coupler_and_splice_are_separate():
    line = RebarLine(diameter_mm=20, length_m=12, quantity=5,
                     splice_length_m=0.8, coupler_count=5, role="main")
    data = line.to_dict()
    assert data["splice_length_m"] == 0.8
    assert data["coupler_count"] == 5


def test_foundation_sanjaghi_and_stirrups_have_distinct_roles():
    result = build_concrete_takeoff(
        "پی منفرد",
        geometry={"length": 2, "width": 2, "height": 0.5},
        rebar=[
            {"diameter_mm": 12, "length_m": 1.8, "quantity": 20, "role": "main"},
            {"diameter_mm": 10, "length_m": 1.2, "quantity": 8, "role": "sanjaghi"},
            {"diameter_mm": 10, "length_m": 1.0, "quantity": 10, "role": "stirrup"},
        ],
    )
    roles = {x["role"] for x in result["rebar"]["lines"]}
    assert roles == {"main", "sanjaghi", "stirrup"}
    assert result["rebar"]["total_stock_bar_count"] > 0


def test_iran_boq_contains_concrete_and_rebar_rows():
    rows = concrete_to_boq(
        "ستون",
        {"length": 0.4, "width": 0.4, "height": 3},
        [{"diameter_mm": 16, "length_m": 3.6, "quantity": 8, "role": "main"}],
    )
    assert rows[0]["unit"] == "m3"
    assert rows[0]["category"] == "ساختمان بتنی ایران"
    assert rows[1]["unit"] == "kg"
    assert rows[1]["stock_bar_count_12m"] == 3


def test_member_catalog_is_deterministic_and_includes_common_members():
    rows = member_catalog()
    names = {x["member_type"] for x in rows}
    assert {"پی منفرد", "پی نواری", "رادیه", "ستون", "تیر", "دیوار", "دال بتنی"}.issubset(names)
