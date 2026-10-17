"""Tests of conservative cross-member physical rebar ownership, without DB writes."""
from __future__ import annotations
from copy import deepcopy
from decimal import Decimal
import pytest

from core.takeoff.shared_rebar_ownership_chat import (
    RebarOwnershipError, reconcile, POLICY,
)

SHA = "a"*64
SHA2 = "b"*64


def claim(bar="BAR-A",piece="PIECE-A",member="WALL-01",source="SW-01",family="shear_wall",
          role="payer", payer="SW-01", peers=None, conn="CON-A", length="1.125", count="3"):
    return {"physical_bar_id":bar,"physical_piece_id":piece,"member_kind":family,
            "member_id":member,"floor_id":"F1","source_id":source,"connection_id":conn,
            "role":role,"payer_source_id":payer,
            "participant_source_ids":sorted(peers if peers is not None else [source]),
            "detail_ref":"DWG:A1/detail-02","detail_sha256":SHA,
            "approved_by":"Engineer A","group":"starter","diameter_mm":"16",
            "count":count,"unit_mass_kg_m":"1.58","unit_mass_ref":"manufacturer-ref-A",
            "cut_parts":[{"piece_part_id":"S", "kind":"straight", "length_m":length, "source_ref":"DWG-cut"},
                         {"piece_part_id":"H", "kind":"hook", "length_m":"0.075", "source_ref":"DWG-hook"}]}


def connection(id="CON-A", bars=None, typ="starter"):
    return {"connection_id":id,"type":typ,"bar_ids":bars if bars is not None else ["BAR-A"],
            "detail_ref":"DWG:A1/connection-4","detail_sha256":SHA2,"approved_by":"Engineer A"}


def sample(shared=True):
    peers=["PILE-01","SW-01"] if shared else ["SW-01"]
    claims=[claim(peers=peers)]
    if shared:
        claims.append(claim(member="PILE-01",source="PILE-01",family="bored_pile",role="reference",peers=peers))
    return {"project_id":"P","snapshot_ref":"structural-sheet-A/version-2",
            "source_sha256":SHA,"independent_reviewer":"Engineer B",
            "review_ref":"independent-reviewed-memo-1","claims":claims,
            "connections":[connection()]}


def test_single_owner_is_preview_only():
    out=reconcile(sample(False))
    assert out["policy"]==POLICY and not out["commit_allowed"]
    assert out["physical_bar_count"]==1
    assert Decimal(out["preview_total_kg"])==Decimal("5.688000")
    assert out["reference_only_claims"]==[]


def test_shared_two_member_pays_once():
    out=reconcile(sample())
    assert out["physical_bar_count"]==1
    assert len(out["reference_only_claims"])==1
    assert out["reference_only_claims"][0]["referencing_source_id"]=="PILE-01"
    assert Decimal(out["preview_total_kg"])==Decimal("5.688")
    assert out["physical_bar_paid_once"][0]["paying_source_id"]=="SW-01"


def test_immutable_input_and_deterministic_fingerprint():
    d=sample();copy=deepcopy(d)
    a,b=reconcile(d),reconcile(d)
    assert d==copy and a==b


def test_distinct_bars_on_documented_lap_are_both_paid():
    d=sample(False)
    d["claims"][0]["connection_id"]="L1"
    d["claims"].append(claim(bar="BAR-B",piece="PIECE-B",member="BEAM-02",source="BEAM-02",family="beam",payer="BEAM-02",peers=["BEAM-02"],conn="L1",length="2"))
    d["connections"]=[connection("L1",["BAR-A","BAR-B"],"lap")]
    for c in d["claims"]:
        c["cut_parts"].append({"piece_part_id":"L", "kind":"lap", "length_m":"0.20", "source_ref":"SYNTHETIC-DWG-LAP"})
    out=reconcile(d)
    assert out["physical_bar_count"]==2
    assert Decimal(out["preview_total_kg"])==(Decimal("1.4")+Decimal("2.275"))*Decimal("1.58")*3


def test_many_distinct_sources():
    d=sample(False)
    kinds=["column", "stair", "bored_pile", "pile_cap", "foundation", "tie_beam", "slab", "beam"]
    for i,k in enumerate(kinds):
        bar=f"B-{i}"; src=f"SRC-{i}";conn=f"CON-{i}"
        d["claims"].append(claim(bar=bar,piece=f"PIECE-{i}",member=src,source=src,family=k,payer=src,conn=conn))
        d["connections"].append(connection(conn,[bar]))
    assert reconcile(d)["physical_bar_count"]==len(kinds)+1


