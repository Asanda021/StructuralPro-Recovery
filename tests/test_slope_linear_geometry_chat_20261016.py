"""Independent synthetic mathematical references for linear slope geometry."""
from decimal import Decimal, localcontext

import pytest

from core.takeoff.slope_linear_geometry import POLICY, calculate_linear_slope


def sample(direction="x"):
    return {
        "policy": POLICY,
        "region_id": "REGION-SYNTHETIC-1",
        "source_ref": "SYNTHETIC-DRAWING-1",
        "approved_by": "SYNTHETIC-REVIEWER-NOT-REAL-APPROVAL",
        "material_ref": "SYNTHETIC-MATERIAL-1",
        "length_m": "5",
        "width_m": "4",
        "direction": direction,
        "start_thickness_m": "0.1",
        "end_thickness_m": "0.3",
        "openings": [],
    }


def void(ident="V1", x="1", y="1", length="1", width="1"):
    return {"id": ident, "source_ref": "SYNTHETIC-VOID-" + ident,
            "x_m": x, "y_m": y, "length_m": length,
            "width_m": width, "penetration": "full_depth"}


@pytest.mark.parametrize("direction", ["x", "y"])
def test_exact_gross_linear_gradient(direction):
    result = calculate_linear_slope(sample(direction))
    assert Decimal(result["gross_area_m2"]) == 20
    assert Decimal(result["gross_volume_m3"]) == 4
    assert result["boq_ready"] is False
    assert result["purchase_quantity"] is None


def test_x_axis_void_integrated_at_its_own_midpoint():
    d = sample("x")
    d["openings"] = [void()]
    result = calculate_linear_slope(d)
    # t(x)=.1+.2*x/5; 1m2 void whose x-centre=1.5 has t=.16m.
    assert Decimal(result["deducted_volume_m3"]) == Decimal("0.16")
    assert Decimal(result["net_volume_m3"]) == Decimal("3.84")
    assert Decimal(result["net_area_m2"]) == Decimal("19")


def test_y_axis_void_integrated_at_its_own_midpoint():
    d = sample("y")
    d["openings"] = [void()]
    result = calculate_linear_slope(d)
    # t(y)=.1+.2*y/4; 1m2 void whose y-centre=1.5 has t=.175m.
    assert Decimal(result["deducted_volume_m3"]) == Decimal("0.175")
    assert Decimal(result["net_volume_m3"]) == Decimal("3.825")


def test_adjoining_voids_not_counted_twice():
    d = sample()
    d["openings"] = [void("V1", "0", "0", "1", "1"),
                     void("V2", "1", "0", "1", "1")]
    result = calculate_linear_slope(d)
    # two unit voids at centre x=.5 (t=.12) and x=1.5 (t=.16)
    assert Decimal(result["deducted_volume_m3"]) == Decimal("0.28")
    assert Decimal(result["net_volume_m3"]) == Decimal("3.72")


def test_constant_thickness_is_documented_special_case():
    d = sample()
    d["start_thickness_m"] = "0.15"
    d["end_thickness_m"] = "0.15"
    d["openings"] = [void()]
    r = calculate_linear_slope(d)
    assert Decimal(r["gross_volume_m3"]) == 3
    assert Decimal(r["net_volume_m3"]) == Decimal("2.85")


def test_exact_high_precision_decimal_not_float():
    d = sample()
    d["length_m"] = "1.00000000000000000000000000001"
    d["width_m"] = "1"
    d["start_thickness_m"] = "0.12345678901234567890123456789"
    d["end_thickness_m"] = "0.12345678901234567890123456789"
    result = calculate_linear_slope(d)
    with localcontext() as ctx:
        ctx.prec = 128
        expected = Decimal(d["length_m"]) * Decimal(d["start_thickness_m"])
    assert Decimal(result["net_volume_m3"]) == expected
    assert isinstance(result["net_volume_m3"], str)


@pytest.mark.parametrize("failure", [
    "missing_field", "unknown_field", "policy", "metadata", "negative", "zero_area",
    "zero_thickness", "axis", "openings_shape", "opening_unknown", "opening_negative",
    "opening_outside", "opening_overlap", "opening_repeat_id", "opening_repeat_source",
    "opening_source_same_as_region", "opening_partial", "all_void", "nan", "bool",
    "nonrectangular", "untrusted_waste", "missing_material",
])
def test_fail_closed_for_unsupported_or_undocumented_inputs(failure):
    d = sample()
    if failure == "missing_field": d.pop("source_ref")
    elif failure == "unknown_field": d["unverified_slope"] = "5%"
    elif failure == "policy": d["policy"] = "guess_v1"
    elif failure == "metadata": d["source_ref"] = ""
    elif failure == "negative": d["start_thickness_m"] = "-0.01"
    elif failure == "zero_area": d["length_m"] = "0"
    elif failure == "zero_thickness": d["start_thickness_m"] = d["end_thickness_m"] = "0"
    elif failure == "axis": d["direction"] = "diagonal"
    elif failure == "openings_shape": d["openings"] = {"x": 1}
    elif failure == "opening_unknown":
        d["openings"] = [dict(void(), angled=True)]
    elif failure == "opening_negative": d["openings"] = [void(x="-0.1")]
    elif failure == "opening_outside": d["openings"] = [void(x="4.5")]
    elif failure == "opening_overlap": d["openings"] = [void(), void("V2", "1.5")]
    elif failure == "opening_repeat_id": d["openings"] = [void(), void()]
    elif failure == "opening_repeat_source":
        d["openings"] = [void(), dict(void("V2", "3"), source_ref="SYNTHETIC-VOID-V1")]
    elif failure == "opening_source_same_as_region":
        d["openings"] = [dict(void(), source_ref=d["source_ref"])]
    elif failure == "opening_partial":
        d["openings"] = [dict(void(), penetration="partial_depth")]
    elif failure == "all_void": d["openings"] = [void(x="0", y="0", length="5", width="4")]
    elif failure == "nan": d["end_thickness_m"] = "NaN"
    elif failure == "bool": d["length_m"] = True
    elif failure == "nonrectangular": d["shape"] = "triangle"
    elif failure == "untrusted_waste": d["waste_pct"] = "15"
    elif failure == "missing_material": d["material_ref"] = None
    with pytest.raises(ValueError):
        calculate_linear_slope(d)


def test_outside_an_edge_by_one_exact_decimal_digit_is_rejected():
    d = sample()
    d["openings"] = [void(x="4.0000000000000000001", length="1")]
    with pytest.raises(ValueError):calculate_linear_slope(d)


def test_bad_extra_openings_blocked_without_truncation():
    d = sample()
    d["openings"] = [void(str(i), x="0", y="0", length="0.001", width="0.001") for i in range(129)]
    with pytest.raises(ValueError):calculate_linear_slope(d)
