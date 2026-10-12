"""Phase 20 acceptance tests."""
from core.revision.phase20 import RevisionManagementWorkflow

def payload(q=10, desc="beam"):
    return {
        "drawing":[{"source_id":"g1","length":q}],
        "elements":[{"element_id":"E1","kind":"beam","quantity":q}],
        "takeoff":[{"element_id":"E1","quantity":q}],
        "boq":[{"item_code":"B1","quantity":q,"description":desc}],
        "estimate":{"cost":{"grand_total":q*100},"factors":{"waste":1.0}},
    }

def test_p20_version_overlay_change_and_impact():
    wf=RevisionManagementWorkflow()
    old=wf.snapshot("R1",payload(),label="Base")
    new=wf.snapshot("R2",payload(12,"beam revised"),label="Rev 2",parent_revision_id="R1")
    result=wf.compare(old,new)
    assert result.comparison.revision_id=="R2"
    assert result.impact["parent_revision_id"]=="R1"
    assert result.impact["quantity_delta_present"]
    assert result.impact["affected_sections"]
    assert any(x["status"]=="quantity-changed" for x in result.change_detection)
    assert result.overlay

def test_p20_added_removed_and_history():
    wf=RevisionManagementWorkflow()
    old=wf.snapshot("R1",payload())
    p=payload()
    p["elements"].append({"element_id":"E2","kind":"column","quantity":5})
    new=wf.snapshot("R2",p,parent_revision_id="R1")
    result=wf.compare(old,new)
    assert any(x["status"]=="added" and x["section"]=="elements" for x in result.change_detection)
    assert len(result.history)==2
    exported=wf.export(result)
    assert exported["revision_id"]=="R2"

def test_p20_parent_mismatch_fails_closed():
    wf=RevisionManagementWorkflow()
    old=wf.snapshot("R1",payload())
    new=wf.snapshot("R2",payload(),parent_revision_id="OTHER")
    try:
        wf.compare(old,new)
    except ValueError as exc:
        assert "parent" in str(exc)
    else:
        raise AssertionError("parent mismatch must fail closed")
