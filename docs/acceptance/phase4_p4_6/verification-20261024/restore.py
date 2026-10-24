"""Verify a Drive-redownloaded archive, Git, SQLite and restored-source tests."""
import hashlib,json,os,shutil,sqlite3,subprocess,sys,zipfile
from pathlib import Path
archive=Path(sys.argv[1]).resolve();dest=Path(sys.argv[2]).resolve()
expected=sys.argv[3]
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
dest.mkdir(parents=True,exist_ok=False)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(dest)
m=json.loads((dest/'MANIFEST.json').read_text())
for name,r in m['files'].items():
    p=dest/name
    assert p.stat().st_size==r['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256'],name
repo=dest/'repo'
def command(args,**kw):return subprocess.run(args,check=True,**kw)
command(['git','clone',str(dest/'code.bundle'),str(repo)])
command(['git','checkout','--detach',m['head']],cwd=repo)
command(['git','fsck','--full'],cwd=repo)
assert subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip()==m['tree']
original=Path(m['scenario_original_path']);held=original.with_name(original.name+'-held-'+dest.name)
assert not held.exists()
original.rename(held)
checked=[]
try:
    # Recreate original evidence paths using only downloaded archive bytes.
    # Do not depend on symlink preservation across subprocess environments.
    shutil.copytree(dest/'scenario',original)
    sys.path.insert(0,str(repo))
    from core.platform.application import StructuralProApp
    app=StructuralProApp(dest/'scenario/prior/engineering/db')
    before=app.open_project('P');before_digest=app.store.current_digest('P')
    assert app.store.integrity_check()['ok']
    assert len(before['project_schedule_tasks'])==15
    assert [r['actual'] for r in before['progress_reports']]==['12.500000','45.000000','75.000000']
    assert app.project_schedule('P')['duration']==20
    assert app.site_dashboard('P',as_of='2026-05-02')['finance']['paid'] is None
    def walk(v):
        if isinstance(v,dict):
            if isinstance(v.get('path'),str) and isinstance(v.get('sha256'),str):
                p=Path(v['path'])
                assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],str(p)
                restored=dest/'scenario'/p.relative_to(original)
                assert hashlib.sha256(restored.read_bytes()).hexdigest()==v['sha256'],str(p)
                checked.append(str(p))
            for x in v.values():walk(x)
        elif isinstance(v,list):
            for x in v:walk(x)
    walk(before)
    assert app.store.current_digest('P')==before_digest
    app.store.close()
    db=dest/'scenario/prior/engineering/db/projects.db'
    with sqlite3.connect(db) as conn:
        assert conn.execute('pragma integrity_check').fetchone()[0]=='ok'
        assert conn.execute('pragma foreign_key_check').fetchall()==[]
        revision_count=conn.execute('select count(*) from revisions').fetchone()[0]
    env={**os.environ,'QT_QPA_PLATFORM':'offscreen','PYTHONPATH':str(repo)}
    tests=['tests/test_phase4_site_resources.py','tests/test_phase4_site_materials.py','tests/test_phase4_site_office.py','tests/test_phase4_site_workspace.py','tests/test_phase4_site_finance.py','tests/test_phase4_site_report_localization.py','tests/test_phase4_report_chart_print.py']
    with (dest/'restored-tests.log').open('w') as log:
        command([sys.executable,'scripts/run_offline_tests.py','-q',*tests,'--junitxml='+str(dest/'restored-tests.xml')],cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT)
finally:
    if original.exists():original.rename(dest/'source-path-replay')
    held.rename(original)
receipt={'status':'PASS','archive_sha256':expected,'manifest_files':len(m['files']),'head':m['head'],'tree':m['tree'],'git_fsck':True,'sqlite_integrity':'ok','sqlite_foreign_key_check':True,'revision_count':revision_count,'source_proofs_checked':len(checked),'source_paths_recreated_only_from_downloaded_archive':True,'restored_tests':'restored-tests.xml','original_source_hidden_during_check':True,'windows_office':'NOT VERIFIED'}
(dest/'restore-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
print(json.dumps(receipt))
