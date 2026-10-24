from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp
from core.projects.controls import measurement,basis_stale
from core.takeoff.boq import build_boq
from test_phase4_structure import cmd,structure,activity
from test_phase4_progress import project,weights,work

def source_project():
    rows=[{'source_id':'T','quantities':[{'code':c,'unit':u,'amount':q,'title':c,'formula':'explicit synthetic fixture'} for c,u,q in [('concrete','m3','10'),('formwork','m2','20')]]}]
    boq=build_boq([{'source_id':'T','source_ids':['T'],'item_code':c,'unit':u,'quantity':q,'description':c} for c,u,q in [('concrete','m3','10'),('formwork','m2','20')]])
    return {'takeoffs':rows,'boq':boq,'project_schedule_tasks':[]}

def test_orphan_boq_rejected():
    p=source_project();p['takeoffs']=[];p['boq']=[p['boq'][0]]
    with pytest.raises(ValueError):measurement(p,{'kind':'boq','source_ids':['T']},'m3','A')

def test_two_quantities_same_takeoff_are_distinct_owners():
    p=source_project()
    a=measurement(p,{'kind':'boq','source_ids':['T'],'item_code':'concrete'},'m3','A')
    p['project_schedule_tasks']=[{'id':'A','measurement':a}]
    b=measurement(p,{'kind':'boq','source_ids':['T'],'item_code':'formwork'},'m2','B')
    assert a['total']=='10' and b['total']=='20'
    with pytest.raises(ValueError):measurement(p,{'kind':'boq','source_ids':['T'],'item_code':'concrete'},'m3','C')

def test_financial_work_quantity_does_not_change_physical_basis():
    p=source_project();m=measurement(p,{'kind':'boq','source_ids':['T'],'item_code':'concrete'},'m3','A');a={'measurement':m}
    p['boq'][0]['current_quantity']='1';p['boq'][0]['unit_price']='999'
    assert basis_stale(p,a) is False
    p['boq'][0]['quantity']='11';assert basis_stale(p,a) is True

@pytest.mark.parametrize('key,value',[('schedule_baselines',[{'id':'FORGED'}]),('project_control_history',[{'op':'FORGED'}]),('progress_documents',[{'status':'approved'}]),('progress_reports',[{'actual':100}])])
def test_pre_activation_official_collections_guarded(tmp_path,key,value):
    a=StructuralProApp(tmp_path);a.create_project('آزمایشی','P');p=a.open_project('P');p[key]=value
    try:
        with pytest.raises(ValueError):a.store.save('P',p)
    finally:a.store.close()

def test_single_floor_shares_cannot_distort_progress(project):
    a,p=project
    with pytest.raises(ValueError):weights(a,p,floor_shares={'A':{'F1':'100'}})

def test_status_title_and_responsible_do_not_invalidate_weight_scope(project):
    a,p=project;weights(a,p);work(a,p,'A','5','2026-01-06','A');work(a,p,'B','5','2026-01-06','B')
    row=a.open_project('P')['project_schedule_tasks'][0]
    cmd(a,'activity',**{**row,'status':'in_progress','title':'عنوان تازه','responsible':'مسئول دیگر'})
    assert a.project_progress('P',as_of='2026-01-06')['actual']=='31.250000'

def test_calendar_refresh_updates_legacy_projection_atomically(project):
    a,p=project;baseline=deepcopy(a.open_project('P')['schedule_baselines'])
    cmd(a,'schedule_calendar',start='2026-02-01',calendar={'weekdays':list(range(7)),'holidays':[]})
    assert a.open_project('P')['project_schedule_tasks'][0]['planned_start']=='2026-02-01'
    assert a.open_project('P')['schedule_baselines']==baseline

def test_legacy_activity_selection_is_explicit_incomplete_editor(tmp_path):
    from PySide6.QtWidgets import QApplication
    from app.project_controls_workspace import ProjectControlsWorkspace
    qt=QApplication.instance() or QApplication([])
    a=StructuralProApp(tmp_path);a.create_project('قدیمی','P');p=a.open_project('P');p['project_schedule_tasks']=[{'id':'OLD','title':'قدیمی','planned_start':'2026-01-01','planned_end':'2026-01-03'}];a.store.save('P',p)
    w=ProjectControlsWorkspace(a,'P')
    try:
        w.select_activity('OLD');assert w.selected_id=='OLD';assert w.fields['activity_code'].text()=='';assert w.fields['activity_unit'].text()==''
    finally:w.close();qt.processEvents();a.store.close()
