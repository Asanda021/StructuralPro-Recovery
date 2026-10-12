from __future__ import annotations

REQUIRED_WORKFLOW_ACTIONS = ("edit", "back", "menu", "restart", "review", "calculate")


def validate_workflow(workflow: dict) -> dict:
    actions = set(workflow.get("actions", []))
    missing = [x for x in REQUIRED_WORKFLOW_ACTIONS if x not in actions]
    rtl = workflow.get("rtl", False)
    stage_input = workflow.get("stage_input", False)
    review_gate = workflow.get("review_gate", False)
    return {
        "missing_actions": missing,
        "rtl": rtl,
        "stage_input": stage_input,
        "review_gate": review_gate,
        "green2": not missing and rtl and stage_input and review_gate,
    }


def score_product_surface(surfaces: list[dict]) -> dict:
    if not surfaces:
        raise ValueError("surfaces required")
    valid = sum(bool(validate_workflow(s)["green2"]) for s in surfaces)
    ratio = valid / len(surfaces)
    return {"surfaces": len(surfaces), "green2_ratio": ratio, "green2": ratio >= 0.95}
