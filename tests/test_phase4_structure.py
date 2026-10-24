from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp

@pytest.fixture
def app(tmp_path):
    a=StructuralProApp(tmp_path);a.create_project('آزمون پنج‌طبقه','P');yield a;a.store.close()

def cmd(a,op,**data):
    return a.project_control_command('P',op,actor='planner',reason='آزمون صریح',expected_version=a.open_project('P')['_meta']['version'],**data)

def structure(a):
    cmd(a,'building',id='B',title='بلوک یک')
    for i in range(1,6):cmd(a,'floor',id=f'F{i}',title=f'طبقه {i}',building_id='B',kind='positive',level=i,height='3.2')
    cmd(a,'zone',id='Z',title='جبهه شرق',floor_ids=['F1','F2'])
    cmd(a,'discipline',id='S',title='سازه')
    cmd(a,'wbs',id='W',title='اجرای ساختمان',parent_id=None,code='01')
    cmd(a,'wbs',id='W1',title='اسکلت',parent_id='W',code='01.01')

def activity(a,id='A',**kw):
    return cmd(a,'activity',id=id,title='بتن‌ریزی',code=id,wbs_id='W1',floor_ids=['F1','F2'],zone_ids=['Z'],discipline_id='S',member_ids=[],unit='m3',responsible='مسئول کارگاه',status='todo',measurement={'kind':'none'},**kw)

def test_structure_multifloor_reopen_and_move(app,tmp_path):
    assert hasattr(app,'project_control_command'),'project controls API is absent'
    structure(app);activity(app)
    cmd(app,'wbs',id='W2',title='بخش دوم',parent_id='W',code='01.02')
    cmd(app,'move_activity',id='A',wbs_id='W2')
    p=app.open_project('P');assert len(p['project_schedule_tasks'])==1
    assert p['project_schedule_tasks'][0]['floor_ids']==['F1','F2']
    assert p['project_schedule_tasks'][0]['wbs_id']=='W2'
    assert [x['sequence'] for x in p['project_control_history']]==list(range(1,14))
    app.store.close();b=StructuralProApp(tmp_path)
    try:assert b.open_project('P')==p
    finally:b.store.close()

@pytest.mark.parametrize('op,data',[
 ('floor',dict(id='X',title='طبقه',building_id='missing',kind='positive',level=1,height='3')),
 ('floor',dict(id='X',title='طبقه',building_id='B',kind='positive',level=True,height='3')),
 ('wbs',dict(id='W',title='دور',parent_id='W1',code='01')),
 ('activity',dict(id='A',title='ناقص')),
 ('zone',dict(id='Z2',title='زون',floor_ids=['unknown'])),
])
def test_invalid_structure_atomic(app,op,data):
    assert hasattr(app,'project_control_command'),'project controls API is absent'
    structure(app);before=deepcopy(app.open_project('P'))
    with pytest.raises(ValueError):cmd(app,op,**data)
    assert app.open_project('P')==before

def test_raw_history_write_and_stale_cas_blocked(app):
    assert hasattr(app,'project_control_command'),'project controls API is absent'
    structure(app);p=app.open_project('P');old=p['_meta']['version'];activity(app)
    with pytest.raises(RuntimeError):app.project_control_command('P','building',actor='x',reason='y',expected_version=old,id='B2',title='دیگر')
    p=app.open_project('P');p['project_control_history'].clear()
    with pytest.raises(ValueError):app.store.save('P',p)

def test_boq_ownership_units_and_stale_basis(app):
    assert hasattr(app,'project_control_command'),'project controls API is absent'
    structure(app);p=app.open_project('P')
    p['takeoffs']=[{'source_id':'T1','quantities':[{'code':'C','unit':'m3','amount':'10.25','title':'بتن','formula':'explicit synthetic fixture'}]}]
    p['boq']=[dict(source_ids=['T1'],source_id='T1',item_code='C',description='بتن',quantity='10.25',unit='m3',status='active')];app.store.save('P',p)
    cmd(app,'activity',id='A',title='بتن',code='A',wbs_id='W1',floor_ids=['F1'],zone_ids=[],discipline_id='S',member_ids=[],unit='m3',responsible='مسئول',status='todo',measurement={'kind':'boq','source_ids':['T1']})
    p=app.open_project('P');a=p['project_schedule_tasks'][0];assert a['measurement']['total']=='10.25'
    args={k:v for k,v in a.items() if k not in ['id','measurement']};args['code']='B'
    with pytest.raises(ValueError):cmd(app,'activity',id='B',measurement={'kind':'boq','source_ids':['T1']},**args)
    p['boq'][0]['quantity']='11';app.store.save('P',p)
    snap=app.project_controls('P');assert snap['activities'][0]['basis_stale'] is True
    assert app.open_project('P')['project_schedule_tasks'][0]['measurement']['total']=='10.25'

def test_floor_edit_preserves_existing_metadata_and_identity(app):
    p=app.open_project('P');p['floors']=[{'id':'F1','name':'قدیمی','drawing_refs':['D1'],'engineering_note':'حفظ شود'}];app.store.save('P',p)
    cmd(app,'building',id='B',title='بلوک')
    cmd(app,'floor',id='F1',title='طبقه یک',building_id='B',kind='positive',level=1,height='3.2')
    f=app.open_project('P')['floors'][0];assert f['drawing_refs']==['D1'] and f['engineering_note']=='حفظ شود'

def test_subactivity_parent_identity_and_cycle(app):
    structure(app);activity(app)
    args=dict(title='زیر فعالیت',code='SUB',wbs_id='W1',floor_ids=['F1'],zone_ids=[],member_ids=[],discipline_id='S',unit='m3',responsible='مسئول',status='todo',measurement={'kind':'none'})
    cmd(app,'activity',id='SUB',parent_activity_id='A',**args)
    assert app.open_project('P')['project_schedule_tasks'][1]['parent_activity_id']=='A'
    original=app.open_project('P')['project_schedule_tasks'][0]
    with pytest.raises(ValueError):cmd(app,'activity',parent_activity_id='SUB',**{k:v for k,v in original.items() if k not in ['planned_start','planned_end','parent_activity_id']})