@pytest.mark.parametrize("field,value",[
    ("source_id",""),("source_id"," S"),("physical_bar_id","BAR-A "),
    ("physical_piece_id",None),("member_kind","tank"),("member_id",""),
    ("floor_id",""),("connection_id",""),("role","paid"),("payer_source_id",""),
    ("detail_ref",""),("detail_sha256","not-sha"),("approved_by",""),
    ("group",""),("diameter_mm",0),("diameter_mm","NaN"),("diameter_mm",float("inf")),
    ("diameter_mm",True),("count","1.5"),("count",0),("count",False),
    ("unit_mass_kg_m","Infinity"),("unit_mass_kg_m",-2),("unit_mass_kg_m",0.0),
    ("unit_mass_ref",""),("participant_source_ids",[]),
    ("participant_source_ids",["SW-01","SW-01"]),
    ("participant_source_ids",["OTHER"]),("participant_source_ids",["SW-01","OTHER"]),
    ("cut_parts",[]),
])
def test_reject_bad_claim(field,value):
    d=sample(False);d["claims"][0][field]=value
    with pytest.raises(RebarOwnershipError):reconcile(d)


@pytest.mark.parametrize("change",[
    lambda d: d["claims"].append(deepcopy(d["claims"][0])),
    lambda d: d["claims"].pop(),
    lambda d: d["claims"][1].update(role="payer"),
    lambda d: d["claims"][0].update(role="reference"),
    lambda d: d["claims"][1].update(unit_mass_kg_m="1.59"),
    lambda d: d["claims"][1].update(count="4"),
    lambda d: d["claims"][1].update(diameter_mm="20"),
    lambda d: d["claims"][1].update(detail_sha256=SHA2),
    lambda d: d["claims"][1].update(connection_id="DIFFERENT"),
    lambda d: d["claims"][1].update(payer_source_id="PILE-01"),
    lambda d: d["claims"][1].update(physical_piece_id="DIFFERENT"),
    lambda d: d["claims"][0].update(participant_source_ids=["SW-01"]),
    lambda d: d["claims"][1]["cut_parts"][0].update(length_m="1.126"),
    lambda d: d["claims"][0]["cut_parts"].append(deepcopy(d["claims"][0]["cut_parts"][0])),
    lambda d: d["claims"][0]["cut_parts"][0].update(kind="imaginary"),
    lambda d: d["claims"][0]["cut_parts"][0].update(source_ref=""),
    lambda d: d["claims"][0]["cut_parts"][0].update(length_m="-0.02"),
    lambda d: d["claims"][0]["cut_parts"][0].update(length_m="NaN"),
    lambda d: d["claims"][0]["cut_parts"][0].update(length_m=0.2),
    lambda d: d["claims"][1].update(source_id="SW-01"),
])
def test_reject_conflicting_or_partial_shared_claims(change):
    d=sample();change(d)
    with pytest.raises(RebarOwnershipError):reconcile(d)


@pytest.mark.parametrize("change",[
    lambda d: d["connections"].clear(),
    lambda d: d["connections"].append(deepcopy(d["connections"][0])),
    lambda d: d["connections"][0].update(bar_ids=["MISSING"]),
    lambda d: d["connections"][0].update(type="teleport"),
    lambda d: d["connections"][0].update(type="lap"),
    lambda d: d["connections"][0].update(detail_ref=""),
    lambda d: d["connections"][0].update(detail_sha256="bad"),
    lambda d: d["connections"][0].update(approved_by="Engineer B"),
    lambda d: d.update(independent_reviewer="Engineer A"),
    lambda d: d.update(source_sha256="SHA"),
    lambda d: d.update(project_id=""),
    lambda d: d.update(claims="bad"),
    lambda d: d.update(connections="bad"),
    lambda d: d.update(extra="silent"),
])
def test_reject_bad_documentation(change):
    d=sample(False);change(d)
    with pytest.raises(RebarOwnershipError):reconcile(d)


def test_reject_same_piece_for_different_bars():
    d=sample(False)
    d["claims"].append(claim(bar="BAR-B",piece="PIECE-A",source="COLUMN-1",member="COL-1",family="column",payer="COLUMN-1",conn="C2"))
    d["connections"].append(connection("C2",["BAR-B"]))
    with pytest.raises(RebarOwnershipError):reconcile(d)


def test_missing_existing_identity_is_reported_not_cleared():
    d=sample(False)
    project={"id":"P", "takeoffs":[{"source_id":"legacy-bar","quantities":[{"code":"rebar","title":"میلگرد", "amount":"2"}]}]}
    out=reconcile(d,project)
    assert not out["commit_allowed"]
    assert any("فاقد هویت" in s for s in out["blockers"])


def test_saved_physical_identity_collision_blocker():
    d=sample(False)
    project={"id":"P","takeoffs":[{"source_id":"legacy-bar","params":{"physical_bar_id":"BAR-A"},"quantities":[{"code":"rebar","title":"میلگرد"}]}]}
    out=reconcile(d,project)
    assert any("برداشت قبلی" in s for s in out["blockers"])


def test_project_not_mutated():
    project={"id":"P", "takeoffs":[]};before=deepcopy(project)
    reconcile(sample(),project)
    assert project==before


