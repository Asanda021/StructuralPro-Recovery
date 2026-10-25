from copy import deepcopy
import hashlib
import pytest
from core.platform.application import StructuralProApp
from test_phase4_structure import structure,activity,cmd

@pytest.fixture
def setup(tmp_path):
    a=StructuralProApp(tmp_path);a.create_project('آزمایش','P');structure(a);activity(a)
    cmd(a,'schedule_calendar',start='2026-10-26',calendar={'weekdays':[0,1,2,3,4],'holidays':['2026-10-28']})
    cmd(a,'schedule_activity',id='A',duration=3,not_before=None,relationships=[])
    f=tmp_path/'source.txt';f.write_text('Explicit test resource evidence')
    proof={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'reference':'TEST ONLY'}
    def run(op,actor='maker',**data):
        return a.site_command('P',op,actor=actor,reason='آزمون مستند',expected_version=a.open_project('P')['_meta']['version'],**data)
    run('policy',actor='owner',owner='owner',establish_owner=True,source=proof,permissions={k:['maker','reviewer','approver','owner'] for k in ['create','review','approve','issue','adjust','finance']})
    yield a,run,proof
    a.store.close()

def resource(run,proof,id='C',kind='crew',capacity='1'):
    run('resource_create',id=id,name='اکیپ آزمایشی',kind=kind,capacity=capacity,unit='crew',discipline_id='S',subcontractor='نمونه',source=proof)
    run('resource_review',actor='reviewer',id=id);run('resource_approve',actor='approver',id=id)
    run('availability',id='AV-'+id,resource_id=id,start='2026-10-26',end='2026-11-20',state='present',capacity=capacity,confirmed=True,source=proof)

def assign(run,proof,id='AS',activity_id='A',resource_id='C',start='2026-10-26',end='2026-10-29'):
    run('assign',id=id,activity_id=activity_id,resource_id=resource_id,start=start,end=end,allocation='1',source=proof)
    run('assignment_review',actor='reviewer',id=id)
    return run('assignment_approve',actor='approver',id=id)

def test_api_capacity_overlap_unknown_and_calendar(setup):
    a,run,proof=setup;resource(run,proof)
    before=deepcopy(a.open_project('P'))
    run('requirements',id='REQ',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof)
    assign(run,proof)
    r=a.site_lookahead('P',start='2026-10-26',days=7)
    assert r['end']=='2026-11-01' and r['activities'][0]['status']=='ready'
    assert r['activities'][0]['work_dates']==['2026-10-26','2026-10-27','2026-10-29']
    with pytest.raises(ValueError):assign(run,proof,id='DUP')
    run('resource_event',id='ABS',resource_id='C',start='2026-10-27',end='2026-10-27',state='absent',source=proof)
    assert a.site_lookahead('P',start='2026-10-26',days=14)['activities'][0]['status']=='resource_conflict'
    assert before['boq']==a.open_project('P')['boq']

def test_unknown_no_approval_raw_bypass_and_cas(setup):
    a,run,proof=setup
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']=='insufficient_information'
    p=a.open_project('P');old=p['_meta']['version']
    with pytest.raises(ValueError):run('resource_create',id='X',name='ناقص',kind='crew',capacity=True,unit='crew',discipline_id='S',subcontractor='x',source=proof)
    assert a.open_project('P')==p
    resource(run,proof)
    with pytest.raises(RuntimeError):a.site_command('P','availability',actor='maker',reason='x',expected_version=old)
    with pytest.raises(ValueError):a.site_command('P','availability',actor='maker',reason='x',expected_version=True)
    p=a.open_project('P');p['project_resources'][0]['capacity']='20'
    with pytest.raises(ValueError):a.store.save('P',p)
    with pytest.raises(ValueError):run('resource_create',actor='intruder')

