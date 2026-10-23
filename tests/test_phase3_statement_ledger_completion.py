from decimal import Decimal
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from core.commercial.finance_depth import FinancePaymentControl,PaymentRecord
from test_statement_amendment_workflow import fixture,version,draft,advance


def test_cash_flow_does_not_treat_accrued_cost_as_cash():
    result=FinancePaymentControl().cash_flow(costs=[{'amount':'100','date':'2026-10-23'}],payments=[{'amount':'40','date':'2026-10-23'}])
    assert result['cash_out']==40


def test_statement_summary_keeps_small_decimal_digits(tmp_path):
    from test_work_issued_financial_integrity import priced
    a=priced(tmp_path)
    a.save_statement_period('P',current_quantities={'W':'7'})
    # Period inputs are real and all rates explicitly zero for this precision test.
    a.save_statement_period('P',current_quantities={'W':'0.000000000000000000123'})
    summary=a.project_statement_summary('P')
    assert Decimal(str(summary['gross_total']))==Decimal('700.0000000000000000123')
    a.store.close()


def test_statement_workspace_requires_explicit_terms_and_two_independent_roles(tmp_path):
    a,docs,_,_=fixture(tmp_path)
    a.configure_statement_workflow('P',actor='synthetic-owner',expected_version=version(a),terms={
        'contract_id':'TEST-CONTRACT','currency':'IRR','advance_paid':'50',
        'factor_basis':'base_rates_only','retention_rate':'0.1','advance_recovery_rate':'0.1',
        'tax_rate':'0','insurance_rate':'0','other_deduction_rate':'0'},source_documents=docs)
    d=a.statement_workflow('P','create',actor='writer',expected_version=version(a),reference='S3',date='2026-10-23',current_quantities={'W':'1'})
    assert d['status']=='DRAFT'
    with pytest.raises(ValueError):a.statement_workflow('P','approve',actor='writer',expected_version=version(a),id=d['id'])
    d=a.statement_workflow('P','review',actor='reviewer',expected_version=version(a),id=d['id'])
    d=a.statement_workflow('P','approve',actor='approver',expected_version=version(a),id=d['id'])
    d=a.statement_workflow('P','issue',actor='approver',expected_version=version(a),id=d['id'])
    assert d['status']=='ISSUED' and Decimal(str(d['period']['gross_current']))==100
    before=a.open_project('P')
    with pytest.raises(ValueError):a.statement_workflow('P','issue',actor='approver',expected_version=version(a),id=d['id'])
    assert a.open_project('P')==before
    a.store.close()


def ledger(a,op='create',**data):
    from core.commercial.statement_amendment import policy
    data.setdefault('source_documents',[{k:d[k] for k in ('ref','path','sha256')} for d in policy(a.open_project('P'))['source_documents']])
    return a.financial_command('P',op,actor='writer',expected_version=version(a),**data)


def posted(a,kind,reference,amount,**extra):
    r=ledger(a,kind=kind,reference=reference,amount=amount,currency='IRR',date='2026-10-23',counterparty='مصنوعی',description='آزمون',**extra)
    a.financial_command('P','review',actor='reviewer',expected_version=version(a),id=r['id'])
    a.financial_command('P','approve',actor='approver',expected_version=version(a),id=r['id'])
    return a.financial_command('P','post',actor='approver',expected_version=version(a),id=r['id'])


def test_ledger_actual_cost_partial_payment_oracle_reversal_reopen(tmp_path):
    a,docs,_,_=fixture(tmp_path)
    b=posted(a,'budget','B1','800')
    c=posted(a,'commitment','C1','700')
    cost=posted(a,'cost','INV1','600',commitment_id=c['id'])
    pay=posted(a,'payment','BANK1','200',cost_id=cost['id'],commitment_id=c['id'])
    snap=a.verified_financial_snapshot('P')
    assert Decimal(str(snap['actual_cost']))==600
    assert Decimal(str(snap['paid']))==200
    assert Decimal(str(snap['debt']))==400
    assert Decimal(str(snap['unpaid_commitments']))==500
    assert Decimal(str(snap['budget_variance']))==200
    before=a.open_project('P')
    with pytest.raises(ValueError):ledger(a,kind='payment',reference='BANK1',amount='200',currency='IRR',date='2026-10-23',counterparty='مصنوعی',description='duplicate')
    assert a.open_project('P')==before
    a.financial_command('P','reverse',actor='approver',expected_version=version(a),id=pay['id'],reference='REV1',date='2026-10-23',reason='برگشت مستند آزمون',source_documents=docs)
    snap=a.verified_financial_snapshot('P');assert snap['paid']==0 and snap['debt']==600
    p=deepcopy(a.open_project('P'));p['payment_entries']=[]
    with pytest.raises(ValueError):a.store.save('P',p)
    a.store.close();a=StructuralProApp(tmp_path/'db')
    assert a.verified_financial_snapshot('P')==snap
    assert a.store.integrity_check()['ok'];a.store.close()


