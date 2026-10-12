"""Production acceptance for P121-P125."""
from core.platform.p121_multitrade import TradeQuantity, normalize, summarize
from core.platform.p122_collaboration import CollaborationStore, RevisionConflict
from core.platform.p123_performance import aggregate
from core.platform.p124_security import safe_relative_path, redact, secret_fingerprint
from core.platform.p125_ux import Action, action_menu, validate_input

def run_acceptance() -> dict:
    rows = [
        TradeQuantity("E1", "civil", "CON", 2.0, "m3"),
        TradeQuantity("E1", "civil", "CON", 3.0, "m3"),
        TradeQuantity("E2", "electrical", "CABLE", 20.0, "m"),
    ]
    normalized = normalize(rows)
    assert len(normalized) == 2 and normalized[0].quantity + normalized[1].quantity > 0
    assert len(summarize(rows)["totals"]) == 2

    store = CollaborationStore()
    event = store.commit("P", "A", 0, "takeoff.edit", {"q": 5})
    assert event.revision == 1 and len(store.events("P")) == 1
    try:
        store.commit("P", "B", 0, "takeoff.edit", {"q": 6})
    except RevisionConflict:
        pass
    else:
        raise AssertionError("stale revision was accepted")

    perf = aggregate([{"trade":"civil","code":"CON","unit":"m3","quantity":2},
                      {"trade":"civil","code":"CON","unit":"m3","quantity":3}], chunk_size=1)
    assert perf[0]["quantity"] == 5

    assert safe_relative_path("reports/estimate.pdf") == "reports/estimate.pdf"
    try:
        safe_relative_path("../escape")
    except ValueError:
        pass
    else:
        raise AssertionError("path traversal accepted")
    assert "<redacted>" in redact("token=abc123")
    assert len(secret_fingerprint("abc")) == 64

    menu = action_menu([
        Action("back", "بازگشت", "Back", 2),
        Action("edit", "اصلاح", "Edit", 1),
        Action("calc", "محاسبه", "Calculate", 3),
    ])
    assert [x["id"] for x in menu] == ["edit", "back", "calc"]
    assert validate_input("  ok  ") == "ok"
    return {"P121": True, "P122": True, "P123": True, "P124": True, "P125": True}

if __name__ == "__main__":
    print(run_acceptance())