def test_project_invalid_fail_closed():
    with pytest.raises(RebarOwnershipError):reconcile(sample(),{"id":"Q"})
    with pytest.raises(RebarOwnershipError):reconcile(sample(),{"id":"P","takeoffs":["bad"]})


def test_fractional_micro_decimal_exact():
    d=sample(False)
    d["claims"][0]["cut_parts"][0]["length_m"]="1.00000000000000000000000000001"
    d["claims"][0]["cut_parts"][1]["length_m"]="0.00000000000000000000000000001"
    d["claims"][0]["unit_mass_kg_m"]="1.2345678901234567890123456789"
    out=reconcile(d)
    with __import__('decimal').localcontext(__import__('decimal').Context(prec=256)):
        expected=(Decimal("1.00000000000000000000000000002")*Decimal("1.2345678901234567890123456789")*3)
    assert Decimal(out["preview_total_kg"])==expected
    assert Decimal(out["physical_bar_paid_once"][0]["mass_kg"])==expected


def test_disjoint_bar_connection_only_does_not_invent_lap_allowance():
    d=sample(False)
    d["claims"][0]["connection_id"]="L1"
    d["claims"].append(claim(bar="BAR-B",piece="PIECE-B",member="BEAM-2",source="BEAM-2",family="beam",payer="BEAM-2",conn="L1"))
    d["connections"]=[connection("L1",["BAR-A","BAR-B"],"lap")]
    for c in d["claims"]:
        c["cut_parts"].append({"piece_part_id":"L", "kind":"lap", "length_m":"0.20", "source_ref":"SYNTHETIC-DWG-LAP"})
    out=reconcile(d)
    assert Decimal(out["preview_total_kg"])==Decimal("1.4")*Decimal("1.58")*3*2
    assert all("lap" not in r for r in out["physical_bar_paid_once"])


def test_decimal_direct_input_is_not_coerced_to_binary_float():
    d=sample(False)
    d["claims"][0]["diameter_mm"]=Decimal("16.000")
    d["claims"][0]["unit_mass_kg_m"]=Decimal("1.58")
    d["claims"][0]["cut_parts"][0]["length_m"]=Decimal("1.125")
    a=reconcile(d)
    assert Decimal(a["preview_total_kg"])==Decimal("5.688")
    assert len(a["source_fingerprint_sha256"])==64


def test_project_legacy_rebar_prevents_global_clearance_even_if_new_claims_unique():
    d=sample(False)
    project={"id":"P", "takeoffs":[{"source_id":"beam-old","params":{"bridge_policy":"legacy"},
              "quantities":[{"code":"beam_rebar","title":"آرماتور بالایی","amount":"11.5"}]}]}
    out=reconcile(d,project)
    assert any("فاقد هویت" in msg for msg in out["blockers"])
    assert out["status"]=="preview_only_not_integrated"


def test_claim_with_forbidden_float_rejects_without_false_success():
    d=sample(False)
    d["claims"][0]["count"]=float("1.0")
    with pytest.raises(RebarOwnershipError):reconcile(d)


def test_real_source_digest_checked_with_bytes():
    import hashlib
    doc=b"strictly synthetic source bytes"
    d=sample(False)
    d["source_sha256"]=hashlib.sha256(doc).hexdigest()
    result=reconcile(d,source_document=doc)
    assert not any("مدرک اصلی" in msg for msg in result["blockers"])
    assert result["commit_allowed"] is False


def test_mismatching_source_bytes_rejected():
    d=sample(False)
    with pytest.raises(RebarOwnershipError):reconcile(d,source_document=b"wrong document")


def test_evidence_param_must_be_bytes():
    d=sample(False)
    with pytest.raises(RebarOwnershipError):reconcile(d,source_document="not bytes")


def test_lap_without_documented_length_rejected():
    d=sample(False)
    d["claims"][0]["connection_id"]="L1"
    d["claims"].append(claim(bar="BAR-B",piece="PIECE-B",member="BEAM-2",source="BEAM-2",family="beam",payer="BEAM-2",conn="L1"))
    d["connections"]=[connection("L1",["BAR-A","BAR-B"],"lap")]
    with pytest.raises(RebarOwnershipError):reconcile(d)


def test_anchorage_connection_without_documented_anchorage_rejected():
    d=sample(False)
    d["connections"][0]["type"]="anchorage"
    with pytest.raises(RebarOwnershipError):reconcile(d)


def test_anchorage_length_documented_passes():
    d=sample(False)
    d["connections"][0]["type"]="anchorage"
    d["claims"][0]["cut_parts"].append({"piece_part_id":"A", "kind":"anchorage", "length_m":".125", "source_ref":"SYNTHETIC-ANCHORAGE"})
    out=reconcile(d)
    assert Decimal(out["preview_total_kg"])==Decimal("1.325")*Decimal("1.58")*3
