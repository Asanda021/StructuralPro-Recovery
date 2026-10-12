from core.estimate.pricebook_mapping_v2 import map_items, mapping_gate

def test_mapping_gate_green_only_for_exact_rows():
    items=[{"takeoff_id":"T1","description":"بتن C25","unit":"m3"}]
    candidates=[{"item_code":"0101","description":"بتن C25","unit":"m3"}]
    result=mapping_gate(map_items(items,candidates,require_exact=True))
    assert result["green"] and result["exact_ratio"]==1.0

def test_mapping_gate_blocks_review():
    items=[{"takeoff_id":"T1","description":"بتن معمولی","unit":"m3"}]
    candidates=[{"item_code":"0101","description":"بتن C25","unit":"m3"}]
    result=mapping_gate(map_items(items,candidates,require_exact=True))
    assert not result["green"] and result["review_required"]==["T1"]
