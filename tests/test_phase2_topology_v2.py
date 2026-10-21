"""Analytic oracles; explicitly synthetic geometry, no engineering approval."""
from decimal import Decimal
import pytest
from core.drawings import planar_geometry as pg
OUTER=[(0,0),(10,0),(10,10),(0,10)]
CASES=[
 (OUTER,[[(0,2),(3,2),(3,4),(0,4)]],94,1),
 (OUTER,[[(0,0),(2,0),(2,2),(0,2)]],96,1),
 (OUTER,[[(2,0),(8,0),(8,2),(2,2)]],88,1),
 (OUTER,[[(2,2),(4,2),(4,4),(2,4)],[(4,2),(6,2),(6,4),(4,4)]],92,1),
 (OUTER,[[(3,5),(5,3),(7,5),(5,7)]],92,1),
 ([(0,0),(10,0),(10,4),(4,4),(4,10),(0,10)],[[(0,6),(2,6),(2,8),(0,8)]],60,1),
 (OUTER,[[(4,0),(6,0),(6,10),(4,10)]],80,2),
 (OUTER,[[(2,2),(8,2),(8,4),(2,4)],[(2,6),(8,6),(8,8),(2,8)],[(2,4),(4,4),(4,6),(2,6)],[(6,4),(8,4),(8,6),(6,6)]],68,2),
 (OUTER,[[(2,2),(4,2),(4,4),(2,4)]],96,1),
]
@pytest.mark.parametrize('outer,holes,net,components',CASES)
def test_boundary_and_multipart_exact_oracles(outer,holes,net,components):
 assert hasattr(pg,'TOPOLOGY_V2'),'missing opt-in topology contract'
 e=pg.evidence(outer,holes,1,['explicit synthetic opening '+str(i) for i in range(len(holes))],topology=pg.TOPOLOGY_V2)
 assert Decimal(e['net_m2'])==net
 assert len(e['components'])==components
 assert sum(Decimal(c['net_m2']) for c in e['components'])==net
 assert len({c['id'] for c in e['components']})==components
 other=pg.evidence(outer[1:]+outer[:1],[h[::-1] for h in holes[::-1]],1,['doc']*len(holes),topology=pg.TOPOLOGY_V2)
 assert other['components']==e['components']

@pytest.mark.parametrize('holes',[[[(9,9),(11,9),(11,11),(9,11)]],[[(2,2),(5,2),(5,5),(2,5)],[(4,4),(6,4),(6,6),(4,6)]],[[(0,0),(10,10),(0,10),(10,0)]]])
def test_invalid_v2_topology_remains_failclosed(holes):
 assert hasattr(pg,'TOPOLOGY_V2')
 with pytest.raises(ValueError):pg.evidence(OUTER,holes,1,['doc']*len(holes),topology=pg.TOPOLOGY_V2)

@pytest.mark.parametrize('scale',['1e-20','1e12'])
def test_v2_coordinate_range_has_exact_analytical_area(scale):
 assert hasattr(pg,'TOPOLOGY_V2')
 from fractions import Fraction
 s=Decimal(scale);outer=[(str(s*x),str(s*y)) for x,y in [(0,0),(1,0),(1,1),(0,1)]]
 e=pg.evidence(outer,[],1,[],topology=pg.TOPOLOGY_V2)
 assert Fraction(e['net_m2'])==Fraction(scale)**2


def test_multipart_overlap_compares_net_material_not_cut():
 cut=[[(4,0),(6,0),(6,10),(4,10)]]
 assert not pg.regions_overlap(OUTER,cut,[(4,2),(6,2),(6,8),(4,8)],[],topology_a=pg.TOPOLOGY_V2)
 assert pg.regions_overlap(OUTER,cut,[(3,2),(5,2),(5,8),(3,8)],[],topology_a=pg.TOPOLOGY_V2)


def test_point_contact_and_many_vertex_many_hole_exact_oracles():
 e=pg.evidence(OUTER,[[(0,5),(2,4),(2,6)]],1,['explicit point contact'],topology=pg.TOPOLOGY_V2)
 assert Decimal(e['net_m2'])==98 and len(e['components'])==1
 outer=[(0,0),(40,0),(40,10)]
 for j in reversed(range(20)):outer.extend([(2*j+1,10),(2*j+1,20),(2*j,20),(2*j,10)])
 holes=[[(str(Decimal(2*j)+Decimal('.2')),2),(str(Decimal(2*j)+Decimal('.8')),2),(str(Decimal(2*j)+Decimal('.8')),3),(str(Decimal(2*j)+Decimal('.2')),3)] for j in range(20)]
 e=pg.evidence(outer,holes,1,['explicit hole '+str(j) for j in range(20)],topology=pg.TOPOLOGY_V2)
 assert Decimal(e['gross_m2'])==600 and Decimal(e['deducted_m2'])==12 and Decimal(e['net_m2'])==588
