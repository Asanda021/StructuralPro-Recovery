"""Independent synthetic acceptance for a candidate planar, multi-zone slope kernel."""
from copy import deepcopy
from decimal import Decimal
from fractions import Fraction

import pytest

from core.takeoff.slope_planar_zones import POLICY, calculate_planar_slope_zones

SHA = "a" * 64  # Declared synthetic digest, NOT a verified engineering document.


def zone(name, x, y, L, W, t00, t10, t01, datum="0", openings=None):
    return dict(region_id=name, physical_key="physical-" + name,
                source_ref="SOURCE-" + name, approved_by="SYNTHETIC-REVIEWER",
                datum_ref="SYNTHETIC-DATUM-" + name,
                x_m=str(x), y_m=str(y), length_m=str(L), width_m=str(W),
                base_elevation_m=str(datum), thickness_00_m=str(t00),
                thickness_10_m=str(t10), thickness_01_m=str(t01),
                openings=deepcopy(openings or []))


def opening(name="H1", x="1", y="0.5", L="1", W="0.5"):
    return dict(id=name, physical_key="physical-"+name,
                source_ref="SOURCE-"+name, x_m=x, y_m=y,
                length_m=L, width_m=W, penetration="full_depth")


def fixture():
    return dict(policy=POLICY, surface_id="SURFACE-1",
                coordinate_frame_ref="DOCUMENTED-XY-AXES",
                source_ref="MASTER-SYNTHETIC-DRAWING", source_sha256=SHA,
                approved_by="SYNTHETIC-NOT-ENGINEERING-APPROVAL",
                material_ref="SYNTHETIC-FILL", coordinate_unit="m",
                elevation_unit="m", zones=[zone("A", 0, 0, 4, 2, ".1", ".3", ".2")])


def checked(d):
    r = calculate_planar_slope_zones(d)
    assert r["boq_ready"] is False and r["purchase_quantity"] is None
    assert r["source_sha256_verified"] is False
    assert r["payment_role"] == "unreviewed_geometry_only"
    return r


def independent_integral(z, cut=None):
    """Alternative exact rational reference from four corner evaluations."""
    def Q(v):return Fraction(str(v))
    x,y,L,W = [Q(z[k]) for k in ("x_m", "y_m", "length_m", "width_m")]
    a,b,c = [Q(z[k]) for k in ("thickness_00_m","thickness_10_m","thickness_01_m")]
    def val(vx,vy):return a+(b-a)*(vx-x)/L+(c-a)*(vy-y)/W
    xx,yy,ll,ww=(x,y,L,W) if cut is None else [Q(cut[k]) for k in ("x_m","y_m","length_m","width_m")]
    return (ll*ww/4)*(val(xx,yy)+val(xx+ll,yy)+val(xx,yy+ww)+val(xx+ll,yy+ww))


def as_fraction(output):
    return Fraction(Decimal(output))


def test_two_axis_affine_single_region_exact_gross_and_void():
    d=fixture()
    d["zones"][0]["openings"]=[opening()]
    r=checked(d)
    assert Decimal(r["gross_volume_m3"]) == Decimal("2")
    assert Decimal(r["deducted_volume_m3"]) == Decimal("0.10625")
    assert Decimal(r["net_volume_m3"]) == Decimal("1.89375")
    assert as_fraction(r["gross_volume_m3"]) == independent_integral(d["zones"][0])
    assert as_fraction(r["deducted_volume_m3"]) == independent_integral(d["zones"][0],opening())
    assert r["zones"][0]["corner_thickness_m"]["t11"] == "0.4"


def test_multiple_connected_zones_with_exact_shared_finished_elevations():
    d=fixture()
    d["zones"][0]["openings"]=[opening()]
    d["zones"].append(zone("B",4,0,3,2,".3",".5",".4"))
    r=checked(d)
    assert r["zone_count"] == 2
    assert len(r["verified_shared_edges"]) == 1
    assert Decimal(r["gross_volume_m3"]) == Decimal("4.7")
    assert Decimal(r["net_volume_m3"]) == Decimal("4.59375")
    assert Decimal(r["net_area_m2"]) == Decimal("13.5")
    assert as_fraction(r["gross_volume_m3"]) == sum(map(independent_integral,d["zones"]))


