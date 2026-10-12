from core.acceptance.p121_p125 import run_acceptance

def test_p121_p125_acceptance():
    result = run_acceptance()
    assert result == {"P121": True, "P122": True, "P123": True, "P124": True, "P125": True}
