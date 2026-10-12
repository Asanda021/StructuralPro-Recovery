from core.platform.audit_integrity import seal_events,verify_chain
def test_chain_seals_and_verifies():
 e=[{"event_id":"1","action":"create"},{"event_id":"2","action":"edit"}]
 s=seal_events(e); assert verify_chain(s); assert s[1]["previous_hash"]==s[0]["hash"]
def test_tampering_is_detected():
 s=seal_events([{"event_id":"1","action":"create"},{"event_id":"2","action":"edit"}]); s[0]["action"]="delete"
 assert not verify_chain(s)
def test_reordering_is_detected():
 s=seal_events([{"event_id":"1","action":"create"},{"event_id":"2","action":"edit"}]); assert not verify_chain(list(reversed(s)))
def test_empty_chain_is_valid():
 assert verify_chain([])
