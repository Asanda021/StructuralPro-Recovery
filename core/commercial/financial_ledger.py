"""Project financial ledger with traceable commitments and receivables."""
from dataclasses import dataclass
from typing import Iterable
from core.commercial.exact_values import number,wire,exact

@dataclass(frozen=True)
class LedgerEntry:
    kind:str; amount:float; reference:str; description:str=""

@exact
def summarize(entries:Iterable[LedgerEntry])->dict:
    totals={"receivable":0,"commitment":0,"payment":0,"other":0}
    rows=[]
    for e in entries:
        amount=number(e.amount,"amount"); kind=e.kind if e.kind in totals else "other"
        totals[kind]+=amount; rows.append({"kind":kind,"amount":amount,"reference":e.reference,"description":e.description})
    totals["net_position"]=totals["receivable"]-totals["commitment"]-totals["payment"]
    return wire({"entries":rows,"totals":totals})

# Commands authorize entries in the existing project financial collections.
# Pending records are evidence/envelopes, not another ledger or money engine.
from copy import deepcopy
from core.commercial.statement_amendment import authorize,policy,documents,check_documents,digest,_text
from core.commercial.statement import valid_date

COLLECTIONS={'budget':'financial_budget','commitment':'commitment_entries',
             'cost':'cost_entries','payment':'payment_entries','receipt':'receipt_entries'}
GUARDED=tuple(COLLECTIONS.values())+('financial_records','financial_reversals','payment_allocations')


def active_records(project):
    reversed_ids={r['target_id'] for r in project.get('financial_reversals',[])}
    return [r for r in project.get('financial_records',[]) if r['status']=='POSTED' and r['id'] not in reversed_ids]


@exact
def verified_snapshot(project):
    records=active_records(project)
    def total(kind):
        rows=[r for r in records if r['kind']==kind]
        return sum((number(r['amount'],'مبلغ') for r in rows),number(0,'صفر')) if rows else None
    budget=total('budget');cost=total('cost');paid=total('payment');received=total('receipt');committed=total('commitment')
    # Missing dimensions remain unknown. Zero residuals after a documented reversal are known.
    ever={r['kind'] for r in project.get('financial_records',[]) if r['status']=='POSTED'}
    if paid is None and 'payment' in ever:paid=number(0,'صفر')
    if received is None and 'receipt' in ever:received=number(0,'صفر')
    payments=paid if paid is not None else number(0,'صفر')
    linked_payments=sum((number(r['amount'],'پرداخت') for r in records if r['kind']=='payment' and r.get('commitment_id')),number(0,'صفر'))
    periods=project.get('statement_periods',[]);net=None
    if periods:
        from core.commercial.statement_amendment import summary
        net=sum((number(summary(project,p['number'])['net']['payable_current'],'خالص') if any(x.get('status')=='POSTED' for x in project.get('statement_amendments',[])) else number(p['payable_current'],'خالص') for p in periods),number(0,'صفر'))
    estimate=(project.get('estimate') or {}).get('cost',{}).get('grand_total')
    return wire({'project_id':project['id'],'currency':policy(project)['money']['currency'],
        'estimate':estimate,'budget':budget,'commitments':committed,'actual_cost':cost,'paid':paid,'received':received,
        'debt':cost-payments if cost is not None else None,
        'unpaid_commitments':committed-linked_payments if committed is not None else None,
        'budget_variance':budget-cost if budget is not None and cost is not None else None,
        'over_budget':cost>budget if budget is not None and cost is not None else None,
        'estimate_variance':number(estimate,'برآورد')-cost if estimate is not None and cost is not None else None,
        'statement_net':net,'receivable':net-(received or 0) if net is not None else None,
        'cash_net':(received or 0)-(paid or 0) if received is not None or paid is not None else None,
        'documents':deepcopy(records),'reversals':deepcopy(project.get('financial_reversals',[])),
        'authority_status':'LOCAL_OWNER_DOCUMENT_ATTRIBUTION_NOT_AUTHENTICATION',
        'missing_message':'اطلاعات کافی ثبت نشده است'})


