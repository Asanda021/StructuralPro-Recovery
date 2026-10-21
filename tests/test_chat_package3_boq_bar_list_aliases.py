"""Conservative grouped/aliased historical BOQ identities: no financial authorization."""
import pytest
from core.takeoff.shared_rebar_ownership_chat import reconcile,RebarOwnershipError
from test_shared_rebar_ownership_chat import sample

@pytest.mark.parametrize("row",[
 {"physical_bar_id":"BAR-A"},
 {"physical_bar_id":"bar-a"},
 {"physical_bar_ids":["BAR-A","BAR-B"]},
 {"params":{"physical_bar_ids":["BAR-A"]}},
])
def test_historical_scalar_alias_or_group_reports_possible_duplicate(row):
    project={"id":"P","takeoffs":[],"boq":[row]}
    out=reconcile(sample(False),project)
    assert out["commit_allowed"] is False
    assert out["status"]=="preview_only_not_integrated"
    assert any("BOQ" in message and "BAR-A" in message.upper()
               for message in out["blockers"])

@pytest.mark.parametrize("row",[
 {"physical_bar_ids":[]},
 {"physical_bar_ids":"BAR-A"},
 {"physical_bar_ids":["BAR-A","BAR-A"]},
 {"physical_bar_ids":["BAR-A","bar-a"]},
 {"physical_bar_ids":[" BAR-A"]},
 {"physical_bar_id":"BAR-A","physical_bar_ids":["BAR-B"]},
 {"physical_bar_ids":["BAR-A"],"params":{"physical_bar_ids":["BAR-B"]}},
 {"physical_bar_id":False},
])
def test_inconsistent_multi_bar_boq_never_silently_clears(row):
    with pytest.raises(RebarOwnershipError):
        reconcile(sample(False),{"id":"P","takeoffs":[],"boq":[row]})

def test_old_rebar_code_without_physical_id_remains_blocked():
    out=reconcile(sample(False),{"id":"P","takeoffs":[],
              "boq":[{"item_code":"beam_rebar","description":"آرماتور"}]})
    assert not out["commit_allowed"]
    assert any("فاقد هویت" in message for message in out["blockers"])

def test_unrelated_boq_row_does_not_invent_rebar_collision():
    out=reconcile(sample(False),{"id":"P","takeoffs":[],
              "boq":[{"item_code":"paint","description":"رنگ"}]})
    assert not out["commit_allowed"]
    assert any("BOQ" in message for message in out["blockers"])