def test_different_documented_base_datum_can_share_one_finished_plane():
    d=fixture()
    # Zone A right edge z=.3 .. .4, B bottom datum=-.1, thickness=.4 .. .5.
    d["zones"].append(zone("B",4,0,2,2,".4",".5",".5",datum="-.1"))
    assert len(checked(d)["verified_shared_edges"]) == 1


def test_edge_adjacency_in_y_direction_and_negative_coordinates():
    d=fixture()
    d["zones"]=[zone("A",-4,-2,4,2,".1",".3",".2"),
                zone("B",-4,0,4,2,".2",".4",".3")]
    r=checked(d)
    assert len(r["verified_shared_edges"]) == 1
    assert Decimal(r["gross_area_m2"]) == 16


def test_corner_only_is_not_an_edge_connection():
    d=fixture();d["zones"].append(zone("B",4,2,2,2,".4",".4",".4"))
    with pytest.raises(ValueError,match="متصل"):calculate_planar_slope_zones(d)


def test_touching_but_not_entire_edge_same_elevation():
    d=fixture()
    # B shares only y in [.5,1.5]; varying y along A edge must match.
    d["zones"].append(zone("B",4,".5",2,1,".325",".425",".375"))
    assert len(checked(d)["verified_shared_edges"]) == 1


@pytest.mark.parametrize("fault", [
    "wrong_policy","extra_head","missing_head","bad_coordinate_unit","bad_elevation_unit",
    "bad_sha","missing_source","bad_zones_type","too_many_zones","duplicate_region_id",
    "duplicate_physical","duplicate_region_source","region_source_same_master",
    "unknown_zone","missing_zone_field","negative_length","zero_width","bool_coordinate",
    "float_coordinate","bad_decimal","nan","infinity","negative_corner",
    "negative_derived_corner","zero_all_corners","bad_datum","missing_datum_ref",
    "missing_approved_by","zones_overlap","zones_gap","zones_corner_only",
    "neighbor_elevation_difference","same_edge_one_end_only","missing_openings",
    "openings_not_list","opening_unknown_field","opening_missing_field","opening_fractional_depth",
    "opening_outside","opening_overlap","duplicate_opening_id","duplicate_opening_physical",
    "duplicate_opening_source","opening_source_region","all_zone_removed","opening_nan",
    "opening_float","zone_count_65","openings_129","wrong_material_ref",
])
def test_fail_closed_rejects_invalid_inputs(fault):
    d=fixture();a=d["zones"][0]
    if fault=="wrong_policy":d["policy"]="other"
    elif fault=="extra_head":d["waste_pct"]="5"
    elif fault=="missing_head":d.pop("surface_id")
    elif fault=="bad_coordinate_unit":d["coordinate_unit"]="cm"
    elif fault=="bad_elevation_unit":d["elevation_unit"]="mm"
    elif fault=="bad_sha":d["source_sha256"]="abc"
    elif fault=="missing_source":d["source_ref"]=""
    elif fault=="bad_zones_type":d["zones"]={}
    elif fault=="too_many_zones":d["zones"]=[]
    elif fault=="duplicate_region_id":d["zones"].append(zone("A",4,0,2,2,".3",".4",".4"))
    elif fault=="duplicate_physical":
        b=zone("B",4,0,2,2,".3",".4",".4");b["physical_key"]=a["physical_key"];d["zones"].append(b)
    elif fault=="duplicate_region_source":
        b=zone("B",4,0,2,2,".3",".4",".4");b["source_ref"]=a["source_ref"];d["zones"].append(b)
    elif fault=="region_source_same_master":a["source_ref"]=d["source_ref"]
    elif fault=="unknown_zone":a["estimated_loss"]=".1"
    elif fault=="missing_zone_field":a.pop("x_m")
    elif fault=="negative_length":a["length_m"]="-1"
    elif fault=="zero_width":a["width_m"]="0"
    elif fault=="bool_coordinate":a["x_m"]=True
    elif fault=="float_coordinate":a["x_m"]=0.1
    elif fault=="bad_decimal":a["x_m"]="abc"
    elif fault=="nan":a["thickness_01_m"]="NaN"
    elif fault=="infinity":a["thickness_10_m"]="Infinity"
    elif fault=="negative_corner":a["thickness_00_m"]="-.1"
    elif fault=="negative_derived_corner":a["thickness_00_m"]=".4";a["thickness_10_m"]=".1";a["thickness_01_m"]=".1"
    elif fault=="zero_all_corners":a["thickness_00_m"]=a["thickness_10_m"]=a["thickness_01_m"]="0"
    elif fault=="bad_datum":a["base_elevation_m"]="-Infinity"
    elif fault=="missing_datum_ref":a["datum_ref"]=""
    elif fault=="missing_approved_by":a["approved_by"]=""
    elif fault=="zones_overlap":d["zones"].append(zone("B",3,0,2,2,".3",".4",".4"))
    elif fault=="zones_gap":d["zones"].append(zone("B",5,0,2,2,".3",".4",".4"))
    elif fault=="zones_corner_only":d["zones"].append(zone("B",4,2,2,2,".4",".4",".4"))
    elif fault=="neighbor_elevation_difference":d["zones"].append(zone("B",4,0,2,2,".31",".5",".41"))
    elif fault=="same_edge_one_end_only":d["zones"].append(zone("B",4,0,2,2,".3",".5",".41"))
    elif fault=="missing_openings":a.pop("openings")
    elif fault=="openings_not_list":a["openings"]={}
    elif fault=="opening_unknown_field":a["openings"]=[dict(opening(),faulty=True)]
    elif fault=="opening_missing_field":b=opening();b.pop("penetration");a["openings"]=[b]
    elif fault=="opening_fractional_depth":a["openings"]=[dict(opening(),penetration="partial_depth")]
    elif fault=="opening_outside":a["openings"]=[opening(x="3.5",L="1")]
    elif fault=="opening_overlap":a["openings"]=[opening(),opening("H2",x="1.2")]
    elif fault=="duplicate_opening_id":a["openings"]=[opening(),opening(x="2")]
    elif fault=="duplicate_opening_physical":b=opening("H2",x="2");b["physical_key"]="physical-H1";a["openings"]=[opening(),b]
    elif fault=="duplicate_opening_source":b=opening("H2",x="2");b["source_ref"]="SOURCE-H1";a["openings"]=[opening(),b]
    elif fault=="opening_source_region":b=opening();b["source_ref"]=a["source_ref"];a["openings"]=[b]
    elif fault=="all_zone_removed":a["openings"]=[opening(x="0",y="0",L="4",W="2")]
    elif fault=="opening_nan":a["openings"]=[opening(x="NaN")]
    elif fault=="opening_float":b=opening();b["x_m"]=.5;a["openings"]=[b]
    elif fault=="zone_count_65":d["zones"]=[zone(str(i),i*4,0,4,2,".1",".1",".1") for i in range(65)]
    elif fault=="openings_129":a["openings"]=[opening(str(i),x="0",y="0",L=".001",W=".001") for i in range(129)]
    elif fault=="wrong_material_ref":d["material_ref"]=""
    with pytest.raises(ValueError):calculate_planar_slope_zones(d)


