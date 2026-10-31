"""P8P2: 70-trade production library, precedence network and statement basis."""
import pytest
from types import SimpleNamespace
from pathlib import Path
from core.projects.production_catalog import (
    CATALOG,catalog_metadata,productivity_days,matching_profile,
    normalized_production_unit,
)
from core.projects.precedence_model import calculate_precedence
from core.drawings.workflow_planning import (
    new_workflow_plan,sync_measured_items,edit_activity,
)
from core.commercial.statement_basis import (
    choose_statement_mode,statement_mode,review_contract_rates,
    validate_statement_pricing,
)


def test_catalog_covers_all_major_building_disciplines_without_faking_official_sources():
    assert len(CATALOG)>=70
    assert set(catalog_metadata()["disciplines"])=={
        "structure","architecture","mechanical","electrical","elevator",
        "fire","site","wood","renovation","restoration"
    }
    assert all(p.rate_source and p.unit and p.keywords for p in CATALOG.values())
    assert any("infralens" in p.rate_source for p in CATALOG.values())
    assert any("ASSUMPTION" in p.rate_source for p in CATALOG.values())
    assert len({p.code for p in CATALOG.values()})==len(CATALOG)


def test_masonry_measured_duration_in_square_metres_and_crew_reallocation():
    r=productivity_days("block_wall",96,"متر مربع",crews=2)
    assert r["min_workdays"]<=r["expected_workdays"]<=r["max_workdays"]
    assert r["expected_workdays"]==4
    doubled=productivity_days("block_wall",96,"m2",crews=1)
    assert doubled["expected_workdays"]==8
    assert r["status"]=="PRELIMINARY_UNAPPROVED"
    with pytest.raises(ValueError,match="واحد"):
        productivity_days("block_wall",96,"kg")
    for invalid in (-1,"nan","inf"):
        with pytest.raises(ValueError):
            productivity_days("block_wall",invalid,"m2")
    with pytest.raises(ValueError):
        productivity_days("block_wall",96,"m2",crews=0)


def test_70_profiles_are_initially_unquantified_and_do_not_claim_actual_progress():
    plan=new_workflow_plan(drawing_source="p.dwg",source_sha256="xyz",
        structure="concrete",disciplines=["architecture","mechanical",
        "electrical","fire","elevator","site","renovation","restoration","wood"])
    tasks={x["id"]:x for x in plan["tasks"]}
    assert "block_wall" in tasks and "hvac_pipe" in tasks
    assert "conduit" in tasks and "elevator_cabin" in tasks
    assert "timber_finish" in tasks and "seismic_retrofit" in tasks
    assert tasks["block_wall"]["duration_days"]==0
    assert tasks["block_wall"]["duration_status"]=="AWAITING_REVIEWED_QUANTITY"
    assert not tasks["block_wall"]["baseline_approved"]
    assert "block_wall" in tasks["handover"]["predecessors"]
    assert plan["calendar"]["start_date"] is None


def test_source_linked_wall_tile_quantity_drives_schedule_days_and_keeps_manual_override():
    p=new_workflow_plan(drawing_source="a.dwg",source_sha256="abc",
        structure="concrete",disciplines=["architecture"])
    item=SimpleNamespace(id="IT-1",label="کاشی دیوار سرویس",takeoff_code="",
        cad_evidence=None,quantity=80,unit="مترمربع",source_ref="source#1")
    sync_measured_items(p,[item])
    task=next(x for x in p["tasks"] if x["id"]=="wall_tile")
    assert task["linked_item_ids"]==["IT-1"]
    assert task["duration_days"]==5
    assert task["duration_status"]=="ESTIMATED_REQUIRES_SITE_REVIEW"
    assert not task["quantity_reviewed"]
    modified=edit_activity(p,"wall_tile",crew_count=1,efficiency="0.8")
    sync_measured_items(modified,[item])
    next_task=next(x for x in modified["tasks"] if x["id"]=="wall_tile")
    assert next_task["duration_days"]>5
    fixed=edit_activity(modified,"wall_tile",duration_days=14)
    sync_measured_items(fixed,[item])
    assert next(x for x in fixed["tasks"] if x["id"]=="wall_tile")["duration_days"]==14


def test_precedence_pdm_four_relation_types_parallel_lag_and_cycles():
    def net(kind,lag):
        return {"tasks":[
            {"id":"A","predecessors":[],"duration_days":5},
            {"id":"B","predecessors":["A"],
             "links":[{"predecessor":"A","type":kind,"lag_days":lag}],
             "duration_days":3},
        ]}
    assert calculate_precedence(net("FS",0))["tasks"][1]["start_workday_offset"]==5
    assert calculate_precedence(net("SS",2))["tasks"][1]["start_workday_offset"]==2
    assert calculate_precedence(net("FF",0))["tasks"][1]["start_workday_offset"]==2
    assert calculate_precedence(net("SF",6))["tasks"][1]["start_workday_offset"]==3
    with pytest.raises(ValueError,match="چرخه"):
        calculate_precedence({"tasks":[
            {"id":"A","predecessors":["B"],"duration_days":1},
            {"id":"B","predecessors":["A"],"duration_days":1},
        ]})
    with pytest.raises(ValueError):
        calculate_precedence(net("TR",0))
    with pytest.raises(ValueError):
        calculate_precedence(net("FS",9999))