def test_parallel_floors_and_reopen(setup,tmp_path):
    a,run,proof=setup;resource(run,proof);resource(run,proof,id='C2')
    cmd(a,'activity',id='B',title='دیوار',code='B',wbs_id='W1',floor_ids=['F3'],zone_ids=[],discipline_id='S',member_ids=[],unit='m3',responsible='مسئول',status='todo',measurement={'kind':'none'})
    cmd(a,'schedule_activity',id='B',duration=3,not_before=None,relationships=[])
    baseline=cmd(a,'schedule_baseline',reference='BASE',approved_by='owner')
    assign(run,proof);assign(run,proof,id='AS2',activity_id='B',resource_id='C2')
    assert len(a.open_project('P')['resource_assignments'])==2
    cmd(a,'schedule_activity',id='B',duration=4,not_before=None,relationships=[])
    assert a.open_project('P')['schedule_baselines'][0]==baseline
    p=a.open_project('P');a.store.close();b=StructuralProApp(tmp_path)
    try:assert b.open_project('P')==p
    finally:b.store.close()

@pytest.mark.parametrize('days',[0,True,15,-1])
def test_invalid_horizon(setup,days):
    a,_,_=setup
    with pytest.raises(ValueError):a.site_lookahead('P',start='2026-10-26',days=days)

def test_missing_equipment_predecessor_and_duration(setup):
    a,run,proof=setup;resource(run,proof,kind='equipment')
    run('requirements',id='R',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof)
    assert a.site_lookahead('P',start='2026-10-26',end='2026-10-29')['activities'][0]['status']=='insufficient_information'
    cmd(a,'activity',id='B',title='بدون مدت',code='B',wbs_id='W1',floor_ids=['F3'],zone_ids=[],discipline_id='S',member_ids=[],unit='m3',responsible='مسئول',status='todo',measurement={'kind':'none'})
    assert all(x['start'] is None for x in a.site_lookahead('P',start='2026-10-26',days=7)['activities'])

def test_event_release_keeps_history_and_restores_availability(setup):
    a,run,proof=setup;resource(run,proof)
    run('requirements',id='R',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof);assign(run,proof)
    event=run('resource_event',id='STOP',resource_id='C',start='2026-10-26',end='2026-10-29',state='stopped',source=proof)
    run('resource_event',id='FIX',resource_id='C',start='2026-10-27',end='2026-10-29',state='released',reference_id='STOP',source=proof)
    from core.projects.site_resources import capacity
    p=a.open_project('P');r=p['project_resources'][0]
    assert capacity(p,r,'2026-10-26')==0
    assert capacity(p,r,'2026-10-27')==1
    assert p['resource_events'][0]==event

def test_changed_source_and_schedule_block_readiness(setup):
    a,run,proof=setup;resource(run,proof)
    run('requirements',id='R',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof);assign(run,proof)
    cmd(a,'schedule_activity',id='A',duration=2,not_before=None,relationships=[])
    run('requirements',id='R2',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof)
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']!='ready'

def test_resolved_and_future_obstacles_do_not_block_historical_readiness(setup):
    a,run,proof=setup;resource(run,proof)
    run('requirements',id='R',activity_id='A',resources=[{'resource_id':'C','quantity':'1'}],materials=[],source=proof);assign(run,proof)
    b=run('obstacle_create',activity_id='A',title='مانع',owner='maker',date='2026-10-26',due_date='2026-10-26',location='طبقه یک',source=proof)
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']=='human_decision'
    run('obstacle_resolve',id=b['id'],date='2026-10-26',resolution='رفع شد',source=proof)
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']=='ready'
    run('obstacle_create',activity_id='A',title='مانع آینده',owner='maker',date='2026-11-01',due_date='2026-11-01',location='طبقه یک',source=proof)
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']=='ready'
    from pathlib import Path
    Path(proof['path']).write_text('changed')
    assert a.site_lookahead('P',start='2026-10-26',days=7)['activities'][0]['status']!='ready'

def test_attendance_correction_adds_record_without_overwrite(setup):
    a,run,proof=setup;resource(run,proof)
    original=deepcopy(a.open_project('P')['resource_availability'][0])
    run('availability',id='CORRECTED',resource_id='C',start=original['start'],end=original['end'],state='absent',capacity='0',confirmed=True,source=proof,supersedes=original['id'])
    p=a.open_project('P');assert p['resource_availability'][0]==original
    assert p['resource_availability'][1]['supersedes']==original['id']
    from core.projects.site_resources import capacity
    assert capacity(p,p['project_resources'][0],'2026-10-26')==0