@pytest.mark.parametrize('change',[{'amount':True},{'amount':'NaN'},{'amount':'-1'},{'amount':'1e129'},{'currency':'IRT'},{'date':'2026-02-30'},{'reference':''}])
def test_invalid_ledger_record_is_atomic(tmp_path,change):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P')
    data=dict(kind='payment',reference='BANK',amount='1',currency='IRR',date='2026-10-23',counterparty='fixture',description='test');data.update(change)
    with pytest.raises(ValueError):ledger(a,**data)
    assert a.open_project('P')==before and not a.store.db.in_transaction;a.store.close()


def test_excess_payment_and_stale_approval_never_post(tmp_path):
    a,docs,_,_=fixture(tmp_path);c=posted(a,'commitment','C','10');cost=posted(a,'cost','INV','10',commitment_id=c['id'])
    posted(a,'payment','BANK1','8',cost_id=cost['id'],commitment_id=c['id'])
    r=ledger(a,kind='payment',reference='BANK2',amount='3',currency='IRR',date='2026-10-23',counterparty='x',description='test',cost_id=cost['id'],commitment_id=c['id'])
    a.financial_command('P','review',actor='reviewer',expected_version=version(a),id=r['id'])
    a.financial_command('P','approve',actor='approver',expected_version=version(a),id=r['id'])
    before=a.open_project('P')
    with pytest.raises(ValueError):a.financial_command('P','post',actor='approver',expected_version=version(a),id=r['id'])
    assert a.open_project('P')==before
    with pytest.raises(RuntimeError):a.financial_command('P','post',actor='approver',expected_version=1,id=r['id'])
    assert a.open_project('P')==before;a.store.close()


def setup_workflow(a,docs,**overrides):
    terms={'contract_id':'TEST','currency':'IRR','advance_paid':'35','factor_basis':'base_rates_only','retention_rate':'0','advance_recovery_rate':'0.5','tax_rate':'0','insurance_rate':'0','other_deduction_rate':'0'};terms.update(overrides)
    a.configure_statement_workflow('P',actor='synthetic-owner',expected_version=version(a),terms=terms,source_documents=docs)


def issue(a,ref,qty):
    d=a.statement_workflow('P','create',actor='writer',expected_version=version(a),reference=ref,date='2026-10-23',current_quantities={'W':qty})
    for op,actor in [('review','reviewer'),('approve','approver'),('issue','approver')]:
        d=a.statement_workflow('P',op,actor=actor,expected_version=version(a),id=d['id'])
    return d


def test_capped_advance_amendment_uses_actual_issued_before(tmp_path):
    from test_statement_amendment_workflow import draft,advance
    a,docs,_,_=fixture(tmp_path)
    setup_workflow(a,docs)
    d=issue(a,'S3','1')
    # Prior legacy periods recovered 35; the explicit remaining advance is zero.
    assert Decimal(str(d['period']['advance_recovery']))==0
    amendment=a.create_statement_amendment('P',3,created_by='writer',reason='اصلاح آزمون',source_documents=docs,
        lines=[{'price_code':'W','source_id':'wall-1','corrected_period_quantity':'0.5','reason':'اصلاح','detail_source_ref':'DETAIL-1'}],expected_project_version=version(a))
    assert Decimal(amendment['effective_before']['advance_recovery'])==0
    assert Decimal(amendment['deltas']['payable_current'])==Decimal('-50')
    a.store.close()


