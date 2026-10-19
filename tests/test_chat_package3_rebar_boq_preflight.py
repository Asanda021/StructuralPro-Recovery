"""Read-only detection of physical bar collisions in historical BOQ entries."""
from copy import deepcopy
import pytest
from core.takeoff.shared_rebar_ownership_chat import reconcile,RebarOwnershipError
from test_shared_rebar_ownership_chat import sample

@pytest.mark.parametrize("placement",["row","params"])
def test_historical_boq_collision_blocks_independent_clearance(placement):
    document=sample(False)
    row={"source_id":"BOQ-OLD","description":"میلگرد تیر","item_code":"beam_rebar"}
    if placement=="row":
        row["physical_bar_id"]="BAR-A"
    else:
        row["params"]={"physical_bar_id":"BAR-A"}
    project={"id":"P","takeoffs":[],"boq":[row]}
    before=deepcopy((project,document))
    result=reconcile(document,project)
    assert result["commit_allowed"] is False
    assert "BAR-A" in " ".join(result["blockers"])
    assert "BOQ" in " ".join(result["blockers"])
    assert (project,document)==before

def test_old_rebar_boq_without_physical_id_is_not_cleared():
    result=reconcile(sample(False),{"id":"P","takeoffs":[],
                 "boq":[{"source_id":"OLD","description":"آرماتور ستون"}]})
    assert result["commit_allowed"] is False
    assert any("فاقد هویت" in message and "BOQ" in message
               for message in result["blockers"])

def test_unrelated_boq_still_requires_financial_reconciliation():
    result=reconcile(sample(False),{"id":"P","takeoffs":[],
                 "boq":[{"description":"سایر عملیات"}]})
    assert result["commit_allowed"] is False
    assert any("BOQ" in message for message in result["blockers"])

@pytest.mark.parametrize("invalid",[
    None,"broken",{},["bad"],
])
def test_malformed_boq_book_rejected(invalid):
    with pytest.raises(RebarOwnershipError):
        reconcile(sample(False),{"id":"P","takeoffs":[],"boq":invalid})

@pytest.mark.parametrize("bad",[1," BAR-A ","",True])
def test_invalid_physical_id_never_normalized_into_payment(bad):
    with pytest.raises(RebarOwnershipError):
        reconcile(sample(False),{"id":"P","takeoffs":[],
                  "boq":[{"physical_bar_id":bad}]})

def test_conflicting_ids_in_one_boq_row_fail_closed():
    with pytest.raises(RebarOwnershipError):
        reconcile(sample(False),{"id":"P","takeoffs":[],
                  "boq":[{"physical_bar_id":"BAR-A",
                          "params":{"physical_bar_id":"BAR-B"}}]})
