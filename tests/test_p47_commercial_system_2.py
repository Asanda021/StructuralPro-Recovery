from datetime import date, timedelta
import pytest
from core.commercial.commercial_system_v2 import *

def lic(status="active"):
    return License("L1","U1","professional",date(2026,1,1),date(2026,12,31),status)

def test_entitlement_and_summary():
    x=lic(); assert entitlement(x,feature="reports",today=date(2026,10,4))
    assert not entitlement(lic("revoked"),feature="reports",today=date(2026,10,4))
    assert subscription_summary([x])["active"]==1

def test_commercial_contract_fails_closed():
    with pytest.raises(ValueError): validate_license(License("L","U","gold",date(2026,1,1),date(2026,1,2)))
    with pytest.raises(ValueError): validate_license(License("L","U","standard",date(2026,2,1),date(2026,1,2)))
    with pytest.raises(ValueError): subscription_summary([lic(),lic()])
