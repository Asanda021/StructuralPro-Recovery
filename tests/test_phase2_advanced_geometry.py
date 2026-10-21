"""Analytic synthetic oracles, independent of product quantity calculation."""
from decimal import Decimal
from fractions import Fraction
import pytest
from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession

RECT=[(0,0),(10,0),(10,10),(0,10)]

@pytest.mark.parametrize('points,area',[
 (RECT,'100'), ([(0,0),(4,3),(1,7),(-3,4)],'25'),
 ([(0,0),(6,0),(6,2),(2,2),(2,6),(0,6)],'20'),
 ([(0,0),(6,0),(3,4)],'12'),
 ([(10**12,10**12),(10**12+2,10**12),(10**12+2,10**12+1),(10**12,10**12+1)],'2'),
 ([(0,0),(1e-10,0),(1e-10,1e-10),(0,1e-10)],'0.00000000000000000001'),
])
def test_exact_polygon_oracles(points,area):
 s=DrawingTakeoffSession();s.calibrate(1,1,1)
 r=s.add_polygon([Point(*p) for p in points],source='explicit synthetic polygon')
 assert Decimal(r.geometry_evidence['net_m2'])==Decimal(area)
 assert r.quantity>0
 assert s.undo() and not s.items
 assert s.redo() and s.items[0].geometry_evidence==r.geometry_evidence

@pytest.mark.parametrize('bad',[
 [(0,0),(4,4),(0,4),(4,0)],[(0,0),(4,0),(4,0),(0,4)],
 [(0,0),(1,1),(2,2)],[(0,0),(4,0),(float('nan'),4)],
 [(0,0),(float('inf'),0),(0,4)],[(0,0),(4,0),(2,0),(2,2)],
])
def test_polygon_rejects_bad_geometry_atomically(bad):
 s=DrawingTakeoffSession();s.calibrate(1,1,1);before=s.to_dict()
 with pytest.raises(ValueError):s.add_polygon([Point(*p) for p in bad])
 assert s.to_dict()==before


def test_holes_exact_references_and_edit_undo():
 s=DrawingTakeoffSession();s.calibrate(1,1,1)
 r=s.add_polygon([Point(*p) for p in RECT],source='owner')
 h=[(1,1),(3,1),(3,3),(1,3)]
 r=s.add_polygon_opening(r.id,h,'explicit O1')
 r=s.add_polygon_opening(r.id,[(3,1),(5,1),(5,3),(3,3)],'explicit O2')
 assert Decimal(r.geometry_evidence['net_m2'])==92
 assert len(r.geometry_evidence['opening_refs'])==2
 before=s.to_dict()
 for bad in (h,[(2,2),(4,2),(4,4),(2,4)],[(9,9),(11,9),(11,11),(9,11)],[(0,1),(1,1),(1,2),(0,2)]):
  with pytest.raises(ValueError):s.add_polygon_opening(r.id,bad,'bad')
  assert s.to_dict()==before
 assert s.undo() and s.items[0].quantity==96
 assert s.redo() and s.items[0].quantity==92

@pytest.mark.parametrize('other,expected',[
 ([(5,5),(15,5),(15,15),(5,15)],True),
 ([(10,0),(20,0),(20,10),(10,10)],False),
 ([(10,10),(20,10),(20,20),(10,20)],False),
 ([(4,1),(8,4),(5,8),(1,5)],True),
])
def test_exact_overlap_oracle(other,expected):
 from core.drawings.planar_geometry import regions_overlap
 assert regions_overlap(RECT,(),other,()) is expected
 assert regions_overlap(other,(),RECT,()) is expected


def test_area_inside_hole_is_not_overlap_and_canonical_collinear():
 from core.drawings.planar_geometry import regions_overlap,canonical_ring
 hole=[(2,2),(8,2),(8,8),(2,8)]
 assert not regions_overlap(RECT,[hole],[(3,3),(7,3),(7,7),(3,7)],[])
 assert canonical_ring(RECT)==canonical_ring(list(reversed(RECT[2:]+RECT[:2])))
 assert canonical_ring(RECT)==canonical_ring([(0,0),(5,0),(10,0),(10,10),(0,10)])


def test_polygon_with_holes_can_be_created_atomically():
 s=DrawingTakeoffSession();s.calibrate(1,1,1)
 r=s.add_polygon([Point(*p) for p in RECT],holes=[[Point(*p) for p in [(2,2),(4,2),(4,4),(2,4)]]],opening_refs=['O1'])
 assert r.quantity==96


