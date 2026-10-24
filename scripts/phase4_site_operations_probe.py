"""Explicit synthetic expansion of the immutable five-floor acceptance fixture."""
from copy import deepcopy
from decimal import Decimal,localcontext
from pathlib import Path
import hashlib,json
from core.platform.application import StructuralProApp
from core.projects.controls import boq_basis,digest

def run(root):
    from scripts.phase4_project_controls_probe import run as previous
    from PySide6.QtWidgets import QApplication
    qt=QApplication.instance() or QApplication([])
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    prior=previous(root/'prior');a=StructuralProApp(root/'prior'/'engineering'/'db')
    f=root/'explicit-site-fixture.txt';f.write_text('SYNTHETIC ONLY. Three crews capacity1, equipment capacity1. Attendance 2026-03-16 through 2026-05-31. Material user consumption rules: concrete 1m3/m3+2.5%; block12 count/m2 wall; tile1m2/m2 wall+7%; pipe0.5m/m2 wall. Stock opening2+receipt4-consume2+return1=5; explicit complete ledger. No real productivity, prices or engineering approval.')
    proof={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'reference':'SYNTHETIC SITE ONLY'}
    # Existing phase3 services supply a genuine fixture statement/ledger, never inferred payments.
    def ver():return a.open_project('P')['_meta']['version']
    docs=[{'ref':proof['reference'],'path':proof['path'],'sha256':proof['sha256']}]
    a.configure_statement_amendments('P',owner_id='synthetic-owner',establish_owner=True,expected_project_version=ver(),policy={'money':{'currency':'IRR','decimal_places':2,'rounding':'ROUND_HALF_UP'},'authorities':{'planner':['create'],'reviewer':['review'],'approver':['approve','post']}},source_documents=docs)
    a.configure_statement_workflow('P',actor='synthetic-owner',expected_version=ver(),source_documents=docs,terms={'contract_id':'SYNTHETIC-CONTRACT','currency':'IRR','advance_paid':'0','factor_basis':'base_rates_only','retention_rate':'0','advance_recovery_rate':'0','tax_rate':'0','insurance_rate':'0','other_deduction_rate':'0'})
    statement=a.statement_workflow('P','create',actor='planner',expected_version=ver(),reference='SYNTHETIC-STATEMENT',date='2026-04-30',current_quantities={'concrete':'1','formwork':'1','rebar':'1','wall':'1'})
    for op,actor in [('review','reviewer'),('approve','approver'),('issue','approver')]:a.statement_workflow('P',op,actor=actor,expected_version=ver(),id=statement['id'])
    for kind,amount in [('budget','10000'),('commitment','1000'),('cost','600')]:
        extra={'commitment_id':commitment_id} if kind=='cost' else {}
        rec=a.financial_command('P','create',actor='planner',expected_version=ver(),kind=kind,reference='SITE-FIXTURE-'+kind,amount=amount,currency='IRR',date='2026-04-30',counterparty='طرف حساب آزمایشی',description='ورودی آزمایشی صریح؛ بدون پرداخت فرضی',source_documents=docs,**extra)
        for op,actor in [('review','reviewer'),('approve','approver'),('post','approver')]:a.financial_command('P',op,actor=actor,expected_version=ver(),id=rec['id'])
        if kind=='commitment':commitment_id=rec['id']
    initial=deepcopy(a.open_project('P'));immutable={k:deepcopy(initial.get(k)) for k in ('boq','takeoffs','schedule_baselines','progress_reports','statement_periods','beam_amendments','financial_records')}
    def cmd(op,actor='planner',**data):return a.site_command('P',op,actor=actor,reason='داده آزمایشی صریح؛ پروژه واقعی نیست',expected_version=a.open_project('P')['_meta']['version'],**data)
    def issue(kind,id):
        for action,actor in [('review','reviewer'),('approve','approver'),('issue','issuer')]:cmd(kind+'_'+action,actor=actor,id=id)
    cmd('policy',actor='synthetic-owner',owner='synthetic-owner',establish_owner=True,source=proof,permissions={k:['planner','reviewer','approver','issuer'] for k in ['create','review','approve','issue','adjust','finance']})
    for id,kind,discipline in [('CS','crew','S'),('CA','crew','A'),('CM','crew','M'),('CRANE','equipment','S')]:
        cmd('resource_create',id=id,name='منبع آزمایشی '+id,kind=kind,capacity='1',unit='crew' if kind=='crew' else 'machine',discipline_id=discipline,subcontractor='پیمانکار آزمایشی',source=proof)
        cmd('resource_review',actor='reviewer',id=id);cmd('resource_approve',actor='approver',id=id)
        cmd('availability',id='AV-'+id,resource_id=id,start='2026-03-16',end='2026-05-31',state='present',capacity='1',confirmed=True,source=proof)
    schedule=a.project_schedule('P')
    for activity,resource in [('S1','CS'),('A1','CA'),('S2','CS'),('M1','CM')]:
        row=schedule['activities'][activity];id='AS-'+activity
        cmd('assign',id=id,activity_id=activity,resource_id=resource,start=row['start'],end=row['finish'],allocation='1',source=proof)
        cmd('assignment_review',actor='reviewer',id=id);cmd('assignment_approve',actor='approver',id=id)
        cmd('requirements',id='REQ-'+activity,activity_id=activity,resources=[{'resource_id':resource,'quantity':'1'}],materials=[],source=proof)
    # Independent interval oracle: A1 and S2 overlap on distinct floors/resources.
    assert schedule['activities']['A1']['start']==schedule['activities']['S2']['start']
    assert next(x for x in initial['project_schedule_tasks'] if x['id']=='A1')['floor_ids']!=next(x for x in initial['project_schedule_tasks'] if x['id']=='S2')['floor_ids']
    row=schedule['activities']['A1'];cmd('assign',id='OVERLAP',activity_id='A1',resource_id='CS',start=row['start'],end=row['finish'],allocation='1',source=proof)
    before=a.open_project('P')
    try:cmd('assignment_review',actor='reviewer',id='OVERLAP')
    except ValueError:pass
    else:raise AssertionError('double booking accepted')
    assert a.open_project('P')==before
    weekly=a.site_lookahead('P',start='2026-03-16',days=7);fortnight=a.site_lookahead('P',start='2026-03-16',days=14)
    assert weekly['end']=='2026-03-22' and fortnight['end']=='2026-03-29'
    assert '2026-03-23' not in [d for x in fortnight['activities'] for d in x['work_dates']]
    cmd('resource_event',id='ABSENT',resource_id='CS',start='2026-03-17',end='2026-03-17',state='absent',source=proof)
    assert a.site_lookahead('P',start='2026-03-16',days=7)['activities'][0]['status']=='resource_conflict'
    cmd('resource_event',id='BACK',resource_id='CS',start='2026-03-17',end='2026-03-17',state='released',reference_id='ABSENT',source=proof)
    material_results=[]
    for code,item,unit,ratio,waste,activity in [('CON','concrete','m3','1','2.5','S1'),('BLK','wall','count','12','0','A2'),('TIL','wall','m2','1','7','A2'),('PIP','wall','m','.5','0','A2')]:
        row=next(x for x in initial['boq'] if x['item_code']==item);rid='RULE-'+code;nid='NEED-'+code
        cmd('material_rule_create',id=rid,material_code=code,specification='مصالح آزمایشی '+code,base_unit=row['unit'],material_unit=unit,ratio=ratio,waste_percent=waste,source_version='SYNTHETIC-1',source=proof)
        cmd('material_rule_review',actor='reviewer',id=rid);cmd('material_rule_approve',actor='approver',id=rid)
        floor='L1' if activity=='S1' else 'L2'
        n=cmd('material_need',id=nid,rule_id=rid,source_ids=row['source_ids'],item_code=item,activity_id=activity,floor_ids=[floor],zone_ids=[],period_start='2026-03-16',period_end='2026-05-31',quantity_approval={'source':proof,'approved_by':'synthetic-quantity-reviewer','source_version':'1','basis_digest':boq_basis(initial,row)})
        expected=Decimal(str(row['quantity']))*Decimal(ratio)*(1+Decimal(waste)/100)
        assert Decimal(n['quantity'])==expected
        stock_args=dict(material_code=code,unit=unit,date='2026-03-16',source=proof,confirmed=True)
        if code!='PIP':
            cmd('inventory_opening',id='OPEN-'+code,reference='OPEN-'+code,quantity='2',**stock_args)
            cmd('inventory_receipt',id='RECEIPT-'+code,reference='RECEIPT-'+code,quantity='4',**stock_args)
            cmd('inventory_consume',id='USE-'+code,reference='USE-'+code,quantity='2',requirement_id=nid,**stock_args)
            cmd('inventory_return',id='RETURN-'+code,reference='RETURN-'+code,quantity='1',direction='stock_in',reference_id='USE-'+code,**stock_args)
            cmd('inventory_close',id='CLOSE-'+code,material_code=code,unit=unit,period_start='2026-03-16',period_end='2026-05-31',source=proof,confirmed=True)
        view=next(x for x in a.site_materials('P',as_of='2026-03-16')['requirements'] if x['id']==nid)
        if code=='PIP':assert view['shortage'] is None
        else:assert Decimal(view['on_hand'])==5 and Decimal(view['shortage'])==max(Decimal(0),expected-6)
        material_results.append({'material':code,'need':str(expected),'shortage':view['shortage']})
    financial_before={k:deepcopy(a.open_project('P').get(k)) for k in ('financial_records','commitment_entries','statement_periods','boq')}
    buy=cmd('purchase_draft',id='PURCHASE-BLK',requirement_id='NEED-BLK',as_of='2026-03-16',owner='planner')
    assert buy['price'] is None
    assert all(a.open_project('P').get(k)==v for k,v in financial_before.items())
    # Daily record is an observation, not automatically approved progress.
    day='2026-04-30';daily_data=dict(activity_id='M5',date=day,summary='کارکرد آزمایشی تأسیسات',location='طبقه پنجم',crew_ids=['CM'],equipment_ids=[],material_ids=[],human_count=3,quantity='1',unit='m',technical_notes='ورودی آزمایشی مستند؛ بدون ادعای تأیید مهندسی واقعی',source=proof,attachments=[proof])
    daily=cmd('daily_create',reference='DAILY-1',**daily_data);issue('daily',daily['id'])
    assert a.open_project('P')['progress_reports']==initial['progress_reports']
    previous_doc=next(x for x in reversed(initial['progress_documents']) if x['activity_id']=='M5' and x['status']=='approved')
    work=cmd('daily_transfer',actor='approver',id=daily['id'],previous_progress_id=previous_doc['id'],previous_cumulative_quantity=previous_doc['quantity'],cumulative_quantity=str(Decimal(previous_doc['quantity'])+1),quantity_semantics='cumulative',source=proof,reference='DAILY-WORK-1')
    assert work['status']=='draft'
    a.project_control_command('P','progress_review',actor='reviewer',reason='fixture',expected_version=a.open_project('P')['_meta']['version'],id=work['id'])
    a.project_control_command('P','progress_approve',actor='planner',reason='fixture',expected_version=a.open_project('P')['_meta']['version'],id=work['id'])
    amendment=cmd('daily_amend',id=daily['id'],reference='DAILY-CORRECTION',**{**daily_data,'quantity':'2'});issue('daily',amendment['id'])
    amended_work=cmd('daily_transfer',actor='approver',id=amendment['id'],previous_progress_id=previous_doc['id'],previous_cumulative_quantity=previous_doc['quantity'],cumulative_quantity=str(Decimal(previous_doc['quantity'])+2),quantity_semantics='cumulative',source=proof,reference='DAILY-WORK-CORRECTION',supersedes=work['id'])
    for op,actor in [('progress_review','reviewer'),('progress_approve','planner')]:a.project_control_command('P',op,actor=actor,reason='fixture correction',expected_version=a.open_project('P')['_meta']['version'],id=amended_work['id'])
    obstacle=cmd('obstacle_create',activity_id='S1',title='توقف آزمایشی',owner='planner',date='2026-03-16',due_date='2026-03-17',location='طبقه یک',source=proof)
    cmd('obstacle_resolve',id=obstacle['id'],date='2026-03-18',resolution='رفع مستند مانع',source=proof)
    meeting=cmd('meeting_create',date=day,reference='MEETING-1',title='جلسه هماهنگی آزمایشی',participants=['planner','reviewer'],decisions='پیگیری نقشه اجرایی',actions=[{'title':'بررسی نقشه','owner':'planner','due_date':'2026-05-01','activity_id':'M5','source':proof}],source=proof,attachments=[proof]);issue('meeting',meeting['id'])
    rfi=cmd('correspondence_create',kind='rfi',date=day,reference='RFI-1',title='پرسش فنی آزمایشی',recipient='reviewer',technical_notes='نیاز به تصمیم صریح',activity_id='M5',source=proof,attachments=[proof]);issue('correspondence',rfi['id'])
    # W4 binds actual issued sources; no fake statement or signature is added.
    p=a.open_project('P');amendment_source=next(iter(p['beam_amendments'].values()))
    sources=[]
    for key,row in [('project_daily_reports',p['project_daily_reports'][1]),('project_meetings',p['project_meetings'][0]),('site_correspondence',p['site_correspondence'][0]),('beam_amendments',amendment_source),('progress_reports',p['progress_reports'][-1])]:sources.append({'collection':key,'id':row['id'],'version':row.get('version',1),'sha256':digest(row)})
    period=p['statement_periods'][0];sources.append({'collection':'statement_periods','id':str(period['number']),'version':1,'sha256':digest(period)})
    package=cmd('package_create',reference='W4-1',date='2026-05-02',title='بسته آزمایشی دفتر فنی',template='site-office',template_version='1',sources=sources);issue('package',package['id'])
    exports=[]
    for kind in ['lookahead','resources','materials','purchases','daily','obstacles','meetings','correspondence','package','dashboard']:
        for fmt in ['pdf','xlsx','docx','csv']:
            path=root/(kind+'.'+fmt);a.site_report('P',kind,fmt,path,as_of='2026-05-02');assert path.stat().st_size>100;exports.append(path.name)
    from app.site_operations_workspace import SiteOperationsWorkspace
    w=SiteOperationsWorkspace(a,'P');w.fields['as_of'].setText('2026-05-02');w.show_dashboard();w.tabs.setCurrentIndex(2);w.show();qt.processEvents();w.grab().save(str(root/'site-dashboard.png'));w.tabs.setCurrentIndex(0);qt.processEvents();w.grab().save(str(root/'site-forms.png'));w.close();qt.processEvents()
    before=deepcopy(a.open_project('P'));dash=a.site_dashboard('P',as_of='2026-05-02')
    assert len(dash['office']['overdue_actions'])==1
    assert Decimal(str(dash['finance']['budget']))==10000 and Decimal(str(dash['finance']['actual_cost']))==600 and Decimal(str(dash['finance']['budget_variance']))==9400
    assert dash['finance']['paid'] is None
    assert all(before.get(k)==v for k,v in immutable.items())
    a.store.close();a=StructuralProApp(root/'prior'/'engineering'/'db')
    assert a.open_project('P')==before and a.site_dashboard('P',as_of='2026-05-02')==dash
    assert a.store.integrity_check()['ok'];a.store.close()
    receipt={'synthetic':True,'prior':prior,'three_crews':True,'equipment':True,'parallel_floors':True,'overbook_blocked':True,'weekly_end':weekly['end'],'fortnight_end':fortnight['end'],'material_oracle':material_results,'purchase_no_financial_effect':True,'daily_transfer_draft_then_reviewed':True,'daily_correction_supersedes':work['id'],'package_sources':sources,'immutable_originals':True,'reopen_equal':True,'sqlite_integrity':'ok','exports':exports}
    (root/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2));return receipt
