from core.acceptance.p11_p50_audit import EVIDENCE, PHASES, audit_summary, phase_priorities

def test_phases_2_to_5_are_exactly_four_ten_priority_blocks():
    assert tuple(PHASES) == (2, 3, 4, 5)
    assert all(len(items) == 10 for items in PHASES.values())
    assert [p for items in PHASES.values() for p in items] == list(range(11, 51))

def test_all_p11_p50_have_historical_evidence_records():
    assert set(EVIDENCE) == set(range(11, 51))
    assert all(len(item.evidence_commit) == 40 for item in EVIDENCE.values())

def test_phase_lookup_is_fail_closed():
    assert phase_priorities(2) == tuple(range(11, 21))
    assert phase_priorities(5) == tuple(range(41, 51))
    import pytest
    with pytest.raises(ValueError):
        phase_priorities(1)

def test_audit_does_not_fabricate_current_green():
    summary = audit_summary()
    assert summary["all_historical_evidence_present"] is True
    assert summary["current_green"] is False
