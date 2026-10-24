"""Create a source/evidence backup; no release binaries or installed runtimes."""
import hashlib,json,shutil,subprocess,sys,tempfile,zipfile
from pathlib import Path
repo=Path(sys.argv[1]).resolve();scenario=Path(sys.argv[2]).resolve();out=Path(sys.argv[3]).resolve()
def git(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
assert not git('status','--porcelain'), 'Commit reviewable evidence before freezing the backup'
with tempfile.TemporaryDirectory(prefix='phase4-backup-') as tmp:
    root=Path(tmp)
    subprocess.run(['git','bundle','create',str(root/'code.bundle'),'--all'],cwd=repo,check=True)
    shutil.copytree(scenario,root/'scenario')
    shutil.copytree(repo/'docs/acceptance/phase4_p4_6/verification-20261024',root/'evidence')
    m={'scope':'Phase4 priorities4-6 only; synthetic fixture; not Windows/Office or engineering acceptance',
       'head':git('rev-parse','HEAD'),'tree':git('rev-parse','HEAD^{tree}'),
       'executable_head':'738221881a3180a7aa1f5ec163691c953b4a29a6',
       'executable_tree':'77b256c5ec1d5fed49237d63ad48f9f5d735d2d4',
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
