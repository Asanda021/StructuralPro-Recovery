from pathlib import Path
import hashlib,json,pytest

def test_new_dbmoved_corrupt_snapshot_is_rejected_unchanged():
 from core.projects.store import ProjectStore
 from core.recovery.recovery import backup_database,RecoveryError
 p=Path('docs/acceptance/phase4_p4_6/closure-20261025/sqlite-runs-frozen/audited-workspace/failure-1792903116210965117/projects.db')
 before=hashlib.sha256(p.read_bytes()).hexdigest()
 assert before=='b5b0e48414dee5205de34a0cd6403fd5d8f9cd819a9a8b87c3e2f7c73eb57e00'
 with pytest.raises(RuntimeError,match='integrity'):ProjectStore(p)
 target=Path('/tmp/REJECTED-closure-273.db');assert not target.exists()
 with pytest.raises(RecoveryError,match='integrity'):backup_database(p,target)
 assert not target.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==before
 Path('docs/acceptance/phase4_p4_6/closure-20261025/new-snapshot-guards.json').write_text(json.dumps({'sha256_unchanged':before,'startup':'REJECTED','backup':'REJECTED','output_created':False},indent=2))