@pytest.mark.parametrize('fmt',['pdf','xlsx','docx','csv'])
def test_verified_reports_are_real_and_reopen(tmp_path,fmt):
    a,docs,_,_=fixture(tmp_path);posted(a,'budget','B','1000')
    c=posted(a,'commitment','C','800');cost=posted(a,'cost','I','600',commitment_id=c['id']);posted(a,'payment','PAY','200',commitment_id=c['id'],cost_id=cost['id'])
    p=tmp_path/('finance.'+fmt);a.verified_financial_report('P',fmt,p)
    assert p.stat().st_size>100
    if fmt=='xlsx':
        from openpyxl import load_workbook
        b=load_workbook(p);assert all(s.sheet_view.rightToLeft for s in b)
    if fmt=='docx':
        from docx import Document
        b=Document(p);assert b.tables and 'bidi' in b._element.xml
    if fmt=='pdf':
        import fitz
        with fitz.open(p) as b:assert len(b)>0 and b[0].get_text()
    if fmt=='csv':assert '۶۰۰' in p.read_text(encoding='utf-8-sig') or '600' in p.read_text(encoding='utf-8-sig')
    s=tmp_path/('statement.'+fmt);a.verified_statement_report('P',2,fmt,s);assert s.stat().st_size>100
    a.store.close()


def test_concurrent_write_during_dispatch_cannot_be_overwritten(tmp_path,monkeypatch):
    import core.commercial.financial_ledger as module
    a,docs,_,_=fixture(tmp_path);other=StructuralProApp(tmp_path/'db');original=module.ledger_dispatch
    def competing(p,command):
        result=original(p,command)
        changed=other.open_project('P');changed['metadata']['concurrent']='preserved';other.store.save('P',changed)
        return result
    monkeypatch.setattr(module,'ledger_dispatch',competing)
    with pytest.raises(RuntimeError):ledger(a,kind='budget',reference='RACE',amount='10',currency='IRR',date='2026-10-23',counterparty='x',description='x')
    p=other.open_project('P');assert p['metadata']['concurrent']=='preserved' and not p.get('financial_records')
    assert not a.store.db.in_transaction;a.store.close();other.store.close()


def test_unknown_indicators_are_not_zero(tmp_path):
    a,docs,_,_=fixture(tmp_path);s=a.verified_financial_snapshot('P')
    assert s['budget'] is None and s['actual_cost'] is None and s['paid'] is None
    assert s['debt'] is None and s['budget_variance'] is None;a.store.close()


def test_statement_ui_terms_reject_advance_already_recovered(tmp_path):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P')
    with pytest.raises(ValueError):setup_workflow(a,docs,advance_paid='1')
    assert a.open_project('P')==before;a.store.close()


def test_legacy_payment_reader_excludes_documented_reversal(tmp_path):
    a,docs,_,_=fixture(tmp_path);c=posted(a,'commitment','C','100');cost=posted(a,'cost','I','100',commitment_id=c['id'])
    pay=posted(a,'payment','BANK','30',cost_id=cost['id'],commitment_id=c['id'])
    assert a.project_payment_summary('P')['payment_total']==30
    a.financial_command('P','reverse',actor='approver',expected_version=version(a),id=pay['id'],reference='REV',date='2026-10-23',reason='آزمون',source_documents=docs)
    assert a.project_payment_summary('P')['payment_total']==0
    assert a.project_commitment_summary('P')['unpaid_total']==100;a.store.close()


def test_receipt_blocks_amendment_that_would_over_settle(tmp_path):
    a,docs,_,_=fixture(tmp_path);posted(a,'receipt','REC','450',statement_no=1)
    d=draft(a,docs,'1');d=a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=d['revision'],expected_project_version=version(a))
    d=a.approve_statement_amendment('P',d['amendment_id'],approved_by='approver',expected_content_digest=d['content_digest'],expected_revision=d['revision'],expected_project_version=version(a))
    before=a.open_project('P')
    with pytest.raises(ValueError):a.post_statement_amendment('P',d['amendment_id'],posted_by='approver',expected_revision=d['revision'],expected_project_version=version(a))
    assert a.open_project('P')==before;a.store.close()


def test_statement_report_localizes_engineering_units(tmp_path):
    import csv
    a,docs,_,_=fixture(tmp_path);p=tmp_path/'statement.csv';a.verified_statement_report('P',1,'csv',p)
    rows=list(csv.reader(p.open(encoding='utf-8-sig')))
    assert any('متر مربع' in row for row in rows)
    a.store.close()


