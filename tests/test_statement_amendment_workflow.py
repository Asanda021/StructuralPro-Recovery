"""Explicit synthetic contract, owner authority and independent currency references."""
import hashlib
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp

def fixture(tmp_path):
    a=StructuralProApp(tmp_path/'db');a.create_project('اصلاحیه با اسناد مصنوعی','P')
    p=a.open_project('P');p['metadata']['financial_owner_id']='synthetic-owner';a.store.save('P',p)
    a.add_takeoff('P','building','wall',source_id='wall-1',system='L1',length=10,height=1,count=1,openings=0,price_code='W',unit_price=100)
    prices=tmp_path/'prices.csv';prices.write_text('year,group,chapter,code,description,unit,unit_price\n1405,ابنیه,01,W,دیوار,m2,100\n')
    a.import_project_pricebook('P',prices,year=1405,approved_by='synthetic-price-reviewer')
    proof=tmp_path/'signed-detail.txt';proof.write_text('EXPLICIT SYNTHETIC OWNER POLICY AND MEASUREMENT DETAIL; NOT A REAL CONTRACT')
    docs=[{'ref':'DETAIL-1','path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest()}]
    policy={'money':{'decimal_places':2,'rounding':'ROUND_HALF_UP','currency':'IRR'},
            'authorities':{'writer':['create'],'reviewer':['review'],'approver':['approve','post']}}
    a.configure_statement_amendments('P',owner_id='synthetic-owner',policy=policy,
                                    source_documents=docs,expected_project_version=version(a))
    a.save_statement_period('P',current_quantities={'W':5},retention_rate=.1,advance_recovery_rate=.05,tax_rate=.09,insurance_rate=.02)
    a.save_statement_period('P',current_quantities={'W':2},retention_rate=.1,advance_recovery_rate=.05,tax_rate=.09,insurance_rate=.02)
    return a,docs,proof,prices

def version(a):return a.open_project('P')['_meta']['version']
def draft(a,docs,qty='4'):
    return a.create_statement_amendment('P',1,created_by='writer',reason='اصلاح اندازه‌گیری مستند',source_documents=docs,
        lines=[{'price_code':'W','source_id':'wall-1','corrected_period_quantity':qty,'reason':'بازبینی سطح','detail_source_ref':'DETAIL-1'}],expected_project_version=version(a))

def advance(a,d):
    d=a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=d['revision'],expected_project_version=version(a))
    d=a.approve_statement_amendment('P',d['amendment_id'],approved_by='approver',expected_content_digest=d['content_digest'],expected_revision=d['revision'],expected_project_version=version(a))
    return a.post_statement_amendment('P',d['amendment_id'],posted_by='approver',expected_revision=d['revision'],expected_project_version=version(a))

def test_negative_positive_and_zero_delta_preserve_original_and_boq(tmp_path):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P');issued=deepcopy(before['statement_periods']);boq=deepcopy(before['boq'])
    d=advance(a,draft(a,docs,'4'));assert d['status']=='POSTED'
    assert d['lines'][0]['delta_quantity']=='-1'
    assert d['deltas']['gross_current']=='-100.00'
    assert d['deltas']['payable_current']=='-90.95'
    d2=advance(a,draft(a,docs,'6'));assert d2['lines'][0]['delta_quantity']=='2'
    assert d2['deltas']['payable_current']=='181.90'
    d3=advance(a,draft(a,docs,'6'));assert d3['deltas']['payable_current']=='0.00'
    assert len({x['amendment_id'] for x in a.statement_amendments('P')})==3
    p=a.open_project('P');assert p['statement_periods']==issued and p['boq']==boq and p['takeoffs']==before['takeoffs']
    result=a.statement_amendment_summary('P',1)
    assert result['original']['payable_current']=='454.75'
    assert result['net']['payable_current']=='545.70'
    assert result['lines'][0]['net_quantity']=='6'
    a.store.close();a=StructuralProApp(tmp_path/'db')
    assert a.statement_amendment_summary('P',1)==result and a.store.integrity_check()['ok'];a.store.close()

def test_next_period_uses_net_quantity_once(tmp_path):
    a,docs,_,_=fixture(tmp_path);advance(a,draft(a,docs,'4'))
    p=a.save_statement_period('P',current_quantities={'W':2})
    assert p['lines'][0]['previous_quantity']==6 and p['lines'][0]['cumulative_quantity']==8
    assert p['gross_current']==200;a.store.close()

@pytest.mark.parametrize('quantity',[True,'NaN','Infinity','-1','9'])
def test_bad_or_over_contract_quantities_roll_back(tmp_path,quantity):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P')
    with pytest.raises(ValueError):draft(a,docs,quantity)
    assert a.open_project('P')==before;a.store.close()

def test_self_or_unregistered_approval_is_rejected(tmp_path):
    a,docs,_,_=fixture(tmp_path);d=draft(a,docs);before=a.open_project('P')
    with pytest.raises(ValueError):a.review_statement_amendment('P',d['amendment_id'],reviewed_by='writer',expected_revision=1,expected_project_version=version(a))
    assert a.open_project('P')==before
    d=a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=1,expected_project_version=version(a))
    for actor in ['writer','reviewer','unknown','']:
        before=a.open_project('P')
        with pytest.raises(ValueError):a.approve_statement_amendment('P',d['amendment_id'],approved_by=actor,expected_revision=d['revision'],expected_content_digest=d['content_digest'],expected_project_version=version(a))
        assert a.open_project('P')==before
    a.store.close()

