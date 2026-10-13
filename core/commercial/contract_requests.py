"""Immutable documented proposals; never pretend a changed contract is posted.

Contract application needs versioned effective BOQ/pricebook integration. Until
that exists, preview and DRAFT are available; approval/POST fail closed even if
an owner has configured an amendment policy. No cash ledger is changed.
"""
from copy import deepcopy
from uuid import uuid4
from datetime import datetime,timezone
import csv,io,base64
from decimal import Decimal
from core.commercial.statement_amendment import documents,digest,summary,cumulative_quantities
from core.commercial.exact_values import number,wire,exact
from core.takeoff.units import normalize_unit

@exact
def contract_preview(project,lines,source_documents):
    docs=documents(source_documents);refs={d['ref']:d for d in docs};boq={}
    for row in project.get('boq',[]):
        code=row.get('price_code')
        if not code or code in boq:raise ValueError('هویت ردیف قرارداد مبهم است')
        boq[code]=row
    if not lines:raise ValueError('ردیف تغییر قرارداد صریح لازم است')
    totals=cumulative_quantities(project);out=[];seen=set();original_total=new_total=Decimal(0)
    for change in lines:
        required={'price_code','source_id','quantity','unit_price','unit','detail_ref','rate_ref'}
        if not isinstance(change,dict) or set(change)!=required:raise ValueError('ساختار درخواست تغییر قرارداد نامعتبر است')
        code=change['price_code']
        if code in seen or code not in boq:raise ValueError('کد قرارداد نامعتبر یا تکراری است')
        seen.add(code);old=boq[code]
        if change['source_id'] not in old.get('source_ids',[]):raise ValueError('منبع فیزیکی قرارداد نامعتبر است')
        if change['detail_ref'] not in refs:raise ValueError('دیتایل مستند تغییر مقدار الزامی است')
        if normalize_unit(change['unit'])!=normalize_unit(old['unit']):raise ValueError('تغییر واحد نیازمند قرارداد مستقل است')
        q=number(change['quantity'],'مقدار قرارداد');price=number(change['unit_price'],'نرخ پیشنهادی')
        if q<totals.get(code,0):raise ValueError('مقدار پیشنهادی کمتر از کارکرد خالص صادرشده است')
        if price!=number(old['unit_price'],'نرخ اولیه'):
            if change['rate_ref'] not in refs:raise ValueError('تغییر نرخ بدون منبع معتبر مجاز نیست')
            raw=base64.b64decode(refs[change['rate_ref']]['snapshot_base64']).decode('utf-8-sig')
            candidates=[r for r in csv.DictReader(io.StringIO(raw)) if r.get('code')==code]
            if len(candidates)!=1 or normalize_unit(candidates[0].get('unit',''))!=normalize_unit(old['unit']) or number(candidates[0].get('unit_price'),'نرخ منبع')!=price:
                raise ValueError('نرخ/واحد پیشنهادی با منبع قیمت مطابقت ندارد')
        original=number(old['quantity'],'مقدار اولیه')*number(old['unit_price'],'نرخ اولیه');revised=q*price
        original_total+=original;new_total+=revised
        out.append({**change,'original_quantity':old['quantity'],'original_unit_price':old['unit_price'],'original_amount':wire(original),'proposed_amount':wire(revised),'delta':wire(revised-original)})
    return {'status':'DRAFT_NOT_PAYABLE','lines':out,'original_changed_lines_total':wire(original_total),'proposed_changed_lines_total':wire(new_total),'delta':wire(new_total-original_total),'source_documents':docs,'remaining_gates':['OWNER_AUTHORITY','INDEPENDENT_REVIEW','VERSIONED_CONTRACT_APPLICATION_NOT_IMPLEMENTED']}

