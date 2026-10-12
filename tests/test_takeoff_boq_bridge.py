from core.drawings.takeoff_boq import DrawingTakeoffBOQBridge

def test_prepare_preserves_provenance_and_confirmation():
    bridge=DrawingTakeoffBOQBridge()
    rows=bridge.prepare([{
        "id":"TO-00001","source_ref":"plan.pdf#page=2&takeoff=TO-00001",
        "label":"Wall","quantity":12.5,"unit":"m","confidence":0.8,
        "needs_confirmation":True
    }])
    assert rows[0].confirmed is False
    assert rows[0].source_ref.startswith("plan.pdf#page=2")

def test_confirm_then_to_boq():
    bridge=DrawingTakeoffBOQBridge(lambda code: 100.0)
    links=bridge.prepare([{
        "id":"TO-1","source_ref":"dxf#takeoff=TO-1","description":"Beam",
        "quantity":2,"unit":"m","price_code":"B01","confirmed":False
    }])
    links=bridge.confirm(links,approved_ids=["TO-1"])
    rows=bridge.to_boq(links)
    assert rows[0]["quantity"] == 2
    assert rows[0]["total"] == 200

def test_unconfirmed_rows_are_not_exported_by_default():
    bridge=DrawingTakeoffBOQBridge()
    links=bridge.prepare([{
        "id":"TO-1","source_ref":"drawing#1","description":"Area",
        "quantity":5,"unit":"m2","needs_confirmation":True
    }])
    assert bridge.to_boq(links) == []
