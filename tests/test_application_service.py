from core.platform.application import StructuralProApp

def test_application_service_offline_project_takeoff_report(tmp_path):
    a=StructuralProApp(tmp_path)
    p=a.create_project("پروژه تست","p1")
    assert p["metadata"]["offline"] is True
    row=a.add_takeoff("p1","building","slab",length=2,width=3,member_code="S1")
    assert row["quantities"][0]["amount"]==6
    assert a.open_project("p1")["takeoffs"]
    assert a.report("p1","csv",tmp_path/"r.csv").exists()


def test_counterparty_master_lifecycle_and_stable_ids(tmp_path):
    a = StructuralProApp(tmp_path)
    a.create_project("پروژه طرف حساب", "cp1")
    first = a.add_project_counterparty("cp1", "  پیمانکار   الف  ", role=" پیمانکار ")
    assert first["id"] == "CP0001"
    assert first["active"] is True
    assert a.find_project_counterparty_by_id("cp1", "CP0001")["name"] == "پیمانکار الف"

    updated = a.update_project_counterparty("cp1", "CP0001", name="پیمانکار الف جدید", role="مجری", notes="اصلی")
    assert updated["name"] == "پیمانکار الف جدید"
    assert updated["role"] == "مجری"
    assert updated["notes"] == "اصلی"

    a.set_project_counterparty_active("cp1", "CP0001", False)
    assert a.project_counterparties("cp1", active_only=True) == []
    second = a.add_project_counterparty("cp1", "فروشنده ب")
    assert second["id"] == "CP0002"
    assert a.project_counterparties("cp1")[0]["active"] is False
    try:
        a.add_project_counterparty("cp1", "پیمانکار الف جدید")
        assert False, "duplicate counterparty should be rejected"
    except ValueError:
        pass


def test_financial_reconciliation_audits_status_without_mutation(tmp_path):
    a = StructuralProApp(tmp_path)
    a.create_project("پروژه تطبیق", "rec1")
    cp = a.add_project_counterparty("rec1", "طرف حساب")
    commitment = a.add_project_commitment("rec1", 1000, paid_amount=400, counterparty=cp["name"])
    a.add_project_financial_document("rec1", "DOC-1", "فاکتور", 1000, counterparty=cp["name"],
                                     payment_status="unpaid", commitment_id=commitment["id"])
    a.add_project_financial_document("rec1", "DOC-2", "فاکتور", 500, counterparty=cp["name"],
                                     payment_status="paid")
    receipt = a.add_project_receipt("rec1", 500, counterparty=cp["name"])
    p = a.open_project("rec1")
    p["financial_documents"][1]["receipt_id"] = receipt["id"]
    a.store.save("rec1", p)

    result = a.project_financial_reconciliation("rec1")
    assert result["document_count"] == 2
    assert result["mismatch_count"] == 1
    assert result["unlinked_count"] == 0
    assert result["rows"][0]["derived_status"] == "partial"
    assert result["rows"][0]["status_match"] is False
    assert result["rows"][1]["derived_status"] == "paid"
    assert a.project_financial_documents("rec1")[0]["payment_status"] == "unpaid"
    assert a.project_financial_reconciliation_report("rec1", "csv", tmp_path/"reconciliation.csv").exists()


