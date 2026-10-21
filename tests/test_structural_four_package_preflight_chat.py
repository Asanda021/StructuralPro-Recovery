"""Four independently developed contracts, reassembled without Work edits."""
from copy import deepcopy
from pathlib import Path
import json
import pytest
from decimal import Decimal
from core.takeoff.structural_four_package_preflight_chat import audit, CombinedPreflightError
from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from core.takeoff.shared_rebar_ownership_chat import reconcile

ROOT=Path(__file__).resolve().parents[1]/"examples"

def load(name): return json.loads((ROOT/name).read_text(encoding="utf-8"))

def setup():
    p={"id":"P","takeoffs":[],"boq":[],"reviewed_aec_systems":{},"reviewed_structural_members":{},"beam_detail_register":{}}
    s=load("shear_wall_chat_reference.json")
    t=load("stair_chat_example.json");t["metadata"]["project_id"]="P" # synthetic fixture adjustment, not a hidden migration
    b=load("bored_pile_documented_synthetic.json")
    o=reconcile(load("rebar_shared_synthetic.json"),p)
    previews={
        "shear_wall":shear(s,p,reviewer="New Independent",review_reference="synthetic future cross-check"),
        "stair":stair(t,p,source_id="STAI-R1",reviewer="New Independent",ownership_reference="synthetic future cross-check"),
        "bored_pile":pile(b,p,independent_reviewer="New Independent",ownership_reference="synthetic future cross-check"),
    }
    sources={"shear_wall":s["source"]["source_id"],"stair":"STAI-R1","bored_pile":b["source"]["source_id"]}
    return previews,sources,o,p

def test_mixed_real_preview_only_union_and_owner_blockers():
    previews,sources,o,p=setup(); original=deepcopy((previews,sources,o,p))
    result=audit(previews,sources,o,p)
    assert result["status"]=="BLOCKED_FOR_COMMIT" and result["commit_allowed"] is False
    assert result["candidate_count"]==66 and result["dry_run_boq_count"]==14
    assert result["candidate_count_by_engine"]=={"shear_wall":5,"stair":58,"bored_pile":3}
    assert result["kg_rows"]>0 and len(result["unlinked_rebar_candidate_source_ids"])==result["kg_rows"]
    assert Decimal(result["preview_totals_by_unit"]["kg"])>0
    assert o["physical_bar_paid_once"] and result["ownership_blockers"]
    assert (previews,sources,o,p)==original
    assert audit(previews,sources,o,p)==result

@pytest.mark.parametrize("break_case",[
    "same_source", "missing_engine", "stolen_payment", "fake_approval",
    "duplicate_row_id", "duplicate_physical_operation", "wrong_source", "float_amount",
    "zero_amount", "nan_amount", "unknown_unit", "bad_boq_row_id",
    "wrong_owner_project", "no_owner_bar_list", "no_owner_blockers", "stale_project",
])
def test_fail_closed_compound_preflight(break_case):
    previews,sources,own,project=setup()
    if break_case=="same_source":sources["stair"]=sources["shear_wall"]
    elif break_case=="missing_engine":previews.pop("stair")
    elif break_case=="stolen_payment":previews["stair"]["commit_allowed"]=True
    elif break_case=="fake_approval":own["commit_allowed"]=True
    elif break_case=="duplicate_row_id":previews["stair"]["takeoff_candidates"][0]["id"]=previews["shear_wall"]["takeoff_candidates"][0]["source_id"];previews["stair"]["takeoff_candidates"][0]["source_id"]=previews["stair"]["takeoff_candidates"][0]["id"]
    elif break_case=="duplicate_physical_operation":
        a=previews["shear_wall"]["takeoff_candidates"][0];b=previews["stair"]["takeoff_candidates"][0]
        b["params"]["physical_component_id"]=a["params"]["physical_component_id"]
        b["quantities"][0]["code"]=a["quantities"][0]["code"]
    elif break_case=="wrong_source":previews["bored_pile"]["takeoff_candidates"][0]["provenance"]["source_id"]="NEW-FAKE"
    elif break_case=="float_amount":previews["stair"]["takeoff_candidates"][0]["quantities"][0]["amount"]=0.1
    elif break_case=="zero_amount":previews["stair"]["takeoff_candidates"][0]["quantities"][0]["amount"]="0"
    elif break_case=="nan_amount":previews["stair"]["takeoff_candidates"][0]["quantities"][0]["amount"]="NaN"
    elif break_case=="unknown_unit":previews["shear_wall"]["takeoff_candidates"][0]["quantities"][0]["unit"]="litre"
    elif break_case=="bad_boq_row_id":previews["shear_wall"]["takeoff_candidates"][0]["id"]="another"
    elif break_case=="wrong_owner_project":own["project_id"]="OTHER"
    elif break_case=="no_owner_bar_list":del own["physical_bar_paid_once"]
    elif break_case=="no_owner_blockers":own["blockers"]=[]
    elif break_case=="stale_project":project["takeoffs"].append(deepcopy(previews["shear_wall"]["takeoff_candidates"][0]))
    with pytest.raises((CombinedPreflightError,ValueError)):
        audit(previews,sources,own,project)