@pytest.mark.parametrize("index",range(25))
def test_independent_rational_corner_integration_varied_profiles(index):
    # Explicit exact rational reference, not an invocation of engine formula.
    d=fixture();a=d["zones"][0]
    a["thickness_00_m"]=str(Decimal("0.02")*index)
    a["thickness_10_m"]=str(Decimal("0.04")*(index+1))
    a["thickness_01_m"]=str(Decimal("0.04")*(index+1))
    a["openings"]=[opening(x=".5",y=".25",L=".5",W=".5")]
    r=checked(d)
    assert as_fraction(r["gross_volume_m3"]) == independent_integral(a)
    assert as_fraction(r["deducted_volume_m3"]) == independent_integral(a,a["openings"][0])
    assert (as_fraction(r["net_volume_m3"]) == independent_integral(a)
            - independent_integral(a,a["openings"][0]))


def test_vertical_edge_micro_gap_rejected_without_tolerance():
    d=fixture()
    d["zones"].append(zone("B","4.0000000000000000000000000001",0,2,2,".3",".5",".4"))
    with pytest.raises(ValueError,match="متصل"):
        calculate_planar_slope_zones(d)


def test_tiny_thickness_difference_rejected_without_rounding():
    d=fixture()
    d["zones"].append(zone("B",4,0,2,2,".30000000000000000000000001",".5",".4"))
    with pytest.raises(ValueError,match="ناپیوسته"):
        calculate_planar_slope_zones(d)


