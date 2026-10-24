from copy import deepcopy
from datetime import date,timedelta
import pytest
from core.platform.application import StructuralProApp
from test_phase4_structure import cmd,structure,activity

CAL={'weekdays':[0,1,2,3,4],'holidays':['2026-01-05']}
def test_cpm_independent_parallel_oracle():
    from core.projects import management
    assert hasattr(management.ProjectManagement,'calculate_cpm'),'CPM is absent'
    tasks=[{'id':'A','duration':2},{'id':'B','duration':3},{'id':'C','duration':1},{'id':'D','duration':2},{'id':'M','duration':0}]
    links=[{'pred':a,'succ':b,'type':'FS','lag':0} for a,b in [('A','B'),('A','C'),('B','D'),('C','D'),('D','M')]]
    r=management.ProjectManagement.calculate_cpm(tasks,links,start='2026-01-02',calendar=CAL)
    by=r['activities'];assert r['duration']==7
    assert {k:(v['es'],v['ef'],v['ls'],v['lf'],v['total_float'],v['free_float']) for k,v in by.items()}=={
      'A':(0,2,0,2,0,0),'B':(2,5,2,5,0,0),'C':(2,3,4,5,2,2),'D':(5,7,5,7,0,0),'M':(7,7,7,7,0,0)}
    # Independent calendar enumeration: Jan2,6,7,8,9,12,13,14.
    assert by['A']['start']=='2026-01-02' and by['A']['finish']=='2026-01-06'
    assert r['finish_boundary']=='2026-01-14'

@pytest.mark.parametrize('relation,lag,es',[('FS',1,5),('SS',1,1),('FF',1,3),('SF',3,1),('FS',-1,3)])
def test_relationship_offsets(relation,lag,es):
    from core.projects import management
    assert hasattr(management.ProjectManagement,'calculate_cpm'),'CPM is absent'
    r=management.ProjectManagement.calculate_cpm([{'id':'A','duration':4},{'id':'B','duration':2}],
        [{'pred':'A','succ':'B','type':relation,'lag':lag}],start='2026-03-19',calendar={'weekdays':list(range(7)),'holidays':[]})
    assert r['activities']['B']['es']==es

@pytest.mark.parametrize('tasks,links,cal',[
 ([{'id':'A','duration':-1}],[],CAL),([{'id':'A','duration':True}],[],CAL),
 ([{'id':'A','duration':1},{'id':'B','duration':1}],[{'pred':'A','succ':'B','type':'FS','lag':0},{'pred':'B','succ':'A','type':'FS','lag':0}],CAL),
 ([{'id':'A','duration':1}],[],{'weekdays':[],'holidays':[]}),
 ([{'id':'A','duration':1}],[{'pred':'A','succ':'MISSING','type':'FS','lag':0}],CAL),
])
def test_bad_network_fails(tasks,links,cal):
    from core.projects import management
    assert hasattr(management.ProjectManagement,'calculate_cpm'),'CPM is absent'
    with pytest.raises(ValueError):management.ProjectManagement.calculate_cpm(tasks,links,start='2026-01-01',calendar=cal)

def test_baseline_immutable_current_revision_reopen(tmp_path):
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');structure(a);activity(a)
    cmd(a,'schedule_calendar',start='2026-03-19',calendar={'weekdays':list(range(7)),'holidays':[]})
    cmd(a,'schedule_activity',id='A',duration=3,not_before=None,relationships=[])
    b=cmd(a,'schedule_baseline',reference='BASE1',approved_by='owner')
    assert b['result']['duration']==3;assert b['result']['activities']['A']['finish']=='2026-03-21'
    cmd(a,'schedule_activity',id='A',duration=5,not_before=None,relationships=[])
    p=a.open_project('P');assert p['schedule_baselines'][0]==b
    p['schedule_baselines'][0]['result']['duration']=99
    with pytest.raises(ValueError):a.store.save('P',p)
    a.store.close();a=StructuralProApp(tmp_path)
    try:
        assert a.project_schedule('P')['duration']==5
        assert a.open_project('P')['schedule_baselines'][0]==b
    finally:a.store.close()

def test_negative_lead_free_float_respects_project_finish():
    from core.projects.management import ProjectManagement
    r=ProjectManagement.calculate_cpm([{'id':'A','duration':4},{'id':'B','duration':2}],[{'pred':'A','succ':'B','type':'FS','lag':-5}],start='2026-01-01',calendar={'weekdays':list(range(7)),'holidays':[]})
    assert r['activities']['A']['free_float']==0
    assert all(x['free_float']<=x['total_float'] for x in r['activities'].values())