def test_financial_document_status_summary_uses_calculated_status(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project("وضعیت اسناد","status1")
    a.add_project_financial_document("status1","S-1","فاکتور",1000,payment_status="unpaid")
    a.add_project_financial_document("status1","S-2","فاکتور",500,payment_status="paid")
    result=a.project_financial_document_status_summary("status1")
    assert result["document_count"]==2
    assert result["counts"]["unpaid"]==1
    assert result["counts"]["paid"]==1
    assert result["amounts"]["unpaid"]==1000
    assert result["mismatch_count"]==1


def test_counterparty_financial_rollup_uses_stable_ids_and_legacy_names(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project("رول‌آپ طرف حساب","roll1")
    cp=a.add_project_counterparty("roll1","پیمانکار")
    a.add_project_commitment("roll1",1000,paid_amount=300,counterparty="پیمانکار")
    a.add_project_cost("roll1","مصالح",200,counterparty="پیمانکار")
    a.add_project_receipt("roll1",500,counterparty="پیمانکار")
    a.add_project_financial_document("roll1","R-1","فاکتور",800,counterparty="پیمانکار")
    rows=a.project_counterparty_financial_rollup("roll1")
    assert len(rows)==1
    assert rows[0]["counterparty_id"]==cp["id"]
    assert rows[0]["commitment_amount"]==1000
    assert rows[0]["paid_commitments"]==300
    assert rows[0]["cost_amount"]==200
    assert rows[0]["receipt_amount"]==500
    assert rows[0]["document_amount"]==800


def test_project_financial_due_summary_exposes_risk_totals(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project("خلاصه سررسید","due1")
    a.add_project_commitment("due1",1000,due_date="1405/06/01")
    a.add_project_commitment("due1",500,due_date="1405/08/01")
    result=a.project_financial_due_summary("due1","1405/07/01")
    assert result["overdue_count"]==1
    assert result["overdue_amount"]==1000
    assert result["upcoming_count"]==1
    assert result["total_open_amount"]==1500
    assert result["highest_risk"]["status"]=="معوق"

def test_jalali_date_validation_rejects_invalid_days_and_accepts_leap_esfand(tmp_path):
    from core.platform.application import _normalize_date_key
    assert _normalize_date_key("۱۴۰۵/۰۶/۳۱") == "1405/06/31"
    assert _normalize_date_key("۱۴۰۵/۰۷/۳۱") is None
    assert _normalize_date_key("۱۴۰۳/۱۲/۳۰") == "1403/12/30"
    assert _normalize_date_key("۱۴۰۲/۱۲/۳۰") is None
    assert _normalize_date_key("۱۴۰۵/۰۲/۳۲") is None


def test_financial_rollup_report_kpi_audit_and_id_ledger(tmp_path):
    a=StructuralProApp(tmp_path)
    a.create_project("کنترل جامع","audit1")
    cp=a.add_project_counterparty("audit1","پیمانکار")
    a.add_project_commitment("audit1",1000,paid_amount=250,counterparty=cp["name"],due_date="1405/06/01")
    a.add_project_cost("audit1","مصالح",200,counterparty=cp["name"])
    a.add_project_receipt("audit1",500,counterparty=cp["name"])
    a.add_project_financial_document("audit1","A-1","فاکتور",800,counterparty=cp["name"],payment_status="unpaid")
    roll=a.project_counterparty_financial_rollup("audit1")
    assert roll[0]["counterparty_id"]==cp["id"]
    assert a.project_counterparty_financial_rollup_report("audit1","csv",tmp_path/"rollup.csv").exists()
    ledger=a.project_counterparty_ledger_by_id("audit1",cp["id"])
    assert ledger["row_count"]==4
    k=a.project_financial_kpi_summary("audit1","1405/07/01")
    assert k["overdue_count"]==1 and k["overdue_amount"]==750
    audit=a.project_financial_audit_summary("audit1")
    assert audit["document_count"]==1 and audit["unpaid_documents"]==1

def test_financial_control_filters_exposure_matrix_and_integrity(tmp_path):
    a=StructuralProApp(tmp_path); a.create_project("کنترل","fc1")
    cp=a.add_project_counterparty("fc1","پیمانکار")
    c=a.add_project_commitment("fc1",1000,paid_amount=400,counterparty=cp["name"])
    a.add_project_financial_document("fc1","F-1","فاکتور",600,counterparty=cp["name"],payment_status="unpaid",commitment_id=c["id"])
    assert len(a.project_financial_documents_by_status("fc1","unpaid"))==1
    assert len(a.project_financial_documents_by_counterparty("fc1",cp["id"]))==1
    ex=a.project_counterparty_exposure("fc1",cp["id"])
    assert ex["unpaid_commitments"]==600
    matrix=a.project_financial_document_status_matrix("fc1")
    assert matrix["matrix"]["partial"]["count"]==1
    assert a.project_financial_integrity_audit("fc1")["healthy"] is True


def test_statement_activity_snapshot_and_exports(tmp_path):
    a=StructuralProApp(tmp_path); a.create_project("صورت","st1")
    a.add_takeoff("st1","building","slab",length=2,width=3,member_code="S1")
    a.open_project("st1")["boq"][0]["price_code"]="S1"
    p=a.open_project("st1"); p["boq"][0]["unit_price"]=100; p["boq"][0]["quantity"]=6; a.store.save("st1",p)
    a.save_statement_period("st1",current_quantities={"S1":2})
    assert a.project_statement_summary("st1")["period_count"]==1
    assert a.project_statement_period("st1",1)["number"]==1
    assert a.project_statement_report("st1","csv",tmp_path/"statement.csv").exists()
    act=a.project_activity_summary("st1")
    assert act["takeoffs"]==1 and act["statement_periods"]==1
    snap=a.project_financial_control_snapshot("st1","1405/07/01")
    assert snap["integrity"]["healthy"] is True
    assert a.project_financial_control_report("st1","1405/07/01","csv",tmp_path/"control.csv").exists()


def test_financial_integrity_detects_broken_reference(tmp_path):
    a=StructuralProApp(tmp_path); a.create_project("صحت","int1")
    a.add_project_financial_document("int1","BAD","فاکتور",100,commitment_id=None)
    p=a.open_project("int1"); p["financial_documents"][0]["receipt_id"]=999; a.store.save("int1",p)
    audit=a.project_financial_integrity_audit("int1")
    assert audit["healthy"] is False
    assert audit["issue_count"]==1
