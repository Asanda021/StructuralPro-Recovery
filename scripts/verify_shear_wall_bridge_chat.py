"""Read-only demonstration of the shear-wall AEC bridge. No SQLite or Git writes."""
from pathlib import Path
from decimal import Decimal
import json

from core.takeoff.shear_wall_bridge_chat import compile_preview
from core.takeoff.commit_guards import rebuild_project_boq


def main():
    root = Path(__file__).resolve().parents[1]
    data = json.loads((root / "examples/shear_wall_chat_reference.json").read_text(encoding="utf-8"))
    project = {"id": data["project_id"], "takeoffs": [], "boq": []}
    bridge = compile_preview(data, project, reviewer="Synthetic independent reviewer", review_reference="Synthetic independent allocation check")
    _, boq = rebuild_project_boq(project, bridge["takeoff_candidates"])
    assert bridge["commit_allowed"] is False
    assert sum(Decimal(str(row["quantity"])) for row in boq if row["unit"] == "m3") == Decimal("3.5")
    assert sum(Decimal(str(row["quantity"])) for row in boq if row["unit"] == "m2") == Decimal("28")
    assert sum(Decimal(str(row["quantity"])) for row in boq if row["unit"] == "kg") == Decimal("84.944")
    print(json.dumps({"bridge_status": bridge["status"], "commit_allowed": bridge["commit_allowed"], "source_sha256": bridge["source_sha256"],
                      "candidate_takeoffs": len(bridge["takeoff_candidates"]), "in_memory_boq_rows": len(boq),
                      "concrete_m3": bridge["totals"]["net_concrete_m3"], "formwork_m2": bridge["totals"]["payable_formwork_m2"], "rebar_kg": bridge["totals"]["rebar_kg"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
