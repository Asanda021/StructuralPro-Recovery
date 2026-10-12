import math
import pytest
from core.takeoff.engine import TakeoffEngine, TakeoffRow


def row(unit, quantity, domain="building"):
    return TakeoffRow(domain=domain, item="sample", description="sample", quantity=quantity, unit=unit, formula="supplied")


def test_mixed_length_and_area_never_report_a_scalar_total_per_domain():
    got = TakeoffEngine.summarize([row("m", 10),row("m2",20)])
    assert got["quantity_by_domain"]["building"] is None
    assert got["quantity_by_domain_unit"]["building"]=={"m":10.0,"m2":20.0}
    assert got["mixed_unit_domains"] == ["building"]


def test_legacy_homogeneous_domain_and_aliases_keep_accurate_single_total():
    got = TakeoffEngine.summarize([row("m", 5),row("متر",2),row("kg",4,"steel")])
    assert got["quantity_by_domain"]=={"building":7.0,"steel":4.0}
    assert got["quantity_by_domain_unit"]=={"building":{"m":7.0},"steel":{"kg":4.0}}
    assert got["quantity_by_unit"]=={"m":7.0,"kg":4.0}


def test_mixed_dimension_unit_divisions_are_explicit():
    got = TakeoffEngine.summarize([row("m",5),row("cm",50),row("m3",3),row("عدد",2)])
    assert got["quantity_by_domain"]["building"] is None
    assert got["quantity_by_domain_unit"]["building"]=={"m":5.0,"cm":50.0,"m3":3.0,"عدد":2.0}
    assert got["quantity_by_unit"]=={"m":5.0,"cm":50.0,"m3":3.0,"عدد":2.0}


@pytest.mark.parametrize("quantity",[float("nan"),float("inf"),float("-inf"),-1,True,False])
def test_summary_rejects_invalid_quantities(quantity):
    with pytest.raises(ValueError): TakeoffEngine.summarize([row("m",quantity)])


def test_summary_rejects_dimensionally_unsupported_unit():
    with pytest.raises(ValueError): TakeoffEngine.summarize([row("no_unit",2)])


def test_aggregation_overflow_fails_closed_without_returning_infinity():
    with pytest.raises(ValueError): TakeoffEngine.summarize([row("m",1e308),row("m",1e308)])


def test_empty_summary_retains_existing_basics():
    got=TakeoffEngine.summarize([])
    assert got["row_count"]==0
    assert got["quantity_by_unit"]=={}
    assert got["quantity_by_domain"]=={}
    assert got["quantity_by_domain_unit"]=={}
    assert got["warnings"]==[]
