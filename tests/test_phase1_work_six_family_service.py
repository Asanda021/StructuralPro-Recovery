"""Synthetic SQLite/service acceptance; does not certify geometry or payment."""
from copy import deepcopy
from hashlib import sha256
import json
import pytest
from core.platform.application import StructuralProApp
from core.takeoff.building_six_family_ownership_chat import audit, _digest
from test_phase1_six_family_ownership_chat import sample


def dump(a):
    return '\n'.join(a.store.db.iterdump())


def setup(tmp_path):
    d,p,docs=sample()
    a=StructuralProApp(tmp_path/'project.sqlite');a.create_project('مصنوعی','P-1')
    original=a.open_project('P-1');original.update(p);a.store.save('P-1',original)
    d['project_sha256']=_digest(a.structural_handoff_basis('P-1'))
    paths={}
    for h,raw in docs.items():
        path=tmp_path/h;path.write_bytes(raw);paths[h]=str(path)
    path=tmp_path/'audit.json';path.write_text(json.dumps(d,ensure_ascii=False),encoding='utf-8')
    args=dict(source_path=str(path),source_sha256=sha256(path.read_bytes()).hexdigest(),evidence_files=paths)
    return a,d,args


def save(a,d,args,revision=0,ident='AUDIT-1'):
    return a.save_structural_handoff_draft('P-1',ident,d,expected_revision=revision,**args)


def test_real_service_save_close_reopen_edit_audit_and_history(tmp_path):
    a,d,args=setup(tmp_path);original=deepcopy(a.open_project('P-1'))
    r=save(a,d,args);assert r['revision']==1 and r['status']=='draft'
    a.store.close();a=StructuralProApp(tmp_path/'project.sqlite')
    try:
        assert a.get_structural_handoff_audit('P-1','AUDIT-1')['data']['request']==d
        r=save(a,d,args,1);assert r['revision']==2
        r=a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=2)
        assert r['result']['document_consistent'] and r['revision']==3
        assert r['result']['totals_not_payable']=={'concrete':'7.500','rebar':'7.500','formwork':'7.500'}
        assert not r['result']['ready'] and not r['result']['commit_allowed'] and r['result']['payable_rows']==[]
        p=a.open_project('P-1');assert p['boq']==original['boq'] and p['takeoffs']==original['takeoffs']
        assert [x['record']['revision'] for x in p['structural_handoff_history']]==[1,2]
        assert a.structural_handoff_basis('P-1')=={k:v for k,v in original.items() if k!='_meta'}
        assert a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert a.store.db.execute('pragma foreign_key_check').fetchall()==[]
        before=dump(a)
        with pytest.raises(ValueError):a.commit_structural_handoff_audit('P-1','AUDIT-1',expected_revision=3)
        assert dump(a)==before
    finally:a.store.close()
    b=StructuralProApp(tmp_path/'project.sqlite')
    try:
        r=b.get_structural_handoff_audit('P-1','AUDIT-1');assert not r['stale'] and r['result']['document_consistent']
    finally:b.store.close()


@pytest.mark.parametrize('bad',['revision','float_revision','bool_revision','duplicate','unicode_id','source','evidence','missing','stale_member','direct_history','direct_result','direct_boq'])
def test_invalid_service_operations_never_change_sqlite_or_boq(tmp_path,bad):
    a,d,args=setup(tmp_path)
    try:
        save(a,d,args)
        if bad=='stale_member':
            p=a.open_project('P-1');next(iter(p['reviewed_structural_members'].values()))['revision']=2;a.store.save('P-1',p)
        if bad=='source':open(args['source_path'],'ab').write(b' ')
        if bad=='evidence':open(next(iter(args['evidence_files'].values())),'ab').write(b' altered')
        if bad=='missing':__import__('pathlib').Path(next(iter(args['evidence_files'].values()))).unlink()
        before=dump(a)
        with pytest.raises((ValueError,RuntimeError)):
            if bad in ('revision','float_revision','bool_revision'):
                save(a,d,args,{'revision':0,'float_revision':1.0,'bool_revision':True}[bad])
            elif bad in ('duplicate','unicode_id'):
                save(a,d,args,ident='ANOTHER' if bad=='duplicate' else 'AUDIT-۱')
            elif bad.startswith('direct_'):
                p=a.open_project('P-1')
                if bad=='direct_history':p['structural_handoff_history'].append({'fake':True})
                elif bad=='direct_result':p['structural_handoff_audits']['AUDIT-1']['result']={'commit_allowed':True}
                else:p['boq'].append({'unapproved':True})
                a.store.save('P-1',p,structural_handoff_command={'audit_id':'AUDIT-1','expected_revision':1}) if bad=='direct_boq' else a.store.save('P-1',p)
            else:a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        assert dump(a)==before
    finally:a.store.close()


