"""Two-round QA evidence only. No product monkeypatch beyond existing observer."""
import os,sys,json,time,traceback,importlib.util,hashlib
from pathlib import Path
from contextlib import closing
HERE=Path(__file__).resolve().parent
ROUND=int(os.environ['SP_FINAL_ROUND'])
ROOT=Path(os.environ['SP_SQLITE_ROOT']).resolve()
OUT=Path(os.environ['SP_SQLITE_OUT']).resolve()
mutations=[]
def audit(event,args):
    if event in {'os.remove','os.rename','os.rmdir','shutil.rmtree','shutil.move','shutil.copyfile','os.link','os.symlink'}:
        values=[str(x) for x in args if isinstance(x,(str,bytes,Path))]
        if any(str(ROOT) in x or (x.startswith('/') and str(ROOT).startswith(x.rstrip('/')+'/')) for x in values):
            mutations.append({'wall_ns':time.time_ns(),'event':event,'args':values,'stack':traceback.format_stack(limit=10)})
sys.addaudithook(audit)
spec=importlib.util.spec_from_file_location('existing_observer',HERE.parent/'closure-20261025/sqlite_worker.py')
worker=importlib.util.module_from_spec(spec);spec.loader.exec_module(worker)

def test_targeted_round():
    started=time.time_ns()
    try:
        worker.test_independent_original_scenario()
        events=[json.loads(x) for x in (OUT/'events.jsonl').read_text().splitlines()]
        relevant=[x for x in events if x.get('path','').endswith('/projects.db')]
        moved=[x for x in relevant if x.get('moved')]
        checks=[x['fresh'] for x in events if 'fresh' in x and 'revision_count' in x['fresh']]
        assert not moved
        assert checks and all(x.get('integrity')==[['ok']] and all(y[2]==1 for y in x['active_tail']) for x in checks)
        db=ROOT/'prior/engineering/db/projects.db'
        current=worker.fresh(db)
        assert current['revision_count']==326 and current['integrity']==[('ok',)]
        from core.recovery.recovery import require_project_history_consistency
        with closing(worker.CONNECT(db.as_uri()+'?mode=ro',uri=True)) as c:require_project_history_consistency(c)
        result={'round':ROUND,'start_ns':started,'end_ns':time.time_ns(),'root':str(ROOT),'path_fd_mismatches':len(moved),'python_file_mutations':mutations,'fresh':current,'sql_counts':{name:sum(x['event']==name for x in events) for name in ['SQL_BEGIN','SQL_INSERT','SQL_COMMIT','CLOSE_BEGIN','CLOSE_RETURN','CONNECT_OR_REOPEN']},'scope':'QA only; no causal attribution from a successful rerun'}
        if ROUND==2:
            # Prove no source SQLite descriptor is live BEFORE copying closed bytes.
            live=worker.identity(db)['fds'];assert not live,live
            assert all(not Path(str(db)+s).exists() for s in ['-journal','-wal','-shm'])
            before=db.stat();raw=db.read_bytes();sha=hashlib.sha256(raw).hexdigest()
            publish=HERE/'closed-snapshot';publish.mkdir(exist_ok=False)
            stage=publish/'.projects.db.part';dest=publish/'projects.db'
            with stage.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
            assert hashlib.sha256(stage.read_bytes()).hexdigest()==sha
            os.link(stage,dest);stage.unlink()
            after=db.stat();assert (before.st_dev,before.st_ino,before.st_size)==(after.st_dev,after.st_ino,after.st_size)
            assert hashlib.sha256(db.read_bytes()).hexdigest()==hashlib.sha256(dest.read_bytes()).hexdigest()==sha
            with closing(worker.CONNECT(dest.as_uri()+'?mode=ro',uri=True)) as c:
                assert c.execute('pragma integrity_check').fetchall()==[('ok',)]
                require_project_history_consistency(c)
            from core.platform.application import StructuralProApp
            app=StructuralProApp(publish);p=app.open_project('P');assert p['_meta']['version']==326
            assert [x['actual'] for x in p['progress_reports']]==['12.500000','45.000000','75.000000']
            assert app.project_schedule('P')['duration']==20
            app.store.close()
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==sha
            result['closed_publication']={'source_live_fds':live,'source_sha256':sha,'published_sha256':sha,'history':'all revisions validated','reopen_version':326,'historical_progress':['12.500000','45.000000','75.000000'],'destination':str(dest),'status':'PASS; operational isolation only, actor not established'}
        (OUT/'round-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        (OUT/'python-mutations.json').write_text(json.dumps(mutations,indent=2))
