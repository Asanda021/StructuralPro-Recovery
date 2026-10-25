"""Finish round two using its already closed data; do not rerun the scenario."""
import hashlib,json,os,sqlite3,importlib.util
from pathlib import Path
from contextlib import closing
HERE=Path(__file__).resolve().parent

def test_closed_round_two_publication():
    root=Path('/tmp/sp-decision-round2-scenario-20261025')
    db=root/'prior/engineering/db/projects.db'
    os.environ.update(SP_SQLITE_OUT='/tmp/sp-decision-publication-observer-20261025',SP_SQLITE_ROOT=str(root),SP_SQLITE_MODE='audited')
    spec=importlib.util.spec_from_file_location('publication_observer',HERE.parent/'closure-20261025/sqlite_worker.py');worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)
    from core.recovery.recovery import require_project_history_consistency
    initial=worker.identity(db);assert initial['fds']==[]
    assert all(not Path(str(db)+s).exists() for s in ['-journal','-wal','-shm'])
    check=worker.fresh(db);assert check['integrity']==[('ok',)] and check['revision_count']==326
    with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as c:require_project_history_consistency(c)
    assert worker.identity(db)['fds']==[]
    before=db.stat();raw=db.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    publish=HERE/'closed-snapshot';publish.mkdir(exist_ok=False);stage=publish/'.projects.db.part';dest=publish/'projects.db'
    with stage.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    assert hashlib.sha256(stage.read_bytes()).hexdigest()==sha
    os.link(stage,dest);stage.unlink()
    with closing(sqlite3.connect(dest.as_uri()+'?mode=ro',uri=True)) as c:
        assert c.execute('pragma integrity_check').fetchall()==[('ok',)]
        assert c.execute('pragma foreign_key_check').fetchall()==[]
        require_project_history_consistency(c)
    from core.platform.application import StructuralProApp
    app=StructuralProApp(publish)
    try:
        p=app.open_project('P');assert p['_meta']['version']==326
        assert [x['actual'] for x in p['progress_reports']]==['12.500000','45.000000','75.000000']
        assert len(p['project_schedule_tasks'])==15 and len(p['schedule_baselines'])==1
        assert app.project_schedule('P')['duration']==20
        last=app.project_progress('P',as_of=p['progress_reports'][-1]['date'])
        assert [last[k] for k in ['planned','planned_current','actual','variance']]==['100.000000','92.500000','75.000000','-25.000000']
        proofs=[]
        def walk(v):
            if isinstance(v,dict):
                if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
                    f=Path(v['path']);assert f.is_relative_to(root) and f.is_file();assert hashlib.sha256(f.read_bytes()).hexdigest()==v['sha256'];proofs.append(str(f))
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(p);assert len(proofs)==270
    finally:app.store.close()
    after=db.stat();assert (before.st_dev,before.st_ino,before.st_size)==(after.st_dev,after.st_ino,after.st_size)
    assert hashlib.sha256(db.read_bytes()).hexdigest()==hashlib.sha256(dest.read_bytes()).hexdigest()==sha
    assert worker.identity(db)['fds']==[] and worker.identity(dest)['fds']==[]
    events=[json.loads(x) for x in Path('/tmp/sp-decision-round2-20261025/events.jsonl').read_text().splitlines()]
    assert not any(x.get('moved') for x in events)
    r={'status':'CLOSED PUBLICATION PASS; NOT ROOT CAUSE FIX','source':str(db),'destination':str(dest),'sha256_source_and_destination':sha,'source_identity_before':initial,'source_identity_after':worker.identity(db),'published_identity':worker.identity(dest),'revisions':326,'proof_occurrences':len(proofs),'distinct_proofs':len(set(proofs)),'active_tail_equal':True,'all_history_valid':True,'integrity':'ok','foreign_key_check':[],'scenario_reexecuted':False,'round2_sql_counts':{name:sum(x['event']==name for x in events) for name in ['SQL_BEGIN','SQL_INSERT','SQL_COMMIT','CLOSE_BEGIN','CLOSE_RETURN','CONNECT_OR_REOPEN']},'round2_path_fd_mismatches':0,'replacement_actor':'UNRESOLVED','historical_corruption':'UNRESOLVED'}
    (HERE/'closed-publication.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));worker.log.close()