def test_second_sqlite_writer_cas_rejects_audit_race(tmp_path,monkeypatch):
    a,d,args=setup(tmp_path);save(a,d,args)
    b=StructuralProApp(tmp_path/'project.sqlite');real=a.store.save
    def competing(*v,**kw):
        p=b.open_project('P-1');p['name']='تغییر هم‌زمان';b.store.save('P-1',p)
        return real(*v,**kw)
    monkeypatch.setattr(a.store,'save',competing)
    try:
        with pytest.raises(RuntimeError):a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        p=b.open_project('P-1');assert p['structural_handoff_audits']['AUDIT-1']['revision']==1
        assert p['boq']==[{'legacy':'unchanged'}]
    finally:a.store.close();b.store.close()


@pytest.mark.parametrize('digits',['۱','١'])
def test_unicode_digit_alias_cannot_pay_same_physical_part_twice(digits):
    d,p,files=sample();d['claims'][0]['physical_id']='PART-1';d['claims'][3]['physical_id']='PART-'+digits
    r=audit(d,p,documents=files)
    assert not r['document_consistent'] and r['totals_not_payable']=={} and r['payable_rows']==[]


def test_invalid_claim_persists_blocked_result_not_partial_totals(tmp_path):
    a,d,args=setup(tmp_path)
    try:
        d['claims'][-1]['quantity_exact']='NaN'
        path=__import__('pathlib').Path(args['source_path']);path.write_text(json.dumps(d),encoding='utf-8');args['source_sha256']=sha256(path.read_bytes()).hexdigest()
        save(a,d,args);r=a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        assert r['status']=='blocked' and not r['result']['document_consistent']
        assert r['result']['totals_not_payable']=={} and a.open_project('P-1')['boq']==[{'legacy':'unchanged'}]
    finally:a.store.close()


def test_six_public_draft_apis_feed_actual_service_and_reopen(tmp_path):
    from test_foundation_tie_stage23_chat import sample as foundation
    from test_reviewed_structural_five_priorities import approved
    from test_beam_stage21 import specialist
    from test_roof_specialist_work import sample as roof
    from test_stair_work_core import sample as stair
    a=StructuralProApp(tmp_path/'real.sqlite');a.create_project('شش خانواده مصنوعی','P-1')
    d,_,docs=sample()
    inputs=[('foundation',foundation('isolated_footing','F1')),
            ('tie_beam',foundation()),('column',approved()),
            ('beam',specialist()),('slab',roof()),('stair',stair(tmp_path,pid='P-1'))]
    try:
        for family,data in inputs:
            data['physical_id']='MEMBER-'+family
            data['source']['source_id']='SYN:'+family
            if family in ('foundation','tie_beam','column'):
                a.save_structural_member_draft('P-1',data,expected_revision=0)
            elif family=='beam':a.save_beam_detail_draft('P-1',data,expected_revision=0)
            else:a.save_aec_system_draft('P-1',data,expected_revision=0)
        p=a.structural_handoff_basis('P-1')
        for link in d['links']:
            key,record=next((k,v) for k,v in p[link['registry']].items()
                            if v['data']['source']['source_id']==link['source_id'])
            data=record['data']
            link.update(record_key=key,record_revision=record['revision'],record_sha256=_digest(record),
                        member_id=data.get('member_id',data.get('beam_id',data.get('system_id'))))
        d['project_sha256']=_digest(p)
        source=tmp_path/'actual-six.json';source.write_text(json.dumps(d),encoding='utf-8')
        paths={}
        for h,b in docs.items():
            path=tmp_path/h;path.write_bytes(b);paths[h]=str(path)
        args=dict(source_path=str(source),source_sha256=sha256(source.read_bytes()).hexdigest(),evidence_files=paths)
        before=dump(a)
        preview=a.preview_structural_handoff('P-1',d,**args)
        assert preview['audit']['document_consistent'] and preview['rows']==[] and dump(a)==before
        save(a,d,args)
    finally:a.store.close()
    b=StructuralProApp(tmp_path/'real.sqlite')
    try:
        r=b.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        assert r['result']['document_consistent'],r['result']['blockers']
        assert not r['result']['ready'] and r['result']['payable_rows']==[]
        assert b.open_project('P-1')['boq']==[]
        # A genuine member edit through its existing service invalidates the saved basis.
        changed=deepcopy(inputs[0][1]);changed['geometry'].update(source_ref='اصلاح صریح دیتایل مصنوعی',approved_by='',status='needs_review')
        b.save_structural_member_draft('P-1',changed,expected_revision=1)
        assert b.get_structural_handoff_audit('P-1','AUDIT-1')['stale']
        snapshot=dump(b)
        with pytest.raises(RuntimeError):b.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=2)
        assert dump(b)==snapshot and b.open_project('P-1')['boq']==[]
    finally:b.store.close()


