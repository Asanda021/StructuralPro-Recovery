"""A wholly synthetic 106-activity, five-storey control project."""
from datetime import date, timedelta
from hashlib import sha256
import csv

import pytest

from core.platform.application import StructuralProApp
from core.projects.controls import digest
from core.projects.store import ProjectStore
from test_phase4_structure import cmd, structure

START = date(2027, 3, 22)
ALL = {'weekdays':list(range(7)), 'holidays':[]}
CREW = {'weekdays':list(range(6)), 'holidays':[]}
LIFT = {'weekdays':list(range(5)), 'holidays':[]}
H = date(2027,3,23)
IDS = [f'{lane}{i:02d}' for lane in 'ABCDE' for i in range(21)]
DISCIPLINES = ['S','ARCH','MEP','ELEC','SITE']


def synthetic_source(tmp_path):
    path=tmp_path/'synthetic-golden-106.txt'
    path.write_text('SYNTHETIC ONLY: 106 activities. No contract, geometry or payment.',encoding='utf-8')
    return {'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest(),'reference':'SYNTHETIC-P8-P2-B-106'}


def link(pred,succ,kind,lag=0):
    return {'pred':pred,'succ':succ,'type':kind,'lag':lag}


def site(service,op,actor='maker',**data):
    return service.site_command('P',op,actor=actor,reason='Golden 106 synthetic',
        expected_version=service.open_project('P')['_meta']['version'],**data)


def resource(service,key,kind,proof,capacity):
    site(service,'resource_create',id=key,name=key,kind=kind,capacity=capacity,unit='unit',
         discipline_id='S',subcontractor='SYNTHETIC',source=proof)
    site(service,'resource_review',actor='reviewer',id=key)
    site(service,'resource_approve',actor='approver',id=key)
    return site(service,'availability',id='AV-'+key,resource_id=key,start=START.isoformat(),
                end=(START+timedelta(days=25)).isoformat(),state='present',capacity=capacity,confirmed=True,source=proof)


def calendars(service,holiday=False):
    crew={**CREW,'holidays':[H.isoformat()] if holiday else []}
    return cmd(service,'schedule_calendar',start=START.isoformat(),calendar=ALL,
               calendars={'activity':ALL,'crew':crew,'lift':LIFT},resource_calendars={'C':'crew','L':'lift'})


def put_task(service,key, proof, total='100'):
    i=int(key[1:]) if key!='M' else 0
    lane='ABCDE'.index(key[0]) if key!='M' else 4
    return cmd(service,'activity',id=key,title=f'فعالیت آزمایشی {key}',code=key,wbs_id='W1',
               floor_ids=[f'F{lane+1}'],zone_ids=[],member_ids=[],discipline_id=DISCIPLINES[lane],
               unit='m2',responsible='آزمایشی',status='todo',measurement=(
                   {'kind':'explicit','total':total,'source':proof,'approved_by':'synthetic-reviewer'}
                   if key=='A00' else {'kind':'none'}))


def plan(service, key, duration=None):
    if key=='M':
        return cmd(service,'schedule_activity',id=key,duration=0,
                   relationships=[link(lane+'20','M','FS') for lane in 'ABCDE'])
    lane, index=key[0],int(key[1:])
    # With equal two-day durations all four expressions imply one-day start gap.
    rels=[] if index==0 else [link(f'{lane}{index-1:02d}',key,*[('FS',-1),('SS',1),('FF',1),('SF',3)][(index-1)%4])]
    return cmd(service,'schedule_activity',id=key,duration=2 if duration is None else duration,
               relationships=rels,**({'calendar_id':'activity','resource_ids':['C','L']} if key=='A00' else {}))


def oracle(holiday=False, extra_days=0):
    # A00 occupies two/three explicitly open weekdays. All other tasks run
    # seven days/week. Every pair has equal duration except A00→A01 (FS−1).
    open_days=[START+timedelta(days=i) for i in range(12)
               if (START+timedelta(days=i)).weekday()<5 and (not holiday or START+timedelta(days=i)!=H)]
    last=open_days[1+extra_days]
    first_lane_gap=(last-START).days
    finish=first_lane_gap+21
    values={}
    for key in IDS:
        i=int(key[1:])
        start=(first_lane_gap+i-1 if i else 0) if key.startswith('A') else i
        end=(last-START).days+1 if key=='A00' else start+2
        float_days=0 if key.startswith('A') else finish-22
        values[key]=(start,end,start+float_days,end+float_days,float_days,0 if i<20 else float_days)
    values['M']=(finish,finish,finish,finish,0,0)
    return START+timedelta(days=finish),values


def check_schedule(service, *, holiday=False, extra_days=0):
    actual=service.project_schedule('P')
    finish, values=oracle(holiday,extra_days)
    assert actual['finish_boundary']==finish.isoformat()
    for key,expected in values.items():
        row=actual['activities'][key]
        assert tuple(row[field] for field in ('es','ef','ls','lf','total_float','free_float'))==expected, key
    return actual


def status(service, day, proof, state, quantity, remaining, work):
    observation={'id':'A00','state':state,'remaining_duration':remaining,'actual_quantity':quantity,
                 'remaining_work':work,'source':proof}
    if state!='NOT_STARTED':
        observation['actual_start']=START.isoformat()
    if state=='COMPLETED':
        observation['actual_finish']='2027-03-25'
    return cmd(service,'schedule_status',data_date=day,policy='RETAINED_LOGIC',unreported='NOT_STARTED',
               observations=[observation])


def test_golden_106_three_status_dates_three_baselines_backup_and_report_readback(tmp_path):
    proof=synthetic_source(tmp_path)
    work=tmp_path/'workspace'
    service=StructuralProApp(work)
    try:
        service.create_project('SYNTHETIC GOLDEN 106 | پروژهٔ کاملاً آزمایشی', 'P')
        structure(service)
        for did in DISCIPLINES[1:]:
            cmd(service,'discipline',id=did,title=did)
        site(service,'policy',actor='owner',owner='owner',establish_owner=True,source=proof,
             permissions={k:['maker','reviewer','approver','owner'] for k in ('create','review','approve','issue','adjust','finance')})
        present=resource(service,'C','crew',proof,'1')
        resource(service,'L','equipment',proof,'1')
        calendars(service)
        for key in [*IDS,'M']:
            put_task(service,key,proof)
        for key in [*IDS,'M']:
            plan(service,key)
        initial=check_schedule(service)
        b1=cmd(service,'schedule_baseline',reference='GOLD-1',approved_by='reviewer')
        s1=status(service,START.isoformat(),proof,'NOT_STARTED','0',2,'100')
        assert s1['forecast_finish']=='2027-04-13'
        put_task(service,'A00',proof,total='120')
        with pytest.raises(ValueError):
            service.project_schedule_forecast('P')
        calendars(service,holiday=True)
        changed=check_schedule(service,holiday=True)
        assert changed['finish_boundary']=='2027-04-14'
        assert changed['activities']['B20']['total_float']==1
        b2=cmd(service,'schedule_baseline',reference='GOLD-2',approved_by='reviewer')
        s2=status(service,'2027-03-24',proof,'IN_PROGRESS','30',1,'90')
        # Resume 24 March, finish boundary 25 March. FS−1 then allows
        # A01 on 24 March. A20 starts 12 April and M is on 14 April,
        # but the other unstarted lanes run 22 days from 24 March.
        assert s2['forecast_finish']=='2027-04-15'
        assert s2['baseline_delta_days']==1
        assert service.project_schedule_forecast('P')['activities']['A00']['resume']=='2027-03-24'
        site(service,'requirements',id='REQ',activity_id='A00',resources=[{'resource_id':'C','quantity':'1'}],
             materials=[],source=proof)
        site(service,'assign',id='AS',activity_id='A00',resource_id='C',start=START.isoformat(),
             end='2027-03-26',allocation='1',source=proof)
        site(service,'assignment_review',actor='reviewer',id='AS')
        site(service,'assignment_approve',actor='approver',id='AS')
        read=lambda:next(x for x in service.site_lookahead('P',start=START.isoformat(),days=7)['activities'] if x['id']=='A00')
        assert read()['status']=='ready'
        before_capacity=service.store.current_digest('P')
        site(service,'availability',id='AV-C-LOW',resource_id='C',start=present['start'],end=present['end'],
             state='present',capacity='0.5',confirmed=True,supersedes=present['id'],source=proof)
        assert read()['status']=='resource_conflict'
        assert service.store.current_digest('P')!=before_capacity
        assert service.project_schedule('P')==changed
        plan(service,'A00',3)
        final=check_schedule(service,holiday=True,extra_days=1)
        b3=cmd(service,'schedule_baseline',reference='GOLD-3',approved_by='reviewer')
        s3=status(service,'2027-03-26',proof,'COMPLETED','120',0,'0')
        assert s3['forecast_finish']=='2027-04-17' and s3['baseline_delta_days']==2
        forecast=service.project_schedule_forecast('P')
        assert forecast['activities']['A00']['actual_finish']=='2027-03-25'
        assert forecast['activities']['A00']['forecast_finish'] is None
        saved=service.open_project('P')
        assert saved['schedule_baselines']==[b1,b2,b3]
        assert [row['version'] for row in saved['schedule_status_records']]==[1,2,3]
        assert len({b['sha256'] for b in (b1,b2,b3)})==3
        assert len({s['sha256'] for s in (s1,s2,s3)})==3
        assert saved.get('boq',[])==[] and saved.get('financial_records',[])==[] and saved.get('statement_periods',[])==[]
        assert len({initial['input_digest'],changed['input_digest'],final['input_digest']})==3
        target=tmp_path/'verified-backup.db'
        service.store.backup(target)
        backup=ProjectStore(target)
        try:
            assert backup.current_digest('P')==service.store.current_digest('P')
            assert backup.revisions('P')==service.store.revisions('P')
        finally:
            backup.close()
        service.store.close()
        service=StructuralProApp(work)
        assert service.open_project('P')==saved
        assert service.project_schedule('P')==final
        assert service.project_schedule_forecast('P')==forecast
        for fmt in ('csv','xlsx','pdf'):
            output=tmp_path/('golden-106.'+fmt)
            service.project_controls_report('P','schedule',fmt,output)
            assert output.stat().st_size>100
            if fmt=='csv':
                with output.open(encoding='utf-8-sig',newline='') as stream:
                    rows=list(csv.reader(stream))
                assert any('پایان پیش‌بینی پیشنهادی' in row and '2027-04-17' in row for row in rows)
                assert any('شروع مشاهده‌شده' in row for row in rows)
            elif fmt=='xlsx':
                from openpyxl import load_workbook
                workbook=load_workbook(output)
                try:
                    assert all(sheet.sheet_view.rightToLeft for sheet in workbook)
                    assert any('A00' in row for sheet in workbook for row in sheet.values)
                finally:
                    workbook.close()
            else:
                import pymupdf
                with pymupdf.open(output) as pdf:
                    assert len(pdf)>=5 and any(page.get_images() for page in pdf)
    finally:
        service.store.close()
