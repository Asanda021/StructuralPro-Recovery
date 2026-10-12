from core.acceptance.p111_p115 import run_all

def test_p111_p115_acceptance_all():
    result=run_all()
    assert result["P111"]["verified"] is True
    assert result["P111"]["official"] is False
    assert all(result["P112"]["files"].values())
    assert "شرح" in result["P112"]["rtl_columns"]
    assert result["P113"]["cost_delta"]==20
    assert result["P113"]["finalizable"] is False
    assert any(x["review_required"] for x in result["P113"]["changes"])
    assert result["P114"]["snapshot"]["large_project"] is True
    assert result["P114"]["page"]["total"]==10000
    assert result["P115"]["hardening"]["ok"] is True
    assert result["P115"]["version"].count(".")==2
