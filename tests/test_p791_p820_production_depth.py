from datetime import date
from decimal import Decimal
import pytest

from core.engineering.production_quantity_scenarios_v1 import production_scenarios
from core.takeoff.production_acceptance_v1 import accept_takeoff_to_estimate
from core.pricing.iranian_price_data_production_pipeline_v1 import PriceRecord
from core.reports.production_acceptance_bundle_v1 import build_acceptance_bundle, validate_acceptance_bundle

def test_deep_quantity_scenarios_are_deterministic_and_complete():
    a, b = production_scenarios(), production_scenarios()
    assert a == b and len(a) == 6
    for row in a:
        assert row["concrete_m3"] >= 0
        assert row["rebar_kg"] >= 0
        assert row["stock_bar_count"] >= 0
        assert "cut_list" in row

def test_takeoff_boq_estimate_preserves_quantity_and_provenance():
    prices=(PriceRecord("CONC","Concrete","m3",Decimal("1000000"),"IRR",date(2026,1,1),"OFFICIAL","1405","pack://1405/concrete"),)
    takeoff=[{"item_code":"CONC","description":"Concrete","quantity":2.5,"unit":"m3","source":"scenario"}]
    result=accept_takeoff_to_estimate(takeoff, prices, as_of=date(2026,10,1))
    assert result["finalizable"] is True
    assert result["boq"][0]["quantity"] == 2.5
    assert result["price_provenance"][0]["source_version"] == "1405"

def test_missing_price_fails_closed():
    prices=(PriceRecord("REBAR","Rebar","kg",Decimal("500000"),"IRR",date(2026,1,1),"OFFICIAL","1405","pack://1405/rebar"),)
    with pytest.raises(LookupError):
        accept_takeoff_to_estimate([{"item_code":"CONC","quantity":1,"unit":"m3"}], prices, as_of=date(2026,10,1))

def test_acceptance_bundle_fingerprint_and_tamper_detection():
    b=build_acceptance_bundle(project_id="GOLDEN-P791-001",revision="R1",
                              takeoff=[{"item_code":"CONC","quantity":2.5}],
                              boq=[{"item_code":"CONC","quantity":2.5}],
                              estimate={"grand_total":2500000},
                              provenance=[{"source_version":"1405"}])
    assert validate_acceptance_bundle(b)["valid"]
    b["boq"][0]["quantity"]=9.0
    with pytest.raises(ValueError):
        validate_acceptance_bundle(b)

def test_empty_inputs_fail_closed():
    with pytest.raises(ValueError):
        accept_takeoff_to_estimate([], (), as_of=date(2026,10,1))