@exact
def settlement_preview(project,receipt_ids):
    if not isinstance(receipt_ids,list) or any(isinstance(i,bool) or not isinstance(i,int) for i in receipt_ids) or len(set(receipt_ids))!=len(receipt_ids):raise ValueError('شناسه دریافت‌های مرتبط باید صریح و یکتا باشد')
    receipts={r['id']:r for r in project.get('receipt_entries',[])}
    if any(i not in receipts for i in receipt_ids):raise ValueError('دریافت واقعی مرتبط یافت نشد')
    if project.get('contract_addenda'):raise ValueError('اثر الحاقیه ناشناخته است؛ تسویه قطعی مسدود است')
    original=changes=Decimal(0)
    for period in project.get('statement_periods',[]):
        original+=number(period['payable_current'],'اصل پرداختنی')
        if project.get('statement_amendment_policy'):
            s=summary(project,period['number']);changes+=number(s['amendment_deltas']['payable_current'],'اصلاحیه',True)
    received=sum((number(receipts[i]['amount'],'دریافتی') for i in receipt_ids),Decimal(0))
    commitments=sum((number(c['amount'],'تعهد')-number(c['paid_amount'],'پرداخت تعهد') for c in project.get('commitment_entries',[])),Decimal(0))
    return wire({'status':'PREVIEW_NOT_SETTLED','direction':'contractor_receivable','original_issued_payable':original,'posted_amendment_delta':changes,'net_issued_payable':original+changes,'selected_receipt_ids':receipt_ids,'received':received,'balance_receivable':original+changes-received,'unpaid_commitments_separate':commitments,'contract_change_requests_not_posted':len(project.get('contract_change_requests',[])),'financial_policy_status':'CONFIGURED' if project.get('statement_amendment_policy') else 'BLOCKED_OWNER_POLICY_REQUIRED'})

def proposal(project,command):
    updated=deepcopy(project);updated.pop('_meta',None)
    if not isinstance(command['actor'],str) or not command['actor'].strip() or not isinstance(command['reason'],str) or not command['reason'].strip():raise ValueError('مسئول درخواست و علت صریح لازم است')
    preview=contract_preview(project,command['lines'],command['source_documents']) if command['kind']=='contract' else settlement_preview(project,command['receipt_ids'])
    if command['kind'] not in {'contract','settlement'}:raise ValueError('نوع سند نامعتبر است')
    if command['kind']=='settlement':preview['source_documents']=documents(command['source_documents'])
    key='contract_change_requests' if command['kind']=='contract' else 'settlement_requests';docs=updated.setdefault(key,[])
    doc={'id':command['id'],'revision':1,'status':'DRAFT','project_id':project['id'],'created_by':command['actor'],'reason':command['reason'],'created_at':command['at'],'project_basis_digest':digest({k:v for k,v in project.items() if k!='_meta'}),'preview':preview}
    doc['content_digest']=digest(doc);docs.append(doc);return updated,doc

def guard(previous,updated,command):
    keys=['contract_change_requests','settlement_requests']
    if all(previous.get(k)==updated.get(k) for k in keys):return
    if command is None:raise ValueError('تغییر مستقیم پیش‌نویس مالی مجاز نیست')
    expected,_=proposal(previous,command)
    actual=deepcopy(updated);actual.pop('_meta',None)
    if digest(expected)!=digest(actual):raise ValueError('درخواست مالی با مبنای معتبر مطابقت ندارد')

def create_request(store,pid,kind,actor,reason,source_documents,expected_project_version,**data):
    p=store.get(pid)
    if p is None:raise KeyError(pid)
    if isinstance(expected_project_version,bool) or not isinstance(expected_project_version,int) or p['_meta']['version']!=expected_project_version:raise RuntimeError('نسخه پروژه تغییر کرده است')
    command={**data,'kind':kind,'actor':actor,'reason':reason,'source_documents':source_documents,'id':uuid4().hex,'at':datetime.now(timezone.utc).isoformat()}
    updated,doc=proposal(p,command)
    from core.platform.concurrency import begin_write
    store.save(pid,updated,expected_digest=begin_write({k:v for k,v in p.items() if k!='_meta'}),financial_request_command=command)
    return deepcopy(doc)

def post_request(*args,**kwargs):
    raise ValueError('BLOCKED: اعمال نسخه‌دار قرارداد و تأیید مالی مستقل هنوز پیاده‌سازی نشده‌اند؛ این سند فقط پیش‌نویس است')
