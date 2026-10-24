"""Explicit synthetic five-floor controls acceptance. Not a real building schedule."""
from copy import deepcopy
from datetime import date,timedelta
from decimal import Decimal,localcontext
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.platform.application import StructuralProApp


def run(root):
    from PySide6.QtWidgets import QApplication
    qt=QApplication.instance() or QApplication([])
    from scripts.phase3_financial_probe import run as prepare
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);prepare(root/'engineering')
    a=StructuralProApp(root/'engineering'/'db');initial=deepcopy(a.open_project('P'));boq=deepcopy(initial['boq'])
    proof=root/'explicit-planning-fixture.txt';proof.write_text('SYNTHETIC TEST ONLY. Five floors 3.2m explicit height; structure=3 workdays, architecture=2, MEP=1. Mon-Fri working, explicit holiday 2026-03-23. Weight S:A:M=2:1:1 each floor. Planned linear at report-day start boundary. Explicit fixture quantities for non-BOQ tasks: 10 m3/20 m2/30 m. Observations and owner/reviewer identities are synthetic, no real engineering approval or inferred production.')
    source={'path':str(proof),'sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),'reference':'SYNTHETIC-PLAN'}
    def command(op,actor='planner',**data):
        return a.project_control_command('P',op,actor=actor,reason='آزمون صریح؛ داده واقعی نیست',expected_version=a.open_project('P')['_meta']['version'],**data)
    command('building',id='B1',title='بلوک بتنی آزمایشی')
    for i in range(1,6):command('floor',id=f'L{i}',title=f'طبقه آزمایشی {i}',building_id='B1',kind='positive',level=i,height='3.2')
    for id,title in [('S','سازه'),('A','معماری'),('M','تأسیسات')]:command('discipline',id=id,title=title)
    command('wbs',id='ROOT',title='ساختمان آزمایشی',code='01',parent_id=None)
    for i in range(1,6):command('wbs',id=f'W{i}',title=f'اجرای طبقه {i}',code=f'01.{i:02}',parent_id='ROOT')
    concrete=next(r for r in boq if r['item_code']=='concrete');wall=next(r for r in boq if r['item_code']=='wall')
    quantities={};weights={};distributions={};tasks={};links=[]
    for i in range(1,6):
        for discipline,label,duration,total,unit in [('S','اسکلت',3,'10','m3'),('A','دیوارچینی',2,'20','m2'),('M','تأسیسات',1,'30','m')]:
            id=discipline+str(i);m={'kind':'explicit','total':total,'source':source,'approved_by':'synthetic-owner'}
            if id in {'S1','A2'}:
                row=concrete if id=='S1' else wall;m={'kind':'boq','source_ids':row['source_ids']};total=str(row['quantity']);unit=row['unit']
            command('activity',id=id,title=label+f' طبقه {i}',code=id,wbs_id=f'W{i}',floor_ids=[f'L{i}'],zone_ids=[],member_ids=['S1'] if id=='S1' else ['W2'] if id=='A2' else [],discipline_id=discipline,unit=unit,responsible='مسئول آزمایشی',status='todo',measurement=m)
            quantities[id]=Decimal(total);weights[id]='2' if discipline=='S' else '1';distributions[id]='linear_workdays';tasks[id]=duration
    calendar={'weekdays':[0,1,2,3,4],'holidays':['2026-03-23']};start='2026-03-16'
    command('schedule_calendar',start=start,calendar=calendar)
    for i in range(1,6):
        for kind in ['S','A','M']:
            id=kind+str(i);pred=f'S{i-1}' if kind=='S' and i>1 else f'S{i}' if kind=='A' else f'A{i}' if kind=='M' else None
            rel=[{'pred':pred,'succ':id,'type':'FS','lag':0}] if pred else [];links.extend(rel)
            command('schedule_activity',id=id,duration=tasks[id],not_before=None,relationships=rel)
    current=a.project_schedule('P');expected_critical=['S1','S2','S3','S4','S5','A5','M5']
    assert set(current['critical_ids'])==set(expected_critical) and current['duration']==18
    # Independent closed-form network oracle; separate calendar day enumeration.
    days=[];cursor=date.fromisoformat(start)
    while len(days)<=18:
        if cursor.weekday() in {0,1,2,3,4} and cursor.isoformat()!='2026-03-23':days.append(cursor)
        cursor+=timedelta(days=1)
    for i in range(1,6):
        for prefix,es in [('S',3*(i-1)),('A',3*i),('M',3*i+2)]:
            r=current['activities'][prefix+str(i)];assert r['es']==es and r['start']==days[es].isoformat()
            assert r['total_float']==(0 if prefix=='S' else 3*(5-i))
    baseline=command('schedule_baseline',reference='SYNTHETIC-BASE-1',approved_by='synthetic-owner')
    w=command('weight_create',reference='SYNTHETIC-WEIGHTS-1',source=source,weights=weights,distributions=distributions,method='manual_approved',decimal_places=6,rounding='ROUND_HALF_EVEN')
    command('weight_review',actor='reviewer',id=w['id']);command('weight_approve',actor='approver',id=w['id'])
    actuals=[];report_dates=[days[5].isoformat(),days[10].isoformat(),days[18].isoformat()]
    for period,day in enumerate(report_dates,1):
        independent=Decimal(0)
        for id,total in quantities.items():
            if period==1:fraction=Decimal(1) if id=='S1' else Decimal('.5') if id=='A1' else Decimal(0)
            elif period==2:fraction=Decimal(1) if id[1:] in {'1','2'} else Decimal('.5') if id=='S3' else Decimal(0)
            else:fraction=Decimal(1) if id[1:] in {'1','2'} or id=='S3' else Decimal('.5')
            # Official correction revises the earlier A1 observation; its issued
            # report remains immutable, then new observed work reaches full.
            if period==3 and id=='A1':
                prior=next(d for d in reversed(a.open_project('P')['progress_documents']) if d['activity_id']==id and d['status']=='approved')
                d=command('progress_create',activity_id=id,cumulative_quantity=str(total*Decimal('.75')),date=prior['date'],reference=f'CORRECT-{id}',source=source,supersedes=prior['id'])
                command('progress_review',actor='reviewer',id=d['id']);command('progress_approve',actor='approver',id=d['id'])
            d=command('progress_create',activity_id=id,cumulative_quantity=str(total*fraction),date=day,reference=f'WORK-{period}-{id}',source=source,supersedes=None)
            command('progress_review',actor='reviewer',id=d['id']);command('progress_approve',actor='approver',id=d['id'])
            independent+=Decimal(weights[id])*fraction*100
        expected=(independent/sum((Decimal(v) for v in weights.values()),Decimal(0))).quantize(Decimal('.000001'))
        r=command('progress_report',date=day,reference=f'REPORT-{period}')
        assert Decimal(r['actual'])==expected;actuals.append(r['actual'])
    assert actuals==['12.500000','45.000000','75.000000']
    # Past reports remain the as-issued observations even after corrections.
    assert a.open_project('P')['progress_reports'][1]['actual']=='45.000000'
    command('schedule_activity',id='S5',duration=5,not_before=None,relationships=[{'pred':'S4','succ':'S5','type':'FS','lag':0}])
    assert a.project_schedule('P')['duration']==20 and a.open_project('P')['schedule_baselines'][0]==baseline
    assert a.open_project('P')['boq']==boq
    exports=[]
    for kind in ['wbs','activities','schedule','progress','curve']:
        for fmt in ['pdf','xlsx','docx','csv']:
            path=root/(kind+'.'+fmt);a.project_controls_report('P',kind,fmt,path,as_of=report_dates[-1]);exports.append(path.name)
    from app.project_controls_workspace import ProjectControlsWorkspace
    w=ProjectControlsWorkspace(a,'P');w.fields['report_date'].setText(report_dates[-1]);w.show();w.tabs.setCurrentIndex(1);qt.processEvents();w.grab().save(str(root/'gantt-workspace.png'))
    w.tabs.setCurrentIndex(0);qt.processEvents();w.grab().save(str(root/'wbs-workspace.png'));w.show_progress();w.tabs.setCurrentIndex(2);qt.processEvents();w.grab().save(str(root/'progress-workspace.png'));w.close();qt.processEvents()
    before=deepcopy(a.open_project('P'));snapshot=a.project_progress('P',as_of=report_dates[-1]);a.store.close();a=StructuralProApp(root/'engineering'/'db')
    assert a.open_project('P')==before and a.project_progress('P',as_of=report_dates[-1])==snapshot
    assert a.store.integrity_check()['ok'];a.store.close()
    result={'synthetic':True,'floors':5,'activities':15,'critical_ids':expected_critical,'duration_baseline':18,'duration_current':20,'actual_periods':actuals,'planned_final':snapshot['planned'],'variance_final':snapshot['variance'],
            'baseline_preserved':True,'boq_preserved':True,'reopen_equal':True,'sqlite_integrity':'ok','exports':exports,'date_contract':'ISO storage; Jalali display; start-of-day planned boundary','report_dates':report_dates}
    (root/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));return result

if __name__=='__main__':print(json.dumps(run(sys.argv[1]),ensure_ascii=False,indent=2))
