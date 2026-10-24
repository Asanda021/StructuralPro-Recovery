from copy import deepcopy
import hashlib
import pytest
from core.projects import site_office as office
from core.projects.controls import digest

@pytest.fixture
def env(tmp_path):
    f=tmp_path/'proof';f.write_text('actual evidence')
    source={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'reference':'proof'}
    p={'id':'P','project_schedule_tasks':[{'id':'A','unit':'m3','measurement':{'kind':'explicit','total':'100'}}], 'project_resources':[{'id':'C'},{'id':'E'}],'project_materials':[{'id':'M'}]}
    data=dict(project_id='P',activity_id='A',date='2026-10-24',reference='D1',summary='Concrete',location='floor1',crew_ids=['C'],equipment_ids=['E'],material_ids=['M'],human_count=4,quantity='1.25',unit='m3',technical_notes='Observed',attachments=[source],source=source)
    return p,data,source

def cmd(p,op,data,actor='author'):
    return office.dispatch(p,op,data,actor,'documented reason')

def issue(p,d,prefix='daily'):
    for suffix,actor in [('review','reviewer'),('approve','approver'),('issue','issuer')]:cmd(p,prefix+'_'+suffix,{'id':d['id']},actor)

def test_daily_versions_transfer_and_no_automatic_progress(env):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    assert not p.get('progress_documents')
    before=deepcopy(d)
    payload={'id':d['id'],'cumulative_quantity':'1.25','initial_observation':True,'previous_cumulative_quantity':'0','quantity_semantics':'cumulative','source':source,'reference':'WORK-D1'}
    result=cmd(p,'daily_transfer',payload)
    assert result['status']=='draft' and result['quantity']=='1.25'
    with pytest.raises(ValueError):cmd(p,'daily_transfer',payload)
    assert len(p['progress_documents'])==1
    amendment=cmd(p,'daily_amend',{**data,'id':d['id'],'reference':'D2','quantity':'2.5'})
    assert d==before and amendment['supersedes']==d['id'] and amendment['version']==2

@pytest.mark.parametrize('field,value',[('quantity',None),('human_count',None),('activity_id','other'),('project_id','other'),('unit','kg'),('crew_ids',['other']),('attachments',[{}])])
def test_daily_rejects_incomplete_or_foreign(env,field,value):
    p,data,_=env
    with pytest.raises(ValueError):cmd(p,'daily_create',{**data,field:value})

def test_review_independence_and_tamper(env):
    p,data,_=env;d=cmd(p,'daily_create',data)
    with pytest.raises(ValueError):cmd(p,'daily_review',{'id':d['id']})
    d['quantity']='99'
    with pytest.raises(ValueError):cmd(p,'daily_review',{'id':d['id']},'reviewer')

def test_packages_snapshot_and_stale_source(env):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    payload=dict(reference='PK1',title='Office',date=data['date'],template='office',template_version='1',sources=[{'collection':'project_daily_reports','id':d['id'],'sha256':digest(d),'version':1}])
    pkg=cmd(p,'package_create',payload);issue(p,pkg,'package')
    assert pkg['documents'][0]['record']==d and pkg['drawing_status']=='waiting_phase7'
    old=deepcopy(pkg);d['summary']='tamper'
    assert pkg==old
    with pytest.raises(ValueError):cmd(p,'package_create',{**payload,'reference':'PK2'})
    for collection in ['nonsense','drawings']:
        with pytest.raises(ValueError):cmd(p,'package_create',{**payload,'sources':[{'collection':collection,'id':'x'}]})

def test_obstacles_meetings_correspondence_and_overdue(env):
    p,data,source=env
    obstacle=cmd(p,'obstacle_create',dict(title='Access',owner='foreman',date=data['date'],due_date='2026-10-25',location='floor1',activity_id='A',source=source))
    meeting=cmd(p,'meeting_create',dict(title='Coordination',date=data['date'],reference='MT1',participants=['Alice','Bob'],decisions='Inspect access',source=source,attachments=[],actions=[dict(title='Inspect',owner='Alice',due_date='2026-10-25',activity_id='A',source=source)]))
    issue(p,meeting,'meeting')
    snap=office.snapshot(p,as_of='2026-10-26')
    assert len(snap['overdue_actions'])==len(snap['overdue_obstacles'])==1
    original=deepcopy(meeting)
    cmd(p,'action_resolve',dict(id=meeting['action_items'][0]['id'],date='2026-10-26',resolution='Inspected',source=source))
    cmd(p,'obstacle_resolve',dict(id=obstacle['id'],date='2026-10-26',resolution='Access restored',source=source))
    assert meeting==original
    assert office.snapshot(p,as_of='2026-10-26')['overdue_actions']==[]
    c=cmd(p,'correspondence_create',dict(title='RFI',kind='rfi',activity_id='A',due_date='2026-10-25',recipient='Engineer',technical_notes='Clarification',date=data['date'],reference='R1',source=source,attachments=[]));issue(p,c,'correspondence')
    assert c['delivery_status']=='not_sent'
    assert c['activity_id']=='A' and c['due_date']=='2026-10-25'

