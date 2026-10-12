"""Integrity regressions; these are not real-project or Windows acceptance."""
from dataclasses import replace
import pytest

from core.ai.takeoff_assistant import LocalTakeoffAssistant
from core.takeoff.workflow import TakeoffWorkflow
from core.estimate.pricebook_row_extraction_v1 import NormalizedPriceRow, _row
from core.estimate.user_pricebook_import_gate_v1 import import_gate
from core.projects.management import ProjectManagement, ScheduleTask
from core.platform.backup import create_backup, validate_backup
from core.recovery.recovery import backup_database, verify_database, RecoveryError
from core.validation.golden import GoldenCase, validate_case
from core.platform.final_product_acceptance_v1 import evaluate_final_product_acceptance, REQUIRED_CHECKS


@pytest.mark.parametrize("quantity", [True, float("nan"), float("inf")])
def test_ai_qa_rejects_invalid_engineering_quantities(quantity):
    issues=LocalTakeoffAssistant().qa([{"quantity":quantity,"unit":"m","price_code":"P"}])
    assert any(issue["code"]=="invalid_quantity" for issue in issues)


def test_ai_price_suggestion_does_not_become_approved_code():
    workflow=TakeoffWorkflow()
    original={"layer":"بتن","quantity":2,"unit":"m3"}
    mapped=workflow.map_price_codes([original],[{"code":"P","description":"بتن"}])
    assert mapped[0]["price_suggestions"]
    assert not mapped[0].get("price_code")
    assert mapped[0]["needs_price_confirmation"]
    assert "price_code" not in original
    with pytest.raises(ValueError,match="تأیید"):
        workflow.build_estimate(mapped)


def test_takeoff_confirmation_requires_explicit_valid_selection():
    workflow=TakeoffWorkflow()
    inspection={"candidates":[{"quantity":1}]}
    with pytest.raises(ValueError): workflow.confirm(inspection)
    with pytest.raises(ValueError): workflow.confirm(inspection,[2])
    assert workflow.confirm(inspection,[1])[0]["confirmed"]


@pytest.mark.parametrize("price", [None, True, -1, float("nan"), float("inf")])
def test_estimate_does_not_guess_missing_or_invalid_price(price):
    with pytest.raises(ValueError):
        TakeoffWorkflow().build_estimate([{"quantity":2,"unit_price":price}])


def test_explicit_zero_catalog_price_is_preserved():
    result=TakeoffWorkflow().build_estimate([{"quantity":2,"price_code":"P","unit_price":99}],{"P":0})
    assert result[0]["total"]==0
    assert _row({"code":"P","unit_price":0},1405,"ابنیه","a"*64,"prices.csv").unit_price==0


@pytest.mark.parametrize("quantity", [True, float("nan"), float("inf"), -1])
def test_estimate_rejects_invalid_quantity(quantity):
    with pytest.raises(ValueError):
        TakeoffWorkflow().build_estimate([{"quantity":quantity,"unit_price":1}])


def test_empty_pricebook_is_rejected_without_exception():
    assert not import_gate([],1405,"ابنیه")["green"]


def test_pricebook_rejects_duplicate_identity_and_fake_hash():
    row=NormalizedPriceRow(1405,"ابنیه","P","بتن","m3",100,"a"*64,"user.csv")
    assert not import_gate([row,row],1405,"ابنیه")["green"]
    assert not import_gate([replace(row,source_sha256="abc")],1405,"ابنیه")["green"]


@pytest.mark.parametrize("price", [True,-1,float("nan"),float("inf")])
def test_pricebook_rejects_invalid_price(price):
    row=NormalizedPriceRow(1405,"ابنیه","P","بتن","m3",price,"a"*64,"user.csv")
    assert not import_gate([row],1405,"ابنیه")["green"]


def test_project_schedule_rejects_dependency_cycle():
    with pytest.raises(ValueError,match="دوری"):
        ProjectManagement(tasks=[
            ScheduleTask("A","A","2026-01-01","2026-01-02",predecessor_ids=("B",)),
            ScheduleTask("B","B","2026-01-01","2026-01-02",predecessor_ids=("A",)),
        ])


@pytest.mark.parametrize("bad", [float("inf"),"inf",True])
def test_golden_reference_cannot_pass_invalid_numeric_equivalence(bad):
    case=GoldenCase("G","1",{},expected_quantities=({"id":"A","quantity":1},))
    result=validate_case(case,[{"id":"A","quantity":bad}],[])
    assert not result.passed


def test_golden_matching_infinity_is_still_invalid():
    case=GoldenCase("G","1",{},expected_quantities=({"id":"A","quantity":"inf"},))
    assert not validate_case(case,[{"id":"A","quantity":"inf"}],[]).passed


def test_database_check_never_creates_missing_source(tmp_path):
    missing=tmp_path/"missing.db"
    with pytest.raises(RecoveryError): verify_database(missing)
    with pytest.raises(RecoveryError): backup_database(missing,tmp_path/"backup.db")
    assert not missing.exists()
    assert not (tmp_path/"backup.db").exists()


def test_database_backup_cannot_target_source(tmp_path):
    import sqlite3
    path=tmp_path/"source.db"
    with sqlite3.connect(path) as connection:
        connection.execute("create table evidence (id integer)")
    before=path.read_bytes()
    with pytest.raises(RecoveryError): backup_database(path,path)
    assert path.read_bytes()==before


def test_backup_rejects_boolean_revision_and_nonfinite_payload():
    with pytest.raises(ValueError): create_backup("P",True,{})
    with pytest.raises(ValueError): create_backup("P",1,{"quantity":float("nan")})
    assert validate_backup([])


def test_final_acceptance_rejects_mixed_key_types_without_crashing():
    result=evaluate_final_product_acceptance({**dict.fromkeys(REQUIRED_CHECKS,True),1:True})
    assert not result.accepted
    assert result.blockers
