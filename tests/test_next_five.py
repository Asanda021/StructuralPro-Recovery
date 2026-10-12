from core.commercial.contract import Contract,ContractItem
from core.commercial.statement import build_payment_statement
from core.commercial.ledger import LedgerEntry,ProjectLedger
from core.projects.store import ProjectStore
from core.projects.library import ProjectLibrary
from core.account import make_account,device_identity
from core.sync.session import SyncSession
from core.sync.conflicts import merge_dict,resolve_conflicts
from core.projects.statement_engine import StatementLine

def test_contract_statement_and_ledger(tmp_path):
    c=Contract("C1","Demo",[ContractItem("A","Concrete","m3",100,10)],advance_paid=100,retention_rate=.1)
    s=build_payment_statement(c,[StatementLine("A","Concrete","m3",100,10,5)])
    assert s["gross_current"]==50 and s["retention"]==5 and s["payable"]==45
    ledger=ProjectLedger([LedgerEntry("2026-10-01","payment","p",45)])
    ledger.add(LedgerEntry("2026-10-02","payment","q",5))
    assert ledger.summary()["total"]==50

def test_project_library_clone_search_and_revision(tmp_path):
    store=ProjectStore(tmp_path/"p.db"); store.save("p1",{"id":"p1","name":"Alpha","takeoffs":[{"member_code":"wall","quantities":[{"amount":1}]}]})
    lib=ProjectLibrary(store)
    assert lib.search("alp")[0]["id"]=="p1"
    clone=lib.clone("p1","p2"); assert clone["id"]=="p2"
    assert len(lib.revisions("p1"))==1

def test_account_device_and_optional_sync_session():
    a=make_account("Mohammad",account_id="acct1"); d=device_identity("android",seed="stable")
    assert a.account_id=="acct1" and d.platform=="android"
    assert not SyncSession(a.account_id,d.device_id).authenticated
    assert SyncSession(a.account_id,d.device_id,"token").authenticated

def test_conflict_preserves_both_sides():
    merged,conf=merge_dict({"x":1},{"x":2},{"x":3})
    assert conf==["x"] and merged["x"]["_conflict"]["local"]==2
    assert resolve_conflicts(merged,{"x":"remote"})["x"]==3
