import pytest
from core.bim.digital_twin_v1 import DigitalTwinGraph, build_twin_graph

def sample():
    return build_twin_graph(
        sources=[{"id":"ifc-1","revision":"r1"}],
        objects=[{"id":"beam-1","source_id":"ifc-1"}],
        two_d=[{"id":"sheet-beam-1","object_id":"beam-1"}],
        quantities=[{"id":"q-1","object_id":"beam-1","quantity":12.5}],
        boq=[{"id":"boq-1","quantity_id":"q-1"}],
        estimates=[{"id":"est-1","boq_id":"boq-1"}],
    )

def test_end_to_end_lineage():
    g=sample()
    source=DigitalTwinGraph._id("source","ifc-1")
    lineage=g.lineage(source)
    assert DigitalTwinGraph._id("object","ifc-1:beam-1") in lineage
    assert DigitalTwinGraph._id("quantity","q-1") in lineage
    assert DigitalTwinGraph._id("boq","boq-1") in lineage
    assert DigitalTwinGraph._id("estimate","est-1") in lineage

def test_two_d_links_to_three_d_object():
    g=sample()
    tid=DigitalTwinGraph._id("two_d","sheet-beam-1")
    oid=DigitalTwinGraph._id("object","ifc-1:beam-1")
    assert any(e.source_id==tid and e.target_id==oid and e.relation=="represents" for e in g.edges)

def test_revision_impact_is_deterministic():
    g=sample()
    q=DigitalTwinGraph._id("quantity","q-1")
    result=g.impact([q])
    assert result["changed"]==[q]
    assert result["affected"]==sorted(result["affected"])
    assert DigitalTwinGraph._id("boq","boq-1") in result["affected"]
    assert DigitalTwinGraph._id("estimate","est-1") in result["affected"]

def test_fingerprint_is_stable():
    assert sample().fingerprint()==sample().fingerprint()

@pytest.mark.parametrize("bad",[
    {"id":"q","object_id":"missing","quantity":1},
    {"id":"q","object_id":"beam-1"},
])
def test_fail_closed_quantity_inputs(bad):
    with pytest.raises(ValueError):
        build_twin_graph(
            sources=[{"id":"s"}], objects=[{"id":"beam-1","source_id":"s"}],
            quantities=[bad])

def test_unknown_impact_node_fails_closed():
    with pytest.raises(ValueError):
        sample().impact(["not-a-node"])
