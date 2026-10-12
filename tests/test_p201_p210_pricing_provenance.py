import pytest
from core.pricing.provenance_v1 import PriceApplication, PricingProvenance, validate_price_application

def registry():
    p=PricingProvenance()
    p.register_verified_source(source_id="official-1405",checksum="abc123",year=1405,license_status="verified",publisher="publisher")
    return p

def test_verified_application_is_deterministic():
    p=registry()
    a=PriceApplication("1001",10,2500,"official-1405","abc123",1405,"IRR",(1.1,0.9))
    x=p.apply(a); y=p.apply(a)
    assert x==y
    assert x["amount"]==24750.0
    assert p.fingerprint(x)==p.fingerprint(y)

def test_source_checksum_mismatch_fails_closed():
    with pytest.raises(ValueError): registry().apply(PriceApplication("1",1,1,"official-1405","bad",1405))

def test_year_mismatch_fails_closed():
    with pytest.raises(ValueError): registry().apply(PriceApplication("1",1,1,"official-1405","abc123",1404))

def test_unregistered_source_fails_closed():
    with pytest.raises(ValueError):
        PricingProvenance().apply(PriceApplication("1",1,1,"missing","x",1405))

@pytest.mark.parametrize("kwargs",[
    {"quantity":-1},{"unit_price":-1},{"dataset_year":1200},{"item_code":""},{"source_id":""},{"source_checksum":""}
])
def test_invalid_application_rejected(kwargs):
    base=dict(item_code="1",quantity=1,unit_price=1,source_id="s",source_checksum="c",dataset_year=1405)
    base.update(kwargs)
    with pytest.raises(ValueError): PriceApplication(**base).validate()

def test_row_required_fields():
    assert validate_price_application({"item_code":"1","quantity":1,"unit_price":1,"source_id":"s","source_checksum":"c","dataset_year":1405})==[]
    assert "source_checksum" in validate_price_application({"item_code":"1"})