@pytest.mark.parametrize('change',[{'quantity_semantics':'incremental'},{'cumulative_quantity':None},{'source':{}},{'project_id':'foreign'}])
def test_transfer_fails_closed(env,change):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    payload={'id':d['id'],'reference':'W1','quantity_semantics':'cumulative','cumulative_quantity':'20','source':source,**change}
    with pytest.raises(ValueError):cmd(p,'daily_transfer',payload)
    assert not p.get('progress_documents') and not p.get('site_action_events')

def test_unapproved_transfer_and_unapproved_package(env):
    p,data,source=env;d=cmd(p,'daily_create',data)
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{'id':d['id'],'reference':'W','quantity_semantics':'cumulative','cumulative_quantity':'2','source':source})
    with pytest.raises(ValueError):cmd(p,'package_create',dict(reference='P',title='Package',template='T',template_version='1',date=data['date'],sources=[{'collection':'project_daily_reports','id':d['id'],'sha256':digest(d),'version':1}]))

def test_evidence_file_tamper_blocks_lifecycle(env):
    p,data,source=env;d=cmd(p,'daily_create',data)
    from pathlib import Path
    Path(source['path']).write_text('changed')
    with pytest.raises(ValueError):cmd(p,'daily_review',{'id':d['id']},'reviewer')

def test_package_rechecks_source_before_issue_and_reads_are_detached(env):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    payload=dict(reference='P',title='Package',template='T',template_version='1',date=data['date'],sources=[{'collection':'project_daily_reports','id':d['id'],'sha256':digest(d),'version':1}])
    pkg=cmd(p,'package_create',payload)
    cmd(p,'package_review',{'id':pkg['id']},'reviewer')
    d['summary']='changed'
    with pytest.raises(ValueError):cmd(p,'package_approve',{'id':pkg['id']},'approver')
    snap=office.snapshot(p,as_of=data['date']);snap['packages'][0]['title']='local edit'
    assert pkg['title']=='Package'

def test_correspondence_cannot_assert_external_delivery(env):
    p,data,source=env
    c=cmd(p,'correspondence_create',dict(title='Instruction',kind='instruction',activity_id='A',recipient='Engineer',technical_notes='Review',date=data['date'],reference='C1',source=source,attachments=[],delivery_status='sent'))
    assert c['delivery_status']=='not_sent'

def test_correspondence_rejects_foreign_activity_or_early_followup(env):
    p,data,source=env
    base=dict(title='RFI',kind='rfi',activity_id='A',recipient='Engineer',technical_notes='Review',date=data['date'],reference='R',source=source,attachments=[])
    for change in [{'activity_id':'foreign'},{'activity_id':None},{'due_date':'2026-10-23'}]:
        with pytest.raises(ValueError):cmd(p,'correspondence_create',{**base,**change})

def test_rfi_response_is_documented_event_not_external_send(env):
    p,data,source=env
    c=cmd(p,'correspondence_create',dict(title='RFI',kind='rfi',activity_id='A',due_date='2026-10-25',recipient='Engineer',technical_notes='Question',date=data['date'],reference='R',source=source,attachments=[]));issue(p,c,'correspondence')
    assert office.snapshot(p,as_of='2026-10-26')['overdue_correspondence'][0]['id']==c['id']
    original=deepcopy(c)
    cmd(p,'correspondence_response',dict(id=c['id'],date='2026-10-26',resolution='Explicit user-recorded reply',source=source))
    assert c==original
    assert office.snapshot(p,as_of='2026-10-26')['overdue_correspondence']==[]
    assert office.snapshot(p,as_of='2026-10-26')['correspondence'][0]['response_status']=='responded'
    with pytest.raises(ValueError):cmd(p,'correspondence_response',dict(id=c['id'],date='2026-10-26',resolution='Duplicate',source=source))

@pytest.mark.parametrize('extra',[{}, {'initial_observation':True,'previous_cumulative_quantity':'0','cumulative_quantity':'90'}, {'initial_observation':True,'previous_cumulative_quantity':'1'}])
def test_transfer_reconciles_signed_daily_quantity(env,extra):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{'id':d['id'],'reference':'W','quantity_semantics':'cumulative','cumulative_quantity':'1.25','source':source,**extra})

def test_transfer_captured_measurement_basis(env):
    p,data,source=env;d=cmd(p,'daily_create',data);issue(p,d)
    p['project_schedule_tasks'][0]['measurement']['total']='101'
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{'id':d['id'],'reference':'W','quantity_semantics':'cumulative','cumulative_quantity':'1.25','source':source,'initial_observation':True,'previous_cumulative_quantity':'0'})