def test_statement_report_previous_work_includes_posted_amendments(tmp_path):
    import csv
    a,docs,_,_=fixture(tmp_path);advance(a,draft(a,docs,'4'))
    p=tmp_path/'second.csv';a.verified_statement_report('P',2,'csv',p)
    rows=list(csv.reader(p.open(encoding='utf-8-sig')))
    assert any('مقدار قبلی W' in row and '4' in row for row in rows)
    a.store.close()


def amend_period(a,docs,no,quantity):
    d=a.create_statement_amendment('P',no,created_by='writer',expected_project_version=version(a),reason='آزمون استهلاک',source_documents=docs,
        lines=[{'price_code':'W','source_id':'wall-1','corrected_period_quantity':quantity,'reason':'آزمون','detail_source_ref':'DETAIL-1'}])
    return advance(a,d)


def test_later_amendment_uses_posted_before_when_earlier_period_frees_advance(tmp_path):
    a,docs,_,_=fixture(tmp_path);setup_workflow(a,docs,advance_paid='135')
    issue(a,'S3','2');issue(a,'S4','1')
    amend_period(a,docs,3,'1')
    d=amend_period(a,docs,4,'2')
    assert Decimal(d['effective_before']['advance_recovery'])==0
    assert Decimal(d['deltas']['advance_recovery'])==50
    assert Decimal(d['deltas']['payable_current'])==50
    net=a.statement_amendment_summary('P',4)['net']
    assert Decimal(net['advance_recovery'])==50 and Decimal(net['payable_current'])==150
    a.store.close()


def test_all_financial_depth_readers_exclude_reversals(tmp_path):
    a,docs,_,_=fixture(tmp_path);posted(a,'budget','B','1000');c=posted(a,'commitment','C','100');cost=posted(a,'cost','I','100',commitment_id=c['id']);pay=posted(a,'payment','PAY','30',cost_id=cost['id'],commitment_id=c['id'])
    for record,ref in [(pay,'REV-PAY'),(cost,'REV-COST')]:
        a.financial_command('P','reverse',actor='approver',expected_version=version(a),id=record['id'],reference=ref,date='2026-10-23',reason='آزمون برگشت',source_documents=docs)
    assert a.project_cash_flow_control('P')['cash_out']==0
    assert a.project_budget_control('P')['actual_total']==0
    snap=a.project_finance_payment_depth_snapshot('P')
    assert snap['cash_flow']['cash_out']==0 and snap['budget']['actual_total']==0
    a.store.close()


def test_counterparty_rollup_keeps_approved_ledger_digits(tmp_path):
    a,docs,_,_=fixture(tmp_path);a.add_project_counterparty('P','مصنوعی')
    c=posted(a,'commitment','C','100.000000000000000000123')
    row=next(r for r in a.project_counterparty_financial_rollup('P') if r['name']=='مصنوعی')
    assert Decimal(str(row['commitment_amount']))==Decimal('100.000000000000000000123')
    a.store.close()


def test_counterparty_cash_is_only_actual_payment_not_cost_plus_commitment(tmp_path):
    a,docs,_,_=fixture(tmp_path);a.add_project_counterparty('P','مصنوعی')
    c=posted(a,'commitment','C','100');cost=posted(a,'cost','I','100',commitment_id=c['id']);posted(a,'payment','PAY','30',cost_id=cost['id'],commitment_id=c['id'])
    assert a.project_counterparty_ledger('P','مصنوعی')['cash_out']==30
    assert a.project_counterparty_summary('P')['counterparties'][0]['paid_commitments']==30
    a.store.close()


def test_new_ledger_cannot_reuse_existing_legacy_bank_reference(tmp_path):
    a,docs,_,_=fixture(tmp_path);a.add_project_payment('P','10',reference='OLD-BANK',date='2026-10-23')
    before=a.open_project('P')
    with pytest.raises(ValueError):ledger(a,kind='payment',reference='OLD-BANK',amount='10',currency='IRR',date='2026-10-23',counterparty='مصنوعی',description='تکرار سند قبلی')
    assert a.open_project('P')==before;a.store.close()
