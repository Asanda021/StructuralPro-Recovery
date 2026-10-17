"""User-controlled manual deletion is CAS-protected, audited and statement-safe."""
import pytest
from core.platform.application import StructuralProApp

def _two(tmp_path):
    app=StructuralProApp(tmp_path)
    app.create_project('آزمایش حذف دستی','P')
    for sid,length in (('synthetic:floor:1',2),('synthetic:floor:2',3)):
        app.add_takeoff('P','building','slab_volume',source_id=sid,system='L1',
                        length=length,width=2,thickness=.1,count=1)
    return app

def test_deletion_retains_other_boq_and_tombstone_after_sqlite_reopen(tmp_path):
    app=_two(tmp_path)
    report=app.delete_takeoff('P','synthetic:floor:1',expected_revision=1)
    assert report['status']=='retired'
    project=app.open_project('P')
    assert len(project['takeoffs'])==1 and len(project['boq'])==1
    assert project['takeoffs'][0]['source_id']=='synthetic:floor:2'
    assert project['deleted_takeoff_sources']==['synthetic:floor:1']
    assert project['takeoff_revision_history'][-1]['event']=='deleted'
    app.store.close()
    reread=StructuralProApp(tmp_path)
    assert reread.open_project('P')['deleted_takeoff_sources']==['synthetic:floor:1']
    with pytest.raises(ValueError,match='حذف‌شده'):
        reread.add_takeoff('P','building','slab_volume',source_id='synthetic:floor:1',
                           system='L1',length=4,width=3,thickness=.1,count=1)
    reread.store.close()

def test_invalid_revision_or_unknown_id_causes_no_write(tmp_path):
    app=_two(tmp_path)
    before=app.open_project('P')
    for expected in (0,2,True,1.5):
        with pytest.raises((RuntimeError,ValueError)):
            app.delete_takeoff('P','synthetic:floor:1',expected_revision=expected)
        assert app.open_project('P')==before
    with pytest.raises(KeyError):
        app.delete_takeoff('P','missing',expected_revision=1)
    assert app.open_project('P')==before
    app.store.close()

def test_issued_statement_cannot_be_bypassed_by_manual_delete(tmp_path):
    app=_two(tmp_path)
    project=app.open_project('P')
    project['statement_periods']=[{'number':1,'lines':[], 'payable_current':100}]
    app.store.save('P',project)
    before=app.open_project('P')
    with pytest.raises(ValueError,match='اصلاحیه'):
        app.delete_takeoff('P','synthetic:floor:1',expected_revision=1)
    assert app.open_project('P')==before
    app.store.close()

def test_deletion_never_uses_generic_path_for_reviewed_or_drawing_sources(tmp_path):
    app=_two(tmp_path)
    project=app.open_project('P')
    project['takeoffs'][0]['domain']='drawing'
    project['takeoffs'][0]['drawing_session_id']='S1'
    app.store.save('P',project)
    before=app.open_project('P')
    with pytest.raises(ValueError,match='تخصصی'):
        app.delete_takeoff('P','synthetic:floor:1',expected_revision=1)
    assert app.open_project('P')==before
    app.store.close()
