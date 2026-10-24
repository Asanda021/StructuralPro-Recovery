"""Create a source/evidence backup; no release binaries or installed runtimes."""
import hashlib,json,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
repo=Path(sys.argv[1]).resolve();scenario=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve()
def git(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
assert not git('status','--porcelain'), 'Commit reviewable evidence before freezing the backup'
qa=json.loads((repo/'docs/acceptance/phase4_p4_6/verification-20261024/final-state.json').read_text())
with tempfile.TemporaryDirectory(prefix='phase4-backup-') as tmp:
    root=Path(tmp)
    subprocess.run(['git','bundle','create',str(root/'code.bundle'),'HEAD',git('symbolic-ref','HEAD')],cwd=repo,check=True)
    shutil.copytree(scenario,root/'scenario')
    shutil.copytree(repo/'docs/acceptance/phase4_p4_6/verification-20261024',root/'evidence')
    if len(sys.argv)>4:
        diagnostic=root/'diagnostics';diagnostic.mkdir()
        shutil.copy2(Path(sys.argv[4]),diagnostic/'FAILED-projects.db')
        (diagnostic/'README.txt').write_text('Known corrupted standalone-probe database, preserved only for investigation. NOT the restoration source. The valid scenario database is in scenario/.')
    m={'scope':'Phase4 priorities4-6 only; synthetic fixture; not Windows/Office or engineering acceptance',
       'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),
       'executable_head':qa['tested_head'],
       'executable_tree':qa['tested_tree'],
       'scenario_original_path':str(scenario),'files':{}}
    for p in sorted(root.rglob('*')):
        if p.is_file():m['files'][str(p.relative_to(root))]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    (root/'MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file():z.write(p,str(p.relative_to(root)))
    receipt={'file':out.name,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'head':m['head'],'tree':m['tree'],'manifest_files':len(m['files'])}
    out.with_suffix('.sha256.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
