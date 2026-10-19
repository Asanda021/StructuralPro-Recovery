"""Actual SQLite/CAS around pure audits; not specialist geometry or a new ledger."""
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp

@pytest.mark.parametrize('kind',['support','six'])
def test_pinned_raw_snapshot_reopens_cas_and_history_stay_guarded(tmp_path,kind):
    if kind=='support':
        from test_phase1_steel_stair_support_crosswalk_chat import example,run
        doc,stair,p,files=example()
        def audit(current):return run(doc,stair,current,files)
        success='support_evidence_checked'
    else:
        from test_phase1_six_family_ownership_chat import sample
        from core.takeoff.building_six_family_ownership_chat import audit as six,_digest
        doc,p,files=sample()
        def audit(current):return six(doc,current,documents=files)
        success='document_consistent'
    pid=p['id'];a=StructuralProApp(tmp_path/'db');a.create_project('Snapshot مصنوعی، بدون پذیرش مهندسی',pid)
    loaded=a.open_project(pid);loaded.update(deepcopy(p));a.store.save(pid,loaded)
    before=deepcopy(a.open_project(pid))
    if kind=='six':doc['project_sha256']=_digest(before)
    dumped='\n'.join(a.store.db.iterdump());out=audit(before)
    assert out[success] is True and out['ready'] is False and out['commit_allowed'] is False and out['payable_rows']==[]
    assert a.open_project(pid)==before and '\n'.join(a.store.db.iterdump())==dumped
    b=StructuralProApp(tmp_path/'db')
    try:
        reopened=b.open_project(pid);assert reopened==before
        assert audit(reopened)[success] is True
        first=next(iter(reopened['reviewed_structural_members'].values()));first['revision']+=1
        b.store.save(pid,reopened)
        with pytest.raises(RuntimeError):a.store.save(pid,before)
        current=b.open_project(pid);invalid=audit(current)
        assert invalid[success] is False and invalid['payable_rows']==[]
        assert current['boq']==before['boq'] and current['takeoffs']==before['takeoffs']
        assert b.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert b.store.db.execute('pragma foreign_key_check').fetchall()==[]
    finally:b.store.close();a.store.close()
