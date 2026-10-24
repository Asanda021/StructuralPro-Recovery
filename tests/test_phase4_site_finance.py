from copy import deepcopy
from decimal import Decimal
import pytest
from test_phase4_site_materials import p as material_fixture,rule,need,stock,close,run as material_run
from test_statement_amendment_workflow import fixture,version

@pytest.mark.parametrize('case',['normal','stale_stock','existing_record_bypass','sqlite_rollback'])
def test_purchase_atomic_handoff_existing_ledger(tmp_path,case):
    a,docs,path,_=fixture(tmp_path)
    try:
        proof={'path':str(path),'sha256':docs[0]['sha256'],'reference':'TEST'}
        def cmd(op,actor='writer',**data):return a.site_command('P',op,actor=actor,reason='TEST ONLY',expected_version=version(a),**data)
        cmd('policy',actor='synthetic-owner',owner='synthetic-owner',source=proof,permissions={k:['writer','reviewer','approver'] for k in ['create','review','approve','issue','adjust','finance']})
        # Existing protected data stays untouched. Use a documented BOQ approval for this snapshot.
        from test_phase4_structure import structure,activity
        structure(a);activity(a)
        cmd('material_rule_create',id='R',material_code='BLK',specification='TEST BLOCK',source_version='1',source=proof,base_unit='m2',material_unit='count',ratio='10',waste_percent='0')
        cmd('material_rule_review',actor='reviewer',id='R');cmd('material_rule_approve',actor='approver',id='R')
        row=a.open_project('P')['boq'][0]
        from core.projects.controls import boq_basis
        cmd('material_need',id='N',rule_id='R',source_ids=row['source_ids'],item_code=row['item_code'],activity_id='A',floor_ids=['F1'],zone_ids=[],period_start='2026-10-01',period_end='2026-10-31',quantity_approval={'source':proof,'approved_by':'engineer','source_version':'1','basis_digest':boq_basis(a.open_project('P'),row)})
        cmd('inventory_opening',id='O',material_code='BLK',unit='count',quantity='0',date='2026-10-01',reference='OPEN',source=proof,confirmed=True)
        cmd('inventory_close',id='CL',material_code='BLK',unit='count',period_start='2026-10-01',period_end='2026-10-31',source=proof,confirmed=True)
        purchase=cmd('purchase_draft',id='BUY',requirement_id='N',as_of='2026-10-23',owner='writer',supplier='TEST supplier',price='1.000000000000000001',currency='IRR',price_source=proof)
        cmd('purchase_review',actor='reviewer',id='BUY');cmd('purchase_approve',actor='approver',id='BUY')
        before=deepcopy(a.open_project('P'));assert not before.get('financial_records')
        if case=='stale_stock':
            cmd('inventory_receipt',id='LATE',material_code='BLK',unit='count',quantity='100',date='2026-10-24',reference='LATE',source=proof,confirmed=True)
            cmd('inventory_close',id='LATE-CLOSE',material_code='BLK',unit='count',period_start='2026-10-01',period_end='2026-10-31',source=proof,confirmed=True)
            current=a.open_project('P')
            with pytest.raises(ValueError):cmd('purchase_commit',id='BUY',date='2026-10-24',confirmed=True)
            assert a.open_project('P')==current
            return
        if case=='existing_record_bypass':
            record=a.financial_command('P','create',actor='writer',expected_version=version(a),kind='commitment',reference='SITE-PR:BUY',amount='1',currency='IRR',date='2026-10-23',counterparty='UNRELATED',description='unrelated',source_documents=docs)
            current=a.open_project('P')
            with pytest.raises(ValueError):a.project_control_command('P','site_purchase_commit',actor='writer',reason='bypass',expected_version=version(a),id='BUY',date='2026-10-23',confirmed=True,ledger_id=record['id'])
            assert a.open_project('P')==current
            return
        if case=='sqlite_rollback':
            import sqlite3
            a.store.db.execute("CREATE TEMP TRIGGER fail_revision BEFORE INSERT ON revisions BEGIN SELECT RAISE(ABORT,'injected revision failure'); END")
            with pytest.raises(sqlite3.IntegrityError):cmd('purchase_commit',id='BUY',date='2026-10-23',confirmed=True)
            assert a.open_project('P')==before
            a.store.db.execute('DROP TRIGGER fail_revision')
        with pytest.raises(ValueError):cmd('purchase_commit',id='BUY',date='2026-10-23',confirmed=False)
        assert a.open_project('P')==before
        result=cmd('purchase_commit',id='BUY',date='2026-10-23',confirmed=True)
        p=a.open_project('P');record=p['financial_records'][0]
        assert record['status']=='DRAFT' and record['kind']=='commitment'
        assert Decimal(str(record['amount']))==Decimal(purchase['quantity'])*Decimal(purchase['price'])
        assert p['boq']==before['boq'] and p['statement_periods']==before['statement_periods']
        assert not p.get('commitment_entries')
        with pytest.raises(ValueError):cmd('purchase_commit',id='BUY',date='2026-10-23',confirmed=True)
        assert len(a.open_project('P')['financial_records'])==1
    finally:a.store.close()
