from core.engineering.domains import concrete_quantities, steel_quantities, masonry_quantities, foundation_quantities
from core.standards import default_iran_registry

def test_standards_registry_is_versioned_and_auditable():
    reg=default_iran_registry(); result=reg.validate()
    assert result["ok"] and result["source_count"] >= 6 and result["rule_count"] >= 6
    assert reg.source("IR-NBR-09").edition == "1399"
    assert reg.source("IR-NBR-10").edition == "1401"
    assert reg.source("IR-PRICE-1404").edition == "1404"
    assert any(r.source_code == "IR-NBR-09" for r in reg.rules_for(domain="concrete"))

def test_concrete_domain_covers_members_rebar_embeds():
    assert concrete_quantities("beam",length=5,width=.3,depth=.5).unit == "m3"
    assert concrete_quantities("reinforcement",length=20,unit_weight=.888,count=4).quantity == 71.04
    assert concrete_quantities("embed",quantity=6).unit == "عدد"
    for k in ("column","slab","wall","roof","frame","stairs"): concrete_quantities(k, length=2,width=2,depth=.2,concrete_volume=.8)

def test_steel_domain_covers_member_connection_shop_items():
    assert steel_quantities("beam",length=10,unit_weight=30).quantity == 300
    assert steel_quantities("plate",length=2,width=1,thickness=.01).quantity == 157.0
    assert steel_quantities("bolt",quantity=8).unit == "عدد"
    assert steel_quantities("weld",length=5).unit == "kg"
    for k in ("column","bracing","truss","plate_girder","section","assembly","shop_part"): steel_quantities(k,length=2,unit_weight=20)

def test_masonry_and_foundation_domains_cover_all_layer1_families():
    assert masonry_quantities("wall",length=5,height=3,thickness=.2).quantity == 3.0
    for k in ("bearing","confined"): masonry_quantities(k,length=2,height=3,thickness=.2)
    for k in ("isolated","strip","combined","strap","mat","pile_cap","grade_beam","foundation_wall"): foundation_quantities(k,length=2,width=2,depth=.5)
    assert foundation_quantities("pile",length=10,diameter=.5,count=2).unit == "m3"
    assert foundation_quantities("pile_group",pile_count=4,pile_volume=2).quantity == 8
    assert foundation_quantities("foundation_connection",quantity=3).unit == "عدد"
