from core.automation.technical_office_v1 import build_plan, advance

def test_pipeline_order_and_fingerprint_are_deterministic():
    stages = {
        "drawing":[{"item_id":"d1","source_id":"sheet-A"}],
        "takeoff":[{"item_id":"t1","source_id":"sheet-A"}],
        "boq":[{"item_id":"b1","source_id":"t1","requires_review":True}],
        "estimate":[{"item_id":"e1","source_id":"price-v1"}],
        "report":[{"item_id":"r1","source_id":"b1"}],
    }
    a=build_plan("P", stages); b=build_plan("P", stages)
    assert [x.stage for x in a.items] == ["drawing","takeoff","boq","estimate","report"]
    assert a.fingerprint == b.fingerprint
    assert a.review_required == ("b1",)

def test_review_never_auto_approves():
    plan=build_plan("P", {"boq":[{"item_id":"b1","source_id":"t1","requires_review":True}]})
    blocked=advance(plan,{})
    assert blocked.items[0].status=="blocked"

def test_explicit_approval_is_required():
    plan=build_plan("P", {"boq":[{"item_id":"b1","source_id":"t1","requires_review":True}]})
    approved=advance(plan,{"b1":True})
    assert approved.items[0].status=="approved"

def test_missing_provenance_fails_closed():
    try: build_plan("P", {"drawing":[{"item_id":"d1"}]})
    except ValueError: pass
    else: raise AssertionError("missing source must fail")

def test_empty_plan_fails_closed():
    try: build_plan("P", {})
    except ValueError: pass
    else: raise AssertionError("empty plan must fail")

def test_invalid_stage_is_rejected():
    try: build_plan("P", {"bad":[{"item_id":"x","source_id":"s"}]})
    except ValueError: pass
    else: raise AssertionError("unknown stage must fail")
