"""P83 construction quantity core contract tests."""
import pytest
from core.takeoff.construction_core import ConstructionQuantityCore, validate_quantity_lines
from core.takeoff.element_model import ConstructionElement

def test_concrete_slab_volume_and_explicit_waste():
    e=ConstructionElement("SLAB-1","slab",area_m2=100,thickness_m=0.20,source_id="D1")
    row=ConstructionQuantityCore.slab_volume(e,waste_rate=0.03)
    assert row.quantity == pytest.approx(20.0)
    assert row.gross_quantity == pytest.approx(20.6)

def test_rectangular_concrete_rejects_missing_dimension():
    e=ConstructionElement("COL-1","column",length_m=0.4,width_m=0.4,source_id="D2")
    with pytest.raises(ValueError): ConstructionQuantityCore.rectangular_volume(e)

def test_rebar_weight_uses_explicit_diameter_formula():
    row=ConstructionQuantityCore.rebar_weight("R1",12,16,10,source_id="D3")
    assert row.quantity == pytest.approx(189.62962963)
    assert row.metadata["unit_weight_kg_m"] == pytest.approx(16**2/162)

def test_steel_weight_is_input_driven_not_hidden_coefficient():
    row=ConstructionQuantityCore.steel_weight("S1",20,12.5,4,source_id="D4")
    assert row.quantity == pytest.approx(1000)

def test_masonry_and_finish_area_exclude_openings():
    e=ConstructionElement("W1","wall",length_m=10,height_m=3,source_id="D5")
    masonry=ConstructionQuantityCore.wall_masonry(e,openings_m2=2)
    finish=ConstructionQuantityCore.finish_area(e,"PLASTER","Plaster",openings_m2=2)
    assert masonry.quantity == pytest.approx(28)
    assert finish.quantity == pytest.approx(28)

def test_linear_and_counted_trade_quantities():
    e=ConstructionElement("M1","pipe",length_m=15,quantity_count=2,source_id="D6")
    pipe=ConstructionQuantityCore.linear_material(e,"plumbing","PIPE","Pipe")
    assert pipe.quantity == pytest.approx(30)
    d=ConstructionElement("D1","door",quantity_count=7,source_id="D7")
    door=ConstructionQuantityCore.counted_item(d,"doors_windows","DOOR","Door")
    assert door.quantity == pytest.approx(7)

def test_aggregation_separates_domain_item_and_unit():
    a=ConstructionQuantityCore.counted_item(ConstructionElement("A","x",2,source_id="A"),"doors_windows","DOOR","Door")
    b=ConstructionQuantityCore.counted_item(ConstructionElement("B","x",3,source_id="B"),"doors_windows","DOOR","Door")
    assert ConstructionQuantityCore.aggregate([a,b])[("doors_windows","DOOR","عدد")] == 5

def test_validation_catches_duplicate_sources():
    a=ConstructionQuantityCore.counted_item(ConstructionElement("A","x",1,source_id="SRC"),"doors_windows","DOOR","Door")
    b=ConstructionQuantityCore.counted_item(ConstructionElement("B","x",1,source_id="SRC"),"doors_windows","DOOR","Door")
    assert not validate_quantity_lines([a,b])["ok"]

def test_units_and_waste_are_distinct():
    row=ConstructionQuantityCore.steel_weight("S2",100,10,1,source_id="S2",waste_rate=0.05)
    converted=ConstructionQuantityCore.convert_line(row,"ton")
    assert converted.quantity == pytest.approx(1.0)
    assert converted.gross_quantity == pytest.approx(1.05)
