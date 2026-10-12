from core.platform.migrations import MigrationRegistry,MigrationStep,migrate_project
def test_sequential_migration_is_deterministic_and_non_mutating():
 def m01(d): d["name"]=d.pop("title",""); d["schema"]=1; return d
 def m12(d): d["metadata"]={"migrated":True}; d["schema"]=2; return d
 r=MigrationRegistry([MigrationStep(0,1,m01),MigrationStep(1,2,m12)])
 src={"title":"A","schema":0}; out=migrate_project(src,0,2,r)
 assert src=={"title":"A","schema":0} and out=={"name":"A","schema":2,"metadata":{"migrated":True}}
def test_missing_path_fails_closed():
 r=MigrationRegistry([MigrationStep(0,1,lambda d:d)])
 try:r.migrate({},0,2)
 except ValueError as e: assert "missing migration" in str(e)
 else: assert False
def test_downgrade_rejected():
 try:MigrationRegistry().migrate({},2,1)
 except ValueError:pass
 else:assert False
def test_bad_migration_result_rejected():
 r=MigrationRegistry([MigrationStep(0,1,lambda d:[])])
 try:r.migrate({},0,1)
 except ValueError:pass
 else:assert False