def test_prior_observation_and_amended_transfer(env):
    p,data,source=env
    from core.projects.physical_progress import progress_command
    prior=progress_command(p,'progress_create',dict(activity_id='A',date='2026-10-23',reference='PREVIOUS',cumulative_quantity='10',source=source),'previous-author','reason')
    for op,actor in [('progress_review','reviewer'),('progress_approve','approver')]:progress_command(p,op,{'id':prior['id']},actor,'reason')
    d=cmd(p,'daily_create',data);issue(p,d)
    payload={'id':d['id'],'reference':'W1','quantity_semantics':'cumulative','cumulative_quantity':'11.25','source':source,'previous_cumulative_quantity':'10','previous_progress_id':prior['id']}
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{**payload,'previous_progress_id':'foreign'})
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{**payload,'previous_cumulative_quantity':'9'})
    transferred=cmd(p,'daily_transfer',payload)
    amendment=cmd(p,'daily_amend',{**data,'id':d['id'],'reference':'D2','quantity':'2.5'});issue(p,amendment)
    correction={**payload,'id':amendment['id'],'reference':'W2','cumulative_quantity':'12.5','supersedes':transferred['id']}
    with pytest.raises(ValueError):cmd(p,'daily_transfer',correction)
    for op,actor in [('progress_review','reviewer'),('progress_approve','approver')]:progress_command(p,op,{'id':transferred['id']},actor,'reason')
    fixed=cmd(p,'daily_transfer',correction)
    assert fixed['supersedes']==transferred['id'] and fixed['quantity']=='12.5' and fixed['status']=='draft'
    with pytest.raises(ValueError):cmd(p,'daily_transfer',correction)
    with pytest.raises(ValueError):cmd(p,'daily_transfer',payload)

def test_statement_package_requires_real_issued_workflow(env):
    p,data,_=env;period={'number':1,'reference':'ST1','date':data['date'],'lines':[]};p['statement_periods']=[period]
    payload=dict(reference='PK1',title='Office',date=data['date'],template='office',template_version='1',sources=[{'collection':'statement_periods','id':'1','sha256':digest(period),'version':1}])
    with pytest.raises(ValueError):cmd(p,'package_create',payload)
    p['statement_workflow']=[{'id':'SW1','status':'APPROVED','period':deepcopy(period)}]
    with pytest.raises(ValueError):cmd(p,'package_create',payload)
    p['statement_workflow'][0]['status']='ISSUED'
    pkg=cmd(p,'package_create',payload)
    assert pkg['documents'][0]['record']==period
    p['statement_workflow'][0]['period']['reference']='tampered'
    with pytest.raises(ValueError):cmd(p,'package_review',{'id':pkg['id']},'reviewer')

def test_progress_report_package_validates_seal_and_source(env):
    p,data,source=env
    doc={'id':'WORK1','status':'approved','activity_id':'A','source':source,'basis_digest':digest(p['project_schedule_tasks'][0]['measurement'])};p['progress_documents']=[doc]
    report={'id':'REPORT1','version':1,'activities':[{'id':'A','source_document':'WORK1'}]};report['sha256']=digest(report);p['progress_reports']=[report]
    payload=dict(reference='PK1',title='Office',date=data['date'],template='office',template_version='1',sources=[{'collection':'progress_reports','id':report['id'],'sha256':digest(report),'version':1}])
    pkg=cmd(p,'package_create',payload);assert pkg['documents'][0]['record']==report
    doc['status']='draft'
    with pytest.raises(ValueError):cmd(p,'package_review',{'id':pkg['id']},'reviewer')
    report['version']=2
    with pytest.raises(ValueError):cmd(p,'package_create',{**payload,'reference':'PK2'})

def test_amendment_before_any_transfer_is_regular_initial_progress(env):
    p,data,source=env;original=cmd(p,'daily_create',data);issue(p,original)
    amended=cmd(p,'daily_amend',{**data,'id':original['id'],'reference':'D2','quantity':'2.5'});issue(p,amended)
    payload={'id':amended['id'],'reference':'W','quantity_semantics':'cumulative','cumulative_quantity':'2.5','previous_cumulative_quantity':'0','initial_observation':True,'source':source}
    result=cmd(p,'daily_transfer',payload)
    assert result['quantity']=='2.5' and result['supersedes'] is None
    with pytest.raises(ValueError):cmd(p,'daily_transfer',{**payload,'id':original['id'],'reference':'OLD'})

def test_package_snapshot_marks_current_source_error_without_mutating_original(env):
    p,data,_=env;d=cmd(p,'daily_create',data);issue(p,d)
    pkg=cmd(p,'package_create',dict(reference='P',title='Package',template='T',template_version='1',date=data['date'],sources=[{'collection':'project_daily_reports','id':d['id'],'sha256':digest(d),'version':1}]))
    issue(p,pkg,'package');original=deepcopy(pkg)
    assert office.snapshot(p,as_of=data['date'])['packages'][0]['current'] is True
    d['summary']='altered'
    result=office.snapshot(p,as_of=data['date'])['packages'][0]
    assert result['current'] is False and result['source_error']
    assert pkg==original
