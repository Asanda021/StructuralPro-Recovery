import hashlib
from decimal import Decimal
import pytest
from core.platform.application import StructuralProApp
from test_phase4_structure import cmd,structure

@pytest.fixture
def project(tmp_path):
    a=StructuralProApp(tmp_path/'db');a.create_project('آزمایشی','P');structure(a)
    path=tmp_path/'proof.txt';path.write_text('SYNTHETIC explicit approved quantities and weights')
    proof={'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'reference':'TEST'}
    for id,floor,total in [('A','F1','10'),('B','F2','20')]:
        cmd(a,'activity',id=id,title='کار '+id,code=id,wbs_id='W1',floor_ids=[floor],zone_ids=[],member_ids=[],discipline_id='S',unit='m3',responsible='مسئول',status='todo',measurement={'kind':'explicit','total':total,'source':proof,'approved_by':'owner'})
    cmd(a,'schedule_calendar',start='2026-01-01',calendar={'weekdays':list(range(7)),'holidays':[]})
    for id in ['A','B']:cmd(a,'schedule_activity',id=id,duration=10,not_before=None,relationships=[])
    cmd(a,'schedule_baseline',reference='B1',approved_by='owner')
    yield a,proof
    a.store.close()

def transition(a,op,id,actor):return a.project_control_command('P',op,actor=actor,reason='بازبینی مستقل آزمایشی',expected_version=a.open_project('P')['_meta']['version'],id=id)
def weights(a,proof,**override):
    r=cmd(a,'weight_create',reference='W1',source=proof,weights={'A':'1','B':'3'},method='manual_approved',distributions={'A':'linear_workdays','B':'linear_workdays'},decimal_places=6,rounding='ROUND_HALF_EVEN',**override)
    transition(a,'weight_review',r['id'],'reviewer');return transition(a,'weight_approve',r['id'],'approver')
def work(a,proof,id,q,date,ref,supersedes=None):
    d=cmd(a,'progress_create',activity_id=id,cumulative_quantity=q,date=date,reference=ref,source=proof,supersedes=supersedes)
    transition(a,'progress_review',d['id'],'reviewer');return transition(a,'progress_approve',d['id'],'approver')

def test_weighted_decimal_and_no_interpolated_periods(project):
    a,p=project;assert hasattr(a,'project_progress'),'verified physical progress API absent'
    weights(a,p);work(a,p,'A','5','2026-01-06','A1');work(a,p,'B','5','2026-01-06','B1')
    r=a.project_progress('P',as_of='2026-01-06')
    assert Decimal(r['actual'])==Decimal('31.25') # (1*50+3*25)/4
    assert Decimal(r['planned'])==Decimal('50')
    assert Decimal(r['variance'])==Decimal('-18.75')
    assert Decimal(r['groups']['floors']['F1']['actual'])==50
    assert Decimal(r['groups']['floors']['F2']['actual'])==25
    cmd(a,'progress_report',date='2026-01-06',reference='R1')
    work(a,p,'A','10','2026-01-11','A2');work(a,p,'B','20','2026-01-11','B2')
    cmd(a,'progress_report',date='2026-01-11',reference='R2')
    curve=a.project_progress_curve('P',frequency='daily');assert [x['date'] for x in curve]==['2026-01-06','2026-01-11']
    assert curve[-1]['actual']=='100.000000'

def test_missing_data_unknown_overrun_rejected_and_correction(project):
    a,p=project;assert hasattr(a,'project_progress'),'verified physical progress API absent'
    assert a.project_progress('P',as_of='2026-01-06')['actual'] is None
    weights(a,p)
    with pytest.raises(ValueError):work(a,p,'A','11','2026-01-06','OVER')
    first=work(a,p,'A','5','2026-01-06','A1');work(a,p,'B','0','2026-01-06','B1')
    assert Decimal(a.project_progress('P',as_of='2026-01-06')['actual'])==Decimal('12.5')
    correction=work(a,p,'A','4','2026-01-06','FIX',supersedes=first['id'])
    r=a.project_progress('P',as_of='2026-01-06');assert Decimal(r['actual'])==10
    assert correction['supersedes']==first['id']
    original=next(d for d in a.open_project('P')['progress_documents'] if d['id']==first['id']);assert original['quantity']=='5'
    with pytest.raises(ValueError):work(a,p,'A','3','2026-01-07','REGRESS')

@pytest.mark.parametrize('q',[True,'NaN','Infinity','-1','1e100'])
def test_invalid_quantity(project,q):
    a,p=project;assert hasattr(a,'project_progress'),'verified physical progress API absent'
    before=a.open_project('P')
    with pytest.raises(ValueError):work(a,p,'A',q,'2026-01-06','BAD')
    assert a.open_project('P')==before

def test_approval_independence_and_raw_reports_immutable(project):
    a,p=project;assert hasattr(a,'project_progress'),'verified physical progress API absent'
    d=cmd(a,'progress_create',activity_id='A',cumulative_quantity='2',date='2026-01-06',reference='A',source=p,supersedes=None)
    with pytest.raises(ValueError):transition(a,'progress_review',d['id'],'planner')
    transition(a,'progress_review',d['id'],'reviewer')
    with pytest.raises(ValueError):transition(a,'progress_approve',d['id'],'reviewer')
    transition(a,'progress_approve',d['id'],'approver')
    weights(a,p);work(a,p,'B','0','2026-01-06','B')
    r=cmd(a,'progress_report',date='2026-01-06',reference='R')
    work(a,p,'A','1','2026-01-06','FIX',supersedes=d['id'])
    assert a.open_project('P')['progress_reports'][0]==r
    dirty=a.open_project('P');dirty['progress_documents'].clear()
    with pytest.raises(ValueError):a.store.save('P',dirty)

def test_current_schedule_revision_does_not_rewrite_weights_or_baseline(project):
    a,p=project;weights(a,p);work(a,p,'A','5','2026-01-06','A');work(a,p,'B','10','2026-01-06','B')
    baseline=a.open_project('P')['schedule_baselines'][0];weight=a.open_project('P')['progress_weight_sets'][0]
    cmd(a,'schedule_activity',id='A',duration=12,not_before=None,relationships=[])
    r=a.project_progress('P',as_of='2026-01-06')
    assert r['actual']=='50.000000' and r['planned']=='50.000000'
    assert a.open_project('P')['schedule_baselines'][0]==baseline and a.open_project('P')['progress_weight_sets'][0]==weight

def test_multifloor_shares_no_rounding_acceptance(project):
    a,p=project
    activity=a.open_project('P')['project_schedule_tasks'][0]
    cmd(a,'activity',**{**activity,'floor_ids':['F1','F3']})
    with pytest.raises(ValueError):
        cmd(a,'weight_create',reference='BADSHARE',source=p,weights={'A':'1','B':'3'},method='manual_approved',distributions={'A':'linear_workdays','B':'linear_workdays'},decimal_places=6,rounding='ROUND_HALF_EVEN',floor_shares={'A':{'F1':'0.999999999999999999999999999999','F3':'0'}})

def test_baseline_current_planned_comparison(project):
    a,p=project;weights(a,p);work(a,p,'A','5','2026-01-06','A');work(a,p,'B','10','2026-01-06','B')
    cmd(a,'schedule_activity',id='A',duration=20,not_before=None,relationships=[])
    r=a.project_progress('P',as_of='2026-01-06')
    assert r['planned']=='50.000000' and r['planned_current']=='43.750000'
    assert r['variance']=='0.000000' and r['variance_current']=='6.250000'