def test_input_and_output_have_no_binary_float_and_input_unchanged():
    d=fixture();before=deepcopy(d)
    r=checked(d)
    assert d==before
    def walk(x):
        if isinstance(x,dict):
            for k,v in x.items():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
        else: assert not isinstance(x,float)
    walk(r)


def test_identical_physical_opening_across_regions_is_not_paid_twice():
    d=fixture()
    d["zones"].append(zone("B",4,0,2,2,".3",".5",".4",openings=[opening("H1",x="4.1",y=".5",L=".3",W=".2")]))
    d["zones"][0]["openings"]=[opening("H1",x="1",y=".5",L=".3",W=".2")]
    with pytest.raises(ValueError):calculate_planar_slope_zones(d)


def test_repeating_decimal_is_safely_blocked_not_rounded():
    d=fixture()
    d["zones"][0]["length_m"]="3"
    d["zones"][0]["openings"]=[opening(x=".2",L=".3")]
    # Thickness at centroid is 1/3 dependent. No finite exact Decimal representation.
    with pytest.raises(ValueError,match="دقت"):
        calculate_planar_slope_zones(d)


def test_four_connected_zones_with_both_axis_slopes_are_order_invariant():
    d=fixture()
    d["zones"]=[
        zone("A",0,0,4,2,".1",".3",".2"),
        zone("B",4,0,3,2,".3",".5",".4"),
        zone("C",0,2,4,1,".2",".4",".3"),
        zone("D",4,2,3,1,".4",".6",".5"),
    ]
    r=checked(d)
    assert Decimal(r["gross_volume_m3"]) == Decimal("7.75")
    assert Decimal(r["gross_area_m2"]) == Decimal("21")
    assert len(r["verified_shared_edges"]) == 4
    d["zones"].reverse()
    r2=checked(d)
    assert r2["net_volume_m3"] == r["net_volume_m3"]
    assert r2["net_area_m2"] == r["net_area_m2"]


def test_sharp_corner_nonlinear_data_is_not_silently_accepted():
    d=fixture()
    d["zones"][0]["thickness_11_m"]="1"
    with pytest.raises(ValueError):calculate_planar_slope_zones(d)


def test_oversized_decimal_precision_is_rejected_by_existing_boundary():
    d=fixture();d["zones"][0]["thickness_01_m"]="0."+"1"*129
    with pytest.raises(ValueError):calculate_planar_slope_zones(d)


def test_adjacent_zones_with_seam_different_slope_but_equal_edge_are_supported():
    d=fixture();d["zones"].append(zone("B",4,0,3,2,".3",".3",".4"))
    assert checked(d)["zone_count"]==2


def test_cli_verifies_actual_source_file_and_never_posts_to_boq(tmp_path):
    import json
    from pathlib import Path
    from scripts.preview_slope_planar_zones import main
    root=Path(__file__).resolve().parents[1]
    in_file=root/'examples/slope_planar_multi_synthetic.json'
    document=root/'examples/slope_planar_multi_source_synthetic.txt'
    out=tmp_path/'preview.json'
    assert main(['--input',str(in_file),'--source-file',str(document),'--output',str(out)])==0
    r=json.loads(out.read_text(encoding='utf-8'))
    assert r['source_sha256_verified'] is True
    assert r['net_volume_m3']=='4.59375'
    assert r['boq_ready'] is False
    with pytest.raises(FileExistsError):
        main(['--input',str(in_file),'--output',str(out)])
    assert json.loads(out.read_text(encoding='utf-8')) == r


def test_cli_cannot_mark_modified_document_as_verified(tmp_path):
    from pathlib import Path
    from scripts.preview_slope_planar_zones import main
    root=Path(__file__).resolve().parents[1]
    in_file=root/'examples/slope_planar_multi_synthetic.json'
    doc=tmp_path/'changed.txt'
    doc.write_text('DIFFERENT BYTES',encoding='utf-8')
    with pytest.raises(ValueError,match='هش'):
        main(['--input',str(in_file),'--source-file',str(doc),'--output',str(tmp_path/'uncreated.json')])
    assert not (tmp_path/'uncreated.json').exists()