def test_tampered_digest_document_and_pricebook_never_post(tmp_path):
    a,docs,proof,prices=fixture(tmp_path);d=draft(a,docs)
    d=a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=1,expected_project_version=version(a));before=a.open_project('P')
    with pytest.raises(ValueError):a.approve_statement_amendment('P',d['amendment_id'],approved_by='approver',expected_revision=d['revision'],expected_content_digest='0'*64,expected_project_version=version(a))
    assert a.open_project('P')==before
    d=a.approve_statement_amendment('P',d['amendment_id'],approved_by='approver',expected_revision=d['revision'],expected_content_digest=d['content_digest'],expected_project_version=version(a))
    original=proof.read_bytes();proof.write_bytes(b'changed detail');before=a.open_project('P')
    with pytest.raises(ValueError):a.post_statement_amendment('P',d['amendment_id'],posted_by='approver',expected_revision=d['revision'],expected_project_version=version(a))
    assert a.open_project('P')==before
    proof.write_bytes(original);prices.write_text(prices.read_text().replace(',100\n',',200\n'))
    with pytest.raises(ValueError):a.post_statement_amendment('P',d['amendment_id'],posted_by='approver',expected_revision=d['revision'],expected_project_version=version(a))
    assert a.open_project('P')==before;a.store.close()

def test_double_post_and_raw_payload_rewrite_are_rejected(tmp_path):
    a,docs,_,_=fixture(tmp_path);d=advance(a,draft(a,docs));before=a.open_project('P')
    with pytest.raises(ValueError):a.post_statement_amendment('P',d['amendment_id'],posted_by='approver',expected_revision=d['revision'],expected_project_version=version(a))
    p=deepcopy(before);p['statement_amendments'][0]['deltas']['payable_current']='999.00'
    with pytest.raises(ValueError):a.store.save('P',p)
    p=deepcopy(before);p['statement_amendments']=[]
    with pytest.raises(ValueError):a.store.save('P',p)
    assert a.open_project('P')==before;a.store.close()

def test_stale_project_or_revision_never_overwrites_other_instance(tmp_path):
    a,docs,_,_=fixture(tmp_path);d=draft(a,docs);stale=version(a);other=StructuralProApp(tmp_path/'db')
    other.add_project_cost('P','مصالح',25);before=other.open_project('P')
    with pytest.raises(RuntimeError):a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=1,expected_project_version=stale)
    assert other.open_project('P')==before
    with pytest.raises(RuntimeError):a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=99,expected_project_version=version(a))
    assert other.open_project('P')==before;a.store.close();other.store.close()


def test_edit_reject_and_missing_policy_fail_closed(tmp_path):
    a,docs,_,_=fixture(tmp_path);d=draft(a,docs)
    data={'reason':'اصلاح مستند پیش‌نویس','source_documents':docs,
          'lines':[{'price_code':'W','source_id':'wall-1','corrected_period_quantity':'3','reason':'دیتایل','detail_source_ref':'DETAIL-1'}]}
    d=a.edit_statement_amendment('P',d['amendment_id'],edited_by='writer',expected_revision=1,expected_project_version=version(a),**data)
    assert d['revision']==2 and d['status']=='DRAFT' and d['lines'][0]['delta_quantity']=='-2'
    d=a.reject_statement_amendment('P',d['amendment_id'],rejected_by='reviewer',reason='عدم پذیرش مدرک',expected_revision=2,expected_project_version=version(a))
    assert d['status']=='REJECTED' and not a.statement_amendment_summary('P',1)['posted_amendment_ids']
    with pytest.raises(ValueError):a.edit_statement_amendment('P',d['amendment_id'],edited_by='writer',expected_revision=3,expected_project_version=version(a),**data)
    a.create_project('فاقد سیاست','U')
    with pytest.raises(ValueError):a.create_statement_amendment('U',1,created_by='writer',reason='x',source_documents=docs,lines=data['lines'],expected_project_version=a.open_project('U')['_meta']['version'])
    a.store.close()

