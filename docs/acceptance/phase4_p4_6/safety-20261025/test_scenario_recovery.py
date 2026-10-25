"""Validate real retained five-floor data on changed persistence, without rewriting it."""
from pathlib import Path
import hashlib,json
from core.projects.store import ProjectStore
from core.recovery.recovery import backup_database,require_project_history_consistency

def test_last_acknowledged_five_floor_recovery(tmp_path):
    source=Path('/tmp/sp-decision-round2-scenario-20261025/prior/engineering/db/projects.db')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    work=tmp_path/'work.db';backup_database(source,work)
    s=ProjectStore(work);p=s.get('P');assert p['_meta']['version']==326
    assert len(p['project_schedule_tasks'])==15
    assert [r['actual'] for r in p['progress_reports']]==['12.500000','45.000000','75.000000']
    proof=[]
    def walk(x):
        if isinstance(x,dict):
            if isinstance(x.get('path'),str) and isinstance(x.get('sha256'),str):
                f=Path(x['path']);assert hashlib.sha256(f.read_bytes()).hexdigest()==x['sha256'];proof.append(str(f))
            for v in x.values():walk(v)
        elif isinstance(x,list):
            for v in x:walk(v)
    walk(p);assert len(proof)==270
    payload={k:v for k,v in p.items() if k!='_meta'}
    ack=s.save('P',p);assert ack['version']==327
    backup=tmp_path/'ack327.db';s.backup(backup);s.close()
    restored=tmp_path/'restored.db';backup_database(backup,restored)
    r=ProjectStore(restored)
    try:
        result=r.get('P');assert result['_meta']['version']==327
        assert {k:v for k,v in result.items() if k!='_meta'}==payload
        require_project_history_consistency(r.db);assert r.integrity_check()['ok']
    finally:r.close()
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    Path('docs/acceptance/phase4_p4_6/safety-20261025/scenario-recovery.json').write_text(json.dumps({'source_unchanged_sha256':before,'source_revision':326,'last_acknowledged_and_restored':327,'all_payload_fields_equal':True,'source_proofs':len(proof),'historical_progress':['12.5','45','75'],'integrity':'ok'}))
