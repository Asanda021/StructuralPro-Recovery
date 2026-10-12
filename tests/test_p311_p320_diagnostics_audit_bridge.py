from core.platform.diagnostics import DiagnosticEvent
from core.platform.diagnostics_audit_bridge_v1 import bridge_events, verify_bridged_events

def test_bridge_is_privacy_safe_and_chain_is_valid():
    events=bridge_events([DiagnosticEvent("E1",details={"token":"abc","module":"engine"}),
                          DiagnosticEvent("E2",severity="warning",details={"user":"local"})])
    assert events[0]["details"]["token"]=="<redacted>"
    assert verify_bridged_events(events)

def test_tampering_breaks_chain():
    events=bridge_events([DiagnosticEvent("E1",details={"x":"1"}),
                          DiagnosticEvent("E2",details={"x":"2"})])
    events[1]["message"]="tampered"
    assert not verify_bridged_events(events)

def test_order_is_material_to_chain():
    a=bridge_events([DiagnosticEvent("E1"),DiagnosticEvent("E2")])
    b=bridge_events([DiagnosticEvent("E2"),DiagnosticEvent("E1")])
    assert a != b
    assert verify_bridged_events(a)
    assert verify_bridged_events(b)
