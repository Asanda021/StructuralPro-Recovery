from core.commercial.contract import Contract,ContractItem
from core.account import make_account,device_identity,LocalAccountStore
from core.sync.local_snapshot import export_snapshot,import_snapshot

def test_commercial_rates_and_validation():
    c=Contract("C","T",[ContractItem("1","x","m3",2,10)],overhead_rate=.1,regional_rate=.05,tax_rate=.09,insurance_rate=.03)
    assert c.validate()==[] and c.commercial_total()==23

def test_account_store_and_snapshot(tmp_path):
    a=make_account("M",account_id="a1"); d=device_identity("desktop",seed="x")
    s=LocalAccountStore(tmp_path/"account.json"); s.save(a,d); aa,dd=s.load(); assert aa==a and dd==d
    p=tmp_path/"snapshot.json"; export_snapshot([{"id":"p1"}],p); assert import_snapshot(p)["projects"][0]["id"]=="p1"

def test_priority5_unified_finance_ledger_reconciles_and_controls_due_dates():
    from core.commercial.finance import FinanceLedger, FinanceParty, FinanceDocument, FinanceEntry
    ledger = FinanceLedger(parties=[FinanceParty("P1", "پیمانکار", "contractor")])
    ledger.add_document(FinanceDocument("D1", "INV-1", "فاکتور", 1000, "P1", "1405/07/01", "partial"))
    ledger.add_obligation(FinanceEntry("O1", 1000, "1405/06/01", "O", "P1", "D1"))
    ledger.add_cost(FinanceEntry("C1", 800, "1405/06/01", "C", "P1", "D1"))
    ledger.add_payment(FinanceEntry("PAY1", 400, "1405/06/15", "P", "P1", "D1"))
    ledger.add_receipt(FinanceEntry("R1", 250, "1405/06/20", "R", "P1"))
    reconciliation = ledger.reconciliation()
    assert reconciliation["rows"][0]["derived_status"] == "partial"
    assert reconciliation["rows"][0]["outstanding"] == 600
    due = ledger.due_control("1405/07/02")
    assert due["overdue_count"] == 1 and due["overdue_amount"] == 600
    dashboard = ledger.dashboard("1405/07/02")
    assert dashboard["payments"] == 400 and dashboard["receipts"] == 250
    assert dashboard["net_cash"] == -150

def test_priority5_finance_rejects_broken_links_and_duplicate_ids():
    from core.commercial.finance import FinanceLedger, FinanceParty, FinanceDocument, FinanceEntry
    import pytest
    ledger = FinanceLedger(parties=[FinanceParty("P1", "A")])
    with pytest.raises(ValueError):
        ledger.add_document(FinanceDocument("D1", "X", "فاکتور", 10, "UNKNOWN"))
    ledger.add_document(FinanceDocument("D1", "X", "فاکتور", 10, "P1"))
    ledger.add_payment(FinanceEntry("PAY1", 1, document_id="D1"))
    with pytest.raises(ValueError):
        ledger.add_payment(FinanceEntry("PAY1", 1, document_id="D1"))
