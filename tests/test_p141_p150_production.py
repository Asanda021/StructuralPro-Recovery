from core.intelligence.p141_p150 import *

def test_p141_to_p147_regional_rule_and_mapping():
    rule = validate_regional_rule(RegionalRule("IR", "fa", "IRR", .09))
    assert rule.currency == "IRR"
    assert map_standard("ACI 318", "IR")["mapped"]

def test_p141_invalid_rule_fails_closed():
    try: validate_regional_rule(RegionalRule("XX", "fa", "IRR"))
    except ValueError: pass
    else: assert False

def test_p145_pricebook_is_normalized_and_traced():
    rows = normalize_pricebook([PricePoint("Concrete","m3","IRR",100,"official","1405")])
    assert rows[0].source == "official"

def test_p148_forecast_is_deterministic():
    assert cost_forecast([HistoricalObservation("1403",1000,10), HistoricalObservation("1404",1200,10)], 1) == 110

def test_p150_price_risk_is_visible():
    signals = cost_risk([PricePoint("Concrete","m3","IRR",100,"a","1404"),
                         PricePoint("Concrete","m3","IRR",140,"b","1404")], .15)
    assert any(s.code == "P150-PRICE-VARIANCE" for s in signals)

def test_digest_is_stable():
    r = RegionalRule("IR","fa","IRR")
    p = [PricePoint("A","u","IRR",10,"s","1405")]
    assert deterministic_intelligence_digest(r,p) == deterministic_intelligence_digest(r,p)