@pytest.mark.parametrize('change',[{'source_id':'other-member'},{'detail_source_ref':'absent'},{'unit_price':200},{'corrected_period_quantity':'1e129'}])
def test_unknown_sources_and_contract_repricing_rejected(tmp_path,change):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P')
    line={'price_code':'W','source_id':'wall-1','corrected_period_quantity':'4','reason':'دیتایل','detail_source_ref':'DETAIL-1',**change}
    with pytest.raises(ValueError):a.create_statement_amendment('P',1,created_by='writer',reason='دیتایل',source_documents=docs,lines=[line],expected_project_version=version(a))
    assert a.open_project('P')==before;a.store.close()

def test_dashboard_is_net_and_cash_ledgers_unchanged(tmp_path):
    a,docs,_,_=fixture(tmp_path);before=a.open_project('P');advance(a,draft(a,docs,'4'))
    dashboard=a.financial_dashboard('P')
    assert dashboard['cumulative_work']==600 and dashboard['total_payable']==545.7
    after=a.open_project('P')
    for key in ('costs','receipts','payments','commitments'):assert after.get(key)==before.get(key)
    a.store.close()

def test_sqlite_backup_reopen_preserves_posted_financial_identity(tmp_path):
    import sqlite3
    a,docs,_,_=fixture(tmp_path);advance(a,draft(a,docs));before=a.statement_amendment_summary('P',1)
    restore=tmp_path/'restored';restore.mkdir()
    dbpath=restore/'projects.sqlite3'
    # Discover the store's actual database filename, keeping its runtime convention.
    originalpath=a.store.db.execute('PRAGMA database_list').fetchone()[2]
    dbpath=restore/__import__('pathlib').Path(originalpath).name
    dest=sqlite3.connect(dbpath);a.store.db.backup(dest);dest.close();a.store.close()
    restored=StructuralProApp(restore)
    assert restored.statement_amendment_summary('P',1)==before
    assert restored.store.integrity_check()['ok'];restored.store.close()

def _concurrent_post_worker(db,doc,version_number,barrier,results):
    app=StructuralProApp(db)
    try:
        barrier.wait(timeout=20)
        app.post_statement_amendment('P',doc['amendment_id'],posted_by='approver',expected_revision=doc['revision'],expected_project_version=version_number)
        results.put('POSTED')
    except RuntimeError:results.put('STALE')
    except Exception as e:results.put(type(e).__name__+': '+str(e))
    finally:app.store.close()

def test_two_processes_only_one_post_commits(tmp_path):
    import multiprocessing
    a,docs,_,_=fixture(tmp_path);d=draft(a,docs)
    d=a.review_statement_amendment('P',d['amendment_id'],reviewed_by='reviewer',expected_revision=1,expected_project_version=version(a))
    d=a.approve_statement_amendment('P',d['amendment_id'],approved_by='approver',expected_revision=d['revision'],expected_content_digest=d['content_digest'],expected_project_version=version(a))
    v=version(a);a.store.close()
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(2);results=ctx.Queue()
    workers=[ctx.Process(target=_concurrent_post_worker,args=(tmp_path/'db',d,v,barrier,results)) for _ in range(2)]
    for worker in workers:worker.start()
    outcomes=[results.get(timeout=30) for _ in workers]
    for worker in workers:worker.join(timeout=10);assert worker.exitcode==0
    assert sorted(outcomes)==['POSTED','STALE']
    a=StructuralProApp(tmp_path/'db');assert a.statement_amendment_summary('P',1)['amendment_deltas']['payable_current']=='-90.95';a.store.close()


def test_high_precision_net_quantity_is_preserved_in_following_period(tmp_path):
    a,docs,_,_=fixture(tmp_path);advance(a,draft(a,docs,'4.12345678901234567890123456789'))
    assert a.statement_amendment_summary('P',1)['lines'][0]['net_quantity']=='4.12345678901234567890123456789'
    before=a.open_project('P')
    period=a.save_statement_period('P',current_quantities={'W':'1'})
    from decimal import Decimal
    assert Decimal(str(period['lines'][0]['previous_quantity']))==Decimal('6.12345678901234567890123456789')
    assert Decimal(str(period['lines'][0]['cumulative_quantity']))==Decimal('7.12345678901234567890123456789')
    assert a.open_project('P')['statement_periods'][:-1]==before['statement_periods'];a.store.close()