def _lookup(project,id,kind):
    matches=[r for r in active_records(project) if r['id']==id and r['kind']==kind]
    if len(matches)!=1:raise ValueError('سند مرجع قطعی یافت نشد یا برگشت خورده است')
    return matches[0]


@exact
def ledger_dispatch(previous,command):
    p=deepcopy(previous);p.pop('_meta',None);actor=command['actor'];op=command['op'];at=command['at']
    records=p.setdefault('financial_records',[])
    if op=='create':
        authorize(p,actor,'create');kind=command['kind']
        if kind not in COLLECTIONS:raise ValueError('نوع ثبت مالی نامعتبر است')
        reference=_text(command['reference'],'مرجع یکتای سند')
        legacy_refs={str(r.get('reference') or r.get('document_number') or '').strip()
                     for collection in tuple(COLLECTIONS.values())+('financial_documents',) for r in p.get(collection,[])}
        if reference in legacy_refs or any(r['reference']==reference for r in records) or any(r['reference']==reference for r in p.get('financial_reversals',[])):
            raise ValueError('مرجع سند مالی تکراری است')
        currency=command['currency']
        if currency not in {'IRR','IRT'} or currency!=policy(p)['money']['currency']:raise ValueError('واحد پول با سیاست پروژه ناسازگار است')
        amount=number(command['amount'],'مبلغ')
        if amount<=0:raise ValueError('مبلغ باید مثبت باشد؛ برگشت از مسیر مستقل لازم است')
        date=valid_date(command['date'])
        r={'id':command['id'],'project_id':p['id'],'kind':kind,'reference':reference,'amount':wire(amount),
           'currency':currency,'date':date,'counterparty':_text(command['counterparty'],'طرف حساب'),
           'description':_text(command['description'],'شرح و مرجع قرارداد'),'status':'DRAFT','created_by':actor,
           'source_documents':documents(command['source_documents']),
           'events':[{'op':op,'actor':actor,'at':at}]}
        for key in ('commitment_id','cost_id','statement_no'):
            if command.get(key) is not None:r[key]=command[key]
        if kind=='budget' and (any(x['kind']=='budget' for x in active_records(p)) or any(x['kind']=='budget' and x['status'] in {'DRAFT','REVIEWED','APPROVED'} for x in records)):raise ValueError('بودجه قبلی باید با سند برگشت مستقل اصلاح شود')
        records.append(r);return p
    matches=[r for r in records if r['id']==command['id']]
    if len(matches)!=1:raise ValueError('سند مالی یافت نشد')
    r=matches[0]
    if op=='reverse':
        authorize(p,actor,'post')
        _lookup(p,r['id'],r['kind'])
        reference=_text(command['reference'],'مرجع برگشت');reason=_text(command['reason'],'علت برگشت')
        if reference in {x['reference'] for x in records+p.get('financial_reversals',[])}:raise ValueError('مرجع برگشت تکراری است')
        if any(x.get('commitment_id')==r['id'] or x.get('cost_id')==r['id'] for x in active_records(p)):
            raise ValueError('ابتدا اسناد وابسته باید به‌صورت مستقل برگشت داده شوند')
        p.setdefault('financial_reversals',[]).append({'id':command['reversal_id'],'target_id':r['id'],'reference':reference,
            'reason':reason,'date':valid_date(command['date']),'actor':actor,'at':at,'original_sha256':digest(r),
            'source_documents':documents(command['source_documents'])})
        return p
    check_documents(r['source_documents'])
    if op=='review':
        authorize(p,actor,'review')
        if r['status']!='DRAFT' or actor==r['created_by']:raise ValueError('تأیید مستقل پیش‌نویس لازم است')
        r['status']='REVIEWED';r['reviewed_by']=actor
    elif op=='approve':
        authorize(p,actor,'approve')
        if r['status']!='REVIEWED' or actor in {r['created_by'],r['reviewed_by']}:raise ValueError('تأیید مستقل سند بازبینی‌شده لازم است')
        r['status']='APPROVED';r['approved_by']=actor
    elif op=='post':
        authorize(p,actor,'post')
        if r['status']!='APPROVED' or actor in {r['created_by'],r['reviewed_by']}:raise ValueError('ثبت مستقل سند تأییدشده لازم است')
        amount=number(r['amount'],'مبلغ')
        if r['kind'] in {'cost','payment'}:
            commitment=_lookup(p,r.get('commitment_id'),'commitment')
            if r['kind']=='cost':
                used=sum((number(x['amount'],'هزینه') for x in active_records(p) if x['kind']=='cost' and x.get('commitment_id')==commitment['id']),number(0,'صفر'))
                if used+amount>number(commitment['amount'],'تعهد'):raise ValueError('هزینه از سقف تعهد بیشتر است')
            else:
                cost=_lookup(p,r.get('cost_id'),'cost')
                if cost.get('commitment_id')!=commitment['id']:raise ValueError('هزینه و تعهد پرداخت ناسازگارند')
                used=sum((number(x['amount'],'پرداخت') for x in active_records(p) if x['kind']=='payment' and x.get('cost_id')==cost['id']),number(0,'صفر'))
                if used+amount>number(cost['amount'],'هزینه'):raise ValueError('پرداخت بیش از مانده سند است')
        if r['kind']=='receipt':
            periods=[x for x in p.get('statement_periods',[]) if x['number']==r.get('statement_no')]
            if len(periods)!=1:raise ValueError('دریافت باید به صورت‌وضعیت صادرشده متصل باشد')
            from core.commercial.statement_amendment import summary
            net=number(summary(p,r['statement_no'])['net']['payable_current'],'خالص')
            used=sum((number(x['amount'],'دریافت') for x in active_records(p) if x['kind']=='receipt' and x.get('statement_no')==r['statement_no']),number(0,'صفر'))
            if used+amount>net:raise ValueError('دریافت از مانده صورت‌وضعیت بیشتر است')
        r['status']='POSTED';r['posted_by']=actor
        row=deepcopy(r)
        # Existing readers keep their established field names and exact values.
        row.update(category='سایر',notes=r['description'],document_id=None,counterparty_id=None)
        if r['kind']=='budget':row.update(code=r['reference'],planned=r['amount'])
        if r['kind']=='commitment':row.update(paid_amount=0,due_date=r['date'])
        if r['kind']=='payment':row['status']='unallocated'
        p.setdefault(COLLECTIONS[r['kind']],[]).append(row)
    else:raise ValueError('عملیات سند مالی نامعتبر است')
    r['events'].append({'op':op,'actor':actor,'at':at})
    return p