def test_forged_audit_result_cannot_enter_store_through_command(tmp_path):
    a,d,args=setup(tmp_path)
    try:
        save(a,d,args);p=a.open_project('P-1');old=deepcopy(p['structural_handoff_audits']['AUDIT-1'])
        fake=deepcopy(old);fake['revision']=2;fake['status']='checked_nonfinancial'
        fake['result']={'document_consistent':True,'ready':False,'commit_allowed':False,'payable_rows':[]}
        fake['result_digest']=_digest(fake['result']);p['structural_handoff_audits']['AUDIT-1']=fake
        p['structural_handoff_history'].append({'audit_id':'AUDIT-1','record':old})
        before=dump(a)
        with pytest.raises(ValueError):a.store.save('P-1',p,structural_handoff_command={'audit_id':'AUDIT-1','expected_revision':1})
        assert dump(a)==before
    finally:a.store.close()


def test_existing_valid_boq_price_and_historical_revisions_survive_audit(tmp_path):
    a,d,args=setup(tmp_path)
    try:
        p=a.open_project('P-1');p['boq']=[];a.store.save('P-1',p)
        a.add_takeoff('P-1','civil','drainage',length='2',source_id='SYNTHETIC:old-drain',unit_price='123.45')
        p=a.open_project('P-1');old_boq=deepcopy(p['boq']);old_rows=deepcopy(p['takeoffs']);old_revisions=deepcopy(a.store.revisions('P-1'))
        assert old_boq and old_rows
        d['project_sha256']=_digest(a.structural_handoff_basis('P-1'))
        path=__import__('pathlib').Path(args['source_path']);path.write_text(json.dumps(d),encoding='utf-8');args['source_sha256']=sha256(path.read_bytes()).hexdigest()
        save(a,d,args);r=a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        assert r['result']['blocked_historical_rows'] and r['result']['payable_rows']==[]
        current=a.open_project('P-1');assert current['boq']==old_boq and current['takeoffs']==old_rows
        assert a.store.revisions('P-1')[:len(old_revisions)]==old_revisions
        before=dump(a)
        with pytest.raises(ValueError):a.add_takeoff('P-1','civil','drainage',length='2',source_id='SYNTHETIC:old-drain')
        assert dump(a)==before
    finally:a.store.close()


@pytest.mark.parametrize('target',['source','sidecar'])
def test_file_changed_during_real_audit_is_rejected(tmp_path,monkeypatch,target):
    from core.takeoff import building_six_family_ownership_chat as engine
    a,d,args=setup(tmp_path);save(a,d,args);real=engine.audit
    def changing(*v,**kw):
        result=real(*v,**kw)
        path=args['source_path'] if target=='source' else next(iter(args['evidence_files'].values()))
        with open(path,'ab') as f:f.write(b' changed during audit')
        return result
    monkeypatch.setattr(engine,'audit',changing);before=dump(a)
    try:
        with pytest.raises((ValueError,RuntimeError)):a.run_structural_handoff_audit('P-1','AUDIT-1',expected_revision=1)
        assert dump(a)==before
    finally:a.store.close()
