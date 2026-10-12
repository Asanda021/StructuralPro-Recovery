from core.takeoff_workbench_v1 import TakeoffItem, UniversalTakeoffWorkbench, WorkbenchAction
import pytest

def item(item_id="b1", discipline="structural", qty=10.0, unit="m3", confidence=.95, status="draft"):
    return TakeoffItem(item_id,discipline,"member","beam",("sheet-A",),qty,unit,"length*section",confidence,status,"A").validate()

def test_accepts_multi_discipline_items():
    w=UniversalTakeoffWorkbench()
    items=[item("b1","structural",10,"m3"),item("wall1","architectural",25,"m2"),item("pipe1","mechanical",40,"m"),item("c1","electrical",70,"m"),item("site1","site",100,"m2")]
    accepted=tuple(w.accept(x) for x in items)
    assert {x.discipline for x in accepted}=={"structural","architectural","mechanical","electrical","site"}

def test_low_confidence_cannot_be_accepted():
    with pytest.raises(ValueError): UniversalTakeoffWorkbench().accept(item(confidence=.79))

def test_missing_source_fails_closed():
    with pytest.raises(ValueError): TakeoffItem("b1","structural","member","beam",(),10,"m3","f",.95).validate()

def test_deterministic_fingerprint_is_order_independent():
    w=UniversalTakeoffWorkbench(); a=item("a"); b=item("b")
    assert w.fingerprint([a,b])==w.fingerprint([b,a])

def test_stale_action_is_rejected():
    w=UniversalTakeoffWorkbench(); current=(item(),)
    with pytest.raises(ValueError,match="stale"): w.apply(current,WorkbenchAction("remove","b1","stale","x"))

def test_add_requires_exact_after_fingerprint():
    w=UniversalTakeoffWorkbench(); current=(); new=item("a")
    action=WorkbenchAction("add","a",w.fingerprint(current),w.fingerprint((new,)))
    assert w.apply(current,action,new)==(new,)

def test_edit_and_revision_are_preserved():
    w=UniversalTakeoffWorkbench(); old=item("a")
    new=TakeoffItem("a","architectural","finish","paint",("sheet-B",),35,"m2","room_perimeter*height",.92,"draft","B").validate()
    action=WorkbenchAction("edit","a",w.fingerprint((old,)),w.fingerprint((new,)),"revision B")
    out=w.apply((old,),action,new)
    assert out[0].revision=="B" and out[0].source_ids==("sheet-B",)

def test_accept_action_requires_matching_after_state():
    w=UniversalTakeoffWorkbench(); old=item("a"); accepted=w.accept(old)
    action=WorkbenchAction("accept","a",w.fingerprint((old,)),w.fingerprint((accepted,)))
    assert w.apply((old,),action)==(accepted,)

def test_summary_only_counts_accepted_quantities():
    w=UniversalTakeoffWorkbench()
    rows=w.summarize([w.accept(item("a","structural",5)),item("b","structural",99)])
    assert rows[0]["accepted_quantity"]==5.0