def ledger_guard(previous,updated,command):
    # Existing legacy projects remain readable; entering the guarded workflow
    # freezes all its financial collections against raw/legacy writes.
    changed=any(previous.get(k)!=updated.get(k) for k in ('financial_records','financial_reversals'))
    if previous.get('financial_records'):changed=changed or any(previous.get(k)!=updated.get(k) for k in GUARDED)
    if not changed:return
    if not command or command.get('domain')!='ledger':raise ValueError('سند مالی قطعی فقط با ثبت یا برگشت مستند تغییر می‌کند')
    expected=ledger_dispatch(previous,command);clean=deepcopy(updated);clean.pop('_meta',None)
    if digest(clean)!=digest(expected):raise ValueError('ثبت مالی با فرمان مجاز مطابقت ندارد')


def financial_projection(project):
    """Read-only legacy reader projection, keeping original rows in storage."""
    result=deepcopy(project);reversed_ids={x['target_id'] for x in project.get('financial_reversals',[])}
    for key in COLLECTIONS.values():
        if key in result:result[key]=[r for r in result[key] if r.get('id') not in reversed_ids]
    return result


@exact
def settlement_guard(project):
    from core.commercial.statement_amendment import summary
    receipts={}
    for r in active_records(project):
        if r['kind']=='receipt':receipts[r['statement_no']]=receipts.get(r['statement_no'],0)+number(r['amount'],'دریافت')
    for no,amount in receipts.items():
        if amount>number(summary(project,no)['net']['payable_current'],'خالص'):
            raise ValueError('اصلاحیه باعث دریافت بیش از خالص می‌شود؛ ابتدا برگشت دریافت لازم است')
