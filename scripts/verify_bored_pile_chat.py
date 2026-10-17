"""Print preview of synthetic pile quantities; no database side effect."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.takeoff.bored_pile_specialist_chat import compile_piles
from core.takeoff.bored_pile_bridge_chat import compile_preview

if __name__ == '__main__':
    base=Path(__file__).resolve().parents[1]
    data=json.loads((base/'examples/bored_pile_documented_synthetic.json').read_text(encoding='utf8'))
    preview=compile_preview(data,{'id':'P','takeoffs':[]},independent_reviewer='IndependentReviewer',ownership_reference='signed-synthetic-owner-ledger')
    print(json.dumps({"engine":compile_piles(data)["totals"],"handoff_status":preview['status'],
                      "commit_allowed":preview['commit_allowed'],"rows":preview['preview_rows']},ensure_ascii=False,indent=2))