def test_direct_edit_cannot_change_advanced_quantity_or_invalid_geometry():
 s=DrawingTakeoffSession();s.calibrate(1,1,1);r=s.add_polygon([Point(*p) for p in RECT]);before=s.to_dict()
 with pytest.raises(ValueError):s.edit(r.id,quantity=101)
 assert s.to_dict()==before
 with pytest.raises(ValueError):s.edit_polygon(r.id,[(0,0),(1,1),(0,1),(1,0)])
 assert s.to_dict()==before


def test_reference_ratio_is_exact_or_fail_closed_not_float_area():
 s=DrawingTakeoffSession();s.calibrate(1,3,1)
 r=s.add_polygon([Point(0,0),Point(3,0),Point(3,3),Point(0,3)])
 assert Decimal(r.geometry_evidence['net_m2'])==1
 assert r.geometry_evidence['meters_per_pixel']=='1/3'
 before=s.to_dict()
 with pytest.raises(ValueError):s.add_polygon([Point(0,0),Point(1,0),Point(1,1),Point(0,1)])
 assert s.to_dict()==before


def test_nonrepresentable_display_coordinate_is_rejected():
 s=DrawingTakeoffSession();s.calibrate(1,1,1)
 with pytest.raises(ValueError):s.add_polygon([Point('0.123456789012345678901',0),Point(1,0),Point(1,1)])

@pytest.mark.parametrize('dx,dy',[(-3,-2),(0,0),(2,1),(5,2),(6,0),(10,10)])
def test_concave_overlap_matches_independent_unit_cell_oracle(dx,dy):
 from core.drawings.planar_geometry import regions_overlap
 # L shape covers exactly these 20 unit cells; second region is a 2x2 square.
 cells={(x,y) for x in range(6) for y in range(6) if x<2 or y<2}
 expected=bool(cells & {(dx+x,dy+y) for x in range(2) for y in range(2)})
 assert regions_overlap([(0,0),(6,0),(6,2),(2,2),(2,6),(0,6)],[],[(dx,dy),(dx+2,dy),(dx+2,dy+2),(dx,dy+2)],[]) is expected


def test_vertex_and_hole_limits_fail_closed():
 from core.drawings.planar_geometry import ring,region
 with pytest.raises(ValueError):ring([(i,i*i) for i in range(129)])
 with pytest.raises(ValueError):region(RECT,[[(1,1),(2,1),(2,2),(1,2)]]*33)


def test_existing_rectangular_opening_tool_keeps_exact_polygon_evidence():
 from core.drawings.roof_region import add_rectangular_opening
 s=DrawingTakeoffSession();s.calibrate(1,1,1);r=s.add_polygon([Point(*p) for p in RECT])
 updated=add_rectangular_opening(s,r.id,[(1,1),(3,1),(3,3),(1,3)],'O1 explicit rectangular detail')
 assert updated.quantity==96 and updated.geometry_evidence['opening_refs']==['O1 explicit rectangular detail']


def test_export_preserves_tiny_polygon_in_mixed_exact_total():
 from core.drawings.takeoff_bridge import build_takeoff_export_payload
 s=DrawingTakeoffSession('synthetic.pdf');s.calibrate(1,1,1)
 s.add_polygon([Point(*p) for p in RECT],source='large')
 s.add_polygon([Point(0,0),Point(1e-10,0),Point(1e-10,1e-10),Point(0,1e-10)],source='tiny')
 result=build_takeoff_export_payload(s)
 assert Decimal(str(result['summary']['by_unit']['m2']))==Decimal('100.00000000000000000001')
 assert result['approval_required'] is True

@pytest.mark.parametrize('page',[True,1.5,float('nan'),float('inf')])
def test_polygon_page_is_explicit_positive_integer(page):
 s=DrawingTakeoffSession();s.calibrate(1,1,1);before=s.to_dict()
 with pytest.raises(ValueError):s.add_polygon([Point(*p) for p in RECT],page=page)
 assert s.to_dict()==before
import pytest
from core.drawings.planar_geometry import region
OUTER=[(0,0),(10,0),(10,10),(0,10)]
@pytest.mark.parametrize('holes',[
 [[(2,2),(8,2),(8,4),(2,4)],[(2,6),(8,6),(8,8),(2,8)],[(2,4),(4,4),(4,6),(2,6)],[(6,4),(8,4),(8,6),(6,6)]],
 [[(2,2),(8,2),(8,3),(3,3),(3,7),(8,7),(8,8),(2,8)],[(7,3),(8,3),(8,7),(7,7)]],
])
def test_contact_holes_cannot_create_disconnected_island(holes):
 with pytest.raises(ValueError):region(OUTER,holes)

def test_contact_chain_preserves_supported_adjacent_holes():
 _,_,g,d=region(OUTER,[[(2,2),(4,2),(4,4),(2,4)],[(4,2),(6,2),(6,4),(4,4)],[(6,2),(8,2),(8,4),(6,4)]])
 assert g-d==88
