from pathlib import Path
import json,hashlib,sqlite3

def test_manual_rescue_of_new_failed_copy():
 from scripts.phase4_sqlite_rescue import rescue
 from core.projects.store import ProjectStore
 source=Path('/workspace/scratch/5ff2acae0199/site-final-20261025/prior/engineering/db/projects.db');before=hashlib.sha256(source.read_bytes()).hexdigest()
 target=Path('/tmp/structuralpro-diagnostic-rescue-251-20261025.db')
 r=rescue(source,target);assert hashlib.sha256(source.read_bytes()).hexdigest()==before
 s=ProjectStore(target);assert s.get('P')['_meta']['version']==251;assert s.integrity_check()['ok'];s.close()
 Path('docs/acceptance/phase4_p4_6/work-20261025/rescue-new-failure.json').write_text(json.dumps(r,indent=2))
