"""Offline synthetic cross-package inspection; never authorizes payment or commits."""
from __future__ import annotations
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.takeoff.shear_wall_bridge_chat import compile_preview as shear
from core.takeoff.stair_bridge_chat import compile_preview as stair
from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
from core.takeoff.shared_rebar_ownership_chat import reconcile
from core.takeoff.structural_four_package_preflight_chat import audit

def read(name):
    return json.loads((ROOT/"examples"/name).read_text(encoding="utf-8"))

def verify():
    project={"id":"P","takeoffs":[],"boq":[],"reviewed_aec_systems":{},
             "reviewed_structural_members":{},"beam_detail_register":{}}
    wall=read("shear_wall_chat_reference.json")
    stair_input=read("stair_chat_example.json")
    # Synthetic alignment of project identity only; unchanged source file and engine.
    stair_input["metadata"]["project_id"]="P"
    pile_input=read("bored_pile_documented_synthetic.json")
    owner=reconcile(read("rebar_shared_synthetic.json"),project)
    previews={
        "shear_wall":shear(wall,project,reviewer="Independent Audit",
                           review_reference="synthetic pending signed ownership"),
        "stair":stair(stair_input,project,source_id="STAI-R1",reviewer="Independent Audit",
                      ownership_reference="synthetic pending signed ownership"),
        "bored_pile":pile(pile_input,project,independent_reviewer="Independent Audit",
                          ownership_reference="synthetic pending signed ownership"),
    }
    source_ids={"shear_wall":wall["source"]["source_id"],"stair":"STAI-R1",
                "bored_pile":pile_input["source"]["source_id"]}
    return audit(previews,source_ids,owner,project)

if __name__=="__main__":
    result=verify()
    print(json.dumps(result,ensure_ascii=False,indent=2))
