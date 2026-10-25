from pathlib import Path
import json,sqlite3,hashlib,os

def test_original_probe_in_tmp():
    from scripts.phase4_site_operations_probe import run
    root=Path('/tmp/structuralpro-final-20261025');result=run(root)
    assert result['immutable_originals'] and result['reopen_equal']
    p=root/'prior/engineering/db/projects.db'
    with sqlite3.connect(p.as_uri()+'?mode=ro',uri=True) as c:
        r={'integrity':c.execute('pragma integrity_check').fetchall(),'journal_mode':c.execute('pragma journal_mode').fetchone()[0],'active':c.execute('select id,version from projects').fetchall(),'revisions':c.execute('select count(*) from revisions').fetchone()[0],'identical':c.execute('select p.payload=r.payload from projects p join revisions r on p.id=r.project_id and p.version=r.version').fetchone()[0]}
    r.update(path=str(p),inode=p.stat().st_ino,device=p.stat().st_dev,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),synthetic_origin='Fresh run of unchanged repository probes; not prior missing documents')
    (root/'persistence.json').write_text(json.dumps(r,indent=2))
    Path('docs/acceptance/phase4_p4_6/work-20261025/tmp-persistence.json').write_text(json.dumps(r,indent=2))
