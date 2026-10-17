"""Proposal acceptance only: no contract application or real settlement claimed."""
from copy import deepcopy
import hashlib
import pytest
from test_statement_amendment_workflow import fixture,version,draft,advance

def change(q='12',price='100',rate_ref=''):
    return [{'price_code':'W','source_id':'wall-1','quantity':q,'unit_price':price,'unit':'m2','detail_ref':'DETAIL-1','rate_ref':rate_ref}]

@pytest.mark.parametrize('quantity,delta',[('12',200),('8',-200)])
def test_positive_negative_contract_requests_preserve_original_and_block_post(tmp_path,quantity,delta):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P')
    doc=a.create_contract_change_request('P',created_by='explicit-drafter',reason='درخواست مستند',source_documents=docs,lines=change(quantity),expected_project_version=version(a))
    assert doc['status']=='DRAFT' and doc['preview']['delta']==delta
    for key in ('boq','statement_periods','takeoffs'):assert a.open_project('P')[key]==before[key]
    with pytest.raises(ValueError,match='BLOCKED'):a.post_contract_change_request('P',doc['id'])
    current=a.open_project('P');bad=deepcopy(current);bad['contract_change_requests'][0]['status']='POSTED'
    with pytest.raises(ValueError):a.store.save('P',bad)
    assert a.open_project('P')==current;a.store.close();a=type(a)(tmp_path/'db')
    assert a.open_project('P')['contract_change_requests'][0]==doc;a.store.close()

def test_rate_source_and_stale_version_fail_closed(tmp_path):
    a,docs,_,_=fixture(tmp_path);v=version(a);before=a.open_project('P')
    with pytest.raises(ValueError):a.create_contract_change_request('P',created_by='drafter',reason='نرخ',source_documents=docs,lines=change(price='200'),expected_project_version=v)
    assert a.open_project('P')==before
    source=tmp_path/'proposed.csv';source.write_text('code,unit,unit_price\nW,m2,200\n')
    rates=docs+[{'ref':'RATE','path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]
    doc=a.create_contract_change_request('P',created_by='drafter',reason='نرخ پیشنهادی نه مصوب',source_documents=rates,lines=change(price='200',rate_ref='RATE'),expected_project_version=v)
    assert doc['preview']['proposed_changed_lines_total']==2400
    with pytest.raises(RuntimeError):a.create_contract_change_request('P',created_by='drafter',reason='نسخه قدیمی',source_documents=docs,lines=change(),expected_project_version=v)
    with pytest.raises(ValueError):a.post_contract_change_request('P',doc['id']);a.store.close()

def test_settlement_preview_uses_selected_receipts_once_and_no_cash_mutation(tmp_path):
    a,docs,_,_=fixture(tmp_path);advance(a,draft(a,docs,'4'))
    a.add_project_receipt('P','100');a.add_project_receipt('P','999')
    a.add_project_commitment('P','70',paid_amount='20');before=a.open_project('P')
    doc=a.create_settlement_request('P',created_by='explicit-drafter',reason='پیش‌نمایش مستقل',source_documents=docs,receipt_ids=[1],expected_project_version=version(a))
    p=doc['preview'];assert p['original_issued_payable']==636.65 and p['posted_amendment_delta']==-90.95
    assert p['net_issued_payable']==545.7 and p['balance_receivable']==445.7 and p['unpaid_commitments_separate']==50
    current=a.open_project('P')
    for key in ('receipt_entries','commitment_entries','statement_periods','boq'):assert current[key]==before[key]
    for ids in ([1,1],[True],[9]):
        with pytest.raises(ValueError):a.create_settlement_request('P',created_by='drafter',reason='رد ورودی',source_documents=docs,receipt_ids=ids,expected_project_version=version(a))
    with pytest.raises(ValueError,match='BLOCKED'):a.post_settlement_request('P',doc['id'])
    assert a.open_project('P')==current;a.store.close()

def test_request_without_owner_policy_is_draft_only(tmp_path):
    from core.platform.application import StructuralProApp
    a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی بدون اختیار مالی','P')
    proof=tmp_path/'request.txt';proof.write_text('EXPLICIT SYNTHETIC REQUEST; NOT AUTHORITY')
    docs=[{'ref':'REQUEST','path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}]
    d=a.create_settlement_request('P',created_by='actual-input-name',reason='درخواست بدون سیاست',source_documents=docs,receipt_ids=[],expected_project_version=version(a))
    assert d['status']=='DRAFT' and d['preview']['financial_policy_status']=='BLOCKED_OWNER_POLICY_REQUIRED'
    with pytest.raises(ValueError):a.post_settlement_request('P',d['id'])
    a.store.close()