def test_mep_parallel_work_same_start_without_false_fs_ordering():
    p=new_workflow_plan(drawing_source="p.dwg",source_sha256="sha",
        structure="steel",disciplines=["architecture","mechanical","electrical"])
    tasks={x["id"]:x for x in p["tasks"]}
    assert tasks["rough_mechanical"]["start_workday_offset"]==tasks["rough_electrical"]["start_workday_offset"]
    assert set(tasks["plaster"]["predecessors"])=={"rough_mechanical","rough_electrical"}


def test_statement_mode_selection_legacy_history_is_immutable():
    p={"boq":[],"statement_periods":[{"number":1}]}
    assert statement_mode(p)=="pricebook"
    with pytest.raises(ValueError):
        choose_statement_mode(p,"contract_rates")
    p2={"boq":[]}
    choose_statement_mode(p2,"contract_rates")
    assert statement_mode(p2)=="contract_rates"
    choose_statement_mode(p2,"pricebook")
    assert "statement_contract_rate_review" not in p2
    with pytest.raises(ValueError):
        choose_statement_mode(p2,"not_a_mode")


def test_no_pricebook_requires_source_document_and_reviewed_exact_rates(tmp_path,monkeypatch):
    import core.reports.aec_office_package as office
    monkeypatch.setattr(office,"audit_boq",lambda project,require_pricebook=False:{
        "pricing_complete":True,"unpriced_item_numbers":[]
    } if not require_pricebook else (_ for _ in ()).throw(ValueError("NO PRICEBOOK")))
    p={"boq":[{"price_code":"C1","item_code":"I1","unit":"m2","unit_price":"2500"}]}
    choose_statement_mode(p,"contract_rates")
    with pytest.raises(ValueError,match="بازبینی"):
        validate_statement_pricing(p)
    source=tmp_path/"private-contract.txt"
    source.write_text("Agreement C1 2500 Rial /m2",encoding="utf-8")
    review_contract_rates(p,source,"مهندس مسئول")
    out=validate_statement_pricing(p)
    assert out["mode"]=="contract_rates" and len(out["agreement_sha256"])==64
    p["boq"][0]["unit_price"]="9999"
    with pytest.raises(ValueError,match="مغایر"):
        validate_statement_pricing(p)
    p["boq"][0]["unit_price"]="2500"
    source.write_text("TAMPER",encoding="utf-8")
    with pytest.raises(ValueError,match="تغییر"):
        validate_statement_pricing(p)


def test_contract_rates_do_not_approve_zero_document_or_missing_price(tmp_path,monkeypatch):
    import core.reports.aec_office_package as office
    monkeypatch.setattr(office,"audit_boq",lambda project,require_pricebook=False:{
        "pricing_complete":False,"unpriced_item_numbers":[1]
    })
    p={"boq":[{"price_code":"B","item_code":"X","unit":"عدد","unit_price":None}]}
    choose_statement_mode(p,"contract_rates")
    proof=tmp_path/"signed.txt";proof.write_text("contract",encoding="utf-8")
    with pytest.raises(ValueError):
        review_contract_rates(p,proof,"Reviewer")



def test_renovation_or_fitout_never_invents_foundation_or_new_frame():
    p=new_workflow_plan(drawing_source="existing.dwg",source_sha256="old",
        structure="unknown",disciplines=["architecture","mechanical"],
        project_kind="renovation")
    by_id={t["id"]:t for t in p["tasks"]}
    assert "demolition" in by_id and "seismic_retrofit" in by_id
    assert not any(x in by_id for x in (
        "earthwork","foundation","concrete_frame","steel_frame","slabs"
    ))
    assert by_id["masonry"]["predecessors"]==["mobilize"]
    assert p["project_kind"]=="renovation"
    fit=new_workflow_plan(drawing_source="existing.dwg",source_sha256="old",
        structure="unknown",disciplines=["architecture"],project_kind="fitout")
    assert "demolition" not in {t["id"] for t in fit["tasks"]}
    with pytest.raises(ValueError,match="نوع پروژه"):
        new_workflow_plan(drawing_source="",source_sha256="",structure="unknown",
                          disciplines=[],project_kind="magic")


def test_single_trade_detail_does_not_double_count_coarse_summary_and_handover():
    plan=new_workflow_plan(drawing_source="p.dwg",source_sha256="sha",
        structure="concrete",disciplines=["architecture"])
    item=SimpleNamespace(id="W1",label="دیوار بلوکی",
                         takeoff_code="",cad_evidence=None,quantity=96,
                         unit="m2",source_ref="p.dwg#W1")
    sync_measured_items(plan,[item])
    tasks={x["id"]:x for x in plan["tasks"]}
    assert tasks["block_wall"]["duration_days"]==4
    assert tasks["masonry"]["duration_days"]==0
    assert tasks["masonry"]["duration_status"]=="SUMMARY_FROM_DETAILED_WBS"
    assert "block_wall" in tasks["masonry"]["predecessors"]
    assert tasks["handover"]["start_workday_offset"]>=tasks["block_wall"]["end_workday_offset"]


def test_manually_edited_predecessors_are_never_replaced_by_summary_expansion():
    p=new_workflow_plan(drawing_source="p.dwg",source_sha256="x",
        structure="concrete",disciplines=["architecture"])
    p=edit_activity(p,"masonry",predecessors=["slabs"])
    assert next(t for t in p["tasks"] if t["id"]=="masonry")["predecessors_edited"]
    item=SimpleNamespace(id="W",label="دیوار بلوکی",
                         takeoff_code="",cad_evidence=None,quantity=48,
                         unit="m2",source_ref="x")
    sync_measured_items(p,[item])
    wall=next(t for t in p["tasks"] if t["id"]=="masonry")
    assert wall["duration_days"]==10
    assert wall["predecessors"]==["slabs"]
