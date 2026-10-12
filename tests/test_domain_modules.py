"""Tests for cross-domain quantity engines."""
from core.takeoff.modules import (
    calculate_building_item,
    calculate_mechanical_item,
    calculate_electrical_item,
    calculate_civil_item,
)

def test_building_wall_net_area():
    r=calculate_building_item("wall",length=5,height=3,openings=2)
    assert r.quantity==13
    assert r.unit=="m2"

def test_building_slab_concrete():
    r=calculate_building_item("slab_volume",length=6,width=4,thickness=.2)
    assert round(r.quantity,6)==4.8

def test_mechanical_duct_area():
    r=calculate_mechanical_item("duct_area",width=.4,height=.3,length=10)
    assert round(r.quantity,6)==14

def test_electrical_cable():
    r=calculate_electrical_item("cable",length=25,count=3)
    assert r.quantity==75
    assert r.unit=="m"

def test_civil_excavation():
    r=calculate_civil_item("excavation",length=10,width=4,depth=1.5)
    assert r.quantity==60
    assert r.unit=="m3"
