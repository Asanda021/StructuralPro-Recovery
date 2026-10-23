"""Commercial payment statement with transparent contractual deductions."""
from __future__ import annotations
from typing import Iterable
from core.commercial.exact_values import number,wire,exact
from core.projects.statement_engine import StatementLine,build_statement

@exact
def build_payment_statement(contract,current:Iterable[StatementLine],*,previous_paid=0.0,
                            advance_recovery_rate=0.0,other_deduction_rate=0.0):
    errors=contract.validate()
    if errors: raise ValueError("; ".join(errors))
    base=build_statement(current,retention_rate=contract.retention_rate,
        advance_recovery_rate=advance_recovery_rate,
        other_deduction_rate=other_deduction_rate,advance_paid=contract.advance_paid)
    gross=number(base['gross_current'],'gross_current');commercial_base=contract.commercial_total(gross)
    tax=commercial_base*number(contract.tax_rate,'tax');insurance=commercial_base*number(contract.insurance_rate,'insurance')
    payable=number(base['payable'],'payable',True)+tax-insurance;paid=number(previous_paid,'previous_paid')
    return wire({**base,'contract_id':contract.contract_id,'contract_total':contract.total(),
        'commercial_base_current':gross,'commercial_total_current':commercial_base,'tax':tax,'insurance':insurance,'payable':payable,
        'previous_paid':paid,'balance_after_current':contract.commercial_total()-paid-payable,
        'financial_policy_status':'LEGACY_PREVIEW_NOT_FINANCIALLY_APPROVED',
        'commercial_factors':{'overhead_rate':contract.overhead_rate,'regional_rate':contract.regional_rate,
            'retention_rate':contract.retention_rate,'tax_rate':contract.tax_rate,'insurance_rate':contract.insurance_rate}})

class PaymentStatement:
    def __init__(self,contract): self.contract=contract
    def build(self,lines,**kwargs): return build_payment_statement(self.contract,lines,**kwargs)

# Guarded lifecycle over the existing statement_periods and amendment engine.
# Actor names are attributed through owner documents, never authenticated here.
from copy import deepcopy
from datetime import date as _date
from core.commercial.statement_amendment import (
    authorize, policy, documents, check_documents, digest, _text, cumulative_quantities, _money,
)


def valid_date(value):
    value=_text(value,'تاریخ میلادی سند')
    try: parsed=_date.fromisoformat(value)
    except (ValueError,TypeError) as exc: raise ValueError('تاریخ سند نامعتبر است؛ YYYY-MM-DD لازم است') from exc
    if parsed.isoformat()!=value: raise ValueError('تاریخ سند باید YYYY-MM-DD باشد')
    return value


@exact
def statement_rows(project):
    """Compatible price-code projection; original BOQ/source rows stay intact."""
    from core.takeoff.units import normalize_unit
    groups={}
    for original in project.get('boq',[]):
        row=deepcopy(original);code=row['price_code'];unit=normalize_unit(row['unit'])
        if number(row.get('factor',1),'ضریب ردیف')!=1 or number(row.get('waste_percent',0),'پرت') or number(row.get('allowance_quantity',0),'اضافه مقدار'):
            raise ValueError('مبنای کارکرد دارای پرت یا ضریب ردیف نیازمند قرارداد صریح مستقل است')
        if code in groups:
            target=groups[code]
            if unit!=normalize_unit(target['unit']) or number(row['unit_price'],'نرخ')!=number(target['unit_price'],'نرخ'):
                raise ValueError('کد مشترک با واحد یا نرخ ناسازگار قابل جمع نیست')
            target['quantity']=wire(number(target['quantity'],'مقدار')+number(row['quantity'],'مقدار'))
            target['source_ids']=sorted(set(target.get('source_ids',[])+row.get('source_ids',[])))
            target['source_rows'].append(row)
        else:
            row['source_rows']=[deepcopy(original)];groups[code]=row
    return list(groups.values())


@exact
def statement_factor_basis(p,t):
    multiplier=number('1','ضریب')
    factor_digest=None
    if t['factor_basis']=='reviewed_sequential_factors':
        import hashlib,json
        from pathlib import Path
        review=p.get('factor_review')
        if not review or review.get('status')!='approved':raise ValueError('ضرایب بازبینی‌شده موجود نیست')
        raw=Path(review['path']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=review['sha256']:raise ValueError('مدرک ضرایب تغییر کرده است')
        data=json.loads(raw)
        if any(review.get(k)!=v for k,v in data.items()) or review['currency']!=t['currency'] or review['pricebook_sha256']!=p['user_pricebook_review']['sha256']:
            raise ValueError('ضرایب با قرارداد یا فهرست‌بها سازگار نیست')
        for item in data['factors']:multiplier*=1+number(item['rate'],'ضریب')
        factor_digest=digest(p['factor_review'])
    return multiplier,factor_digest


@exact
def statement_dispatch(previous, command):
    from core.commercial.progress import build_progress
    from core.reports.aec_office_package import audit_boq
    from core.projects.store import _contract_basis
    p=deepcopy(previous);p.pop('_meta',None)
    op=command['op'];actor=command['actor'];at=command['at']
    if op=='configure':
        if p.get('statement_workflow_terms'):raise ValueError('شرایط قرارداد ثبت‌شده قابل بازنویسی نیست')
        if actor!=policy(p)['owner_id']:raise ValueError('مجوز مستند مالک لازم است')
        t=deepcopy(command['terms'])
        required={'contract_id','currency','advance_paid','factor_basis','retention_rate','advance_recovery_rate','tax_rate','insurance_rate','other_deduction_rate'}
        if set(t)!=required:raise ValueError('تمام شرایط قرارداد و نرخ صفرِ صریح الزامی است')
        _text(t['contract_id'],'شماره قرارداد')
        if t['currency'] not in {'IRR','IRT'} or t['currency']!=policy(p)['money']['currency']:
            raise ValueError('واحد پول قرارداد و سیاست مالی ناسازگار است')
        if (p.get('user_pricebook_review') or {}).get('currency') not in {None,t['currency']}:
            raise ValueError('واحد پول فهرست‌بها ناسازگار است')
        if t['factor_basis'] not in {'base_rates_only','reviewed_sequential_factors'}:
            raise ValueError('مبنای ضرایب قرارداد باید صریح باشد')
        for key in required-{'contract_id','currency','factor_basis'}:
            t[key]=format(number(t[key],key),'f')
            if key.endswith('_rate') and number(t[key],key)>1:raise ValueError('نرخ باید بین صفر و یک باشد')
        if p.get('statement_periods') and t['factor_basis']!='base_rates_only':
            raise ValueError('تغییر مبنای ضرایب سوابق صادرشده نیازمند الحاقیه است')
        recovered=sum((number(x['advance_recovery'],'استهلاک') for x in p.get('statement_periods',[])),number(0,'صفر'))
        for change in p.get('statement_amendments',[]):
            if change.get('status')=='POSTED':recovered+=number(change['deltas']['advance_recovery'],'اصلاح استهلاک',True)
        if number(t['advance_paid'],'پیش‌پرداخت')<recovered:raise ValueError('پیش‌پرداخت کمتر از استهلاک ثبت‌شده است')
        p['statement_workflow_terms']={'terms':t,'source_documents':documents(command['source_documents']),'owner':actor,'at':at}
        return p
    config=p.get('statement_workflow_terms')
    if not config:raise ValueError('شرایط مستند صورت‌وضعیت تنظیم نشده است')
    check_documents(config['source_documents']);t=config['terms']
    records=p.setdefault('statement_workflow',[])
    if op=='create':
        authorize(p,actor,'create');reference=_text(command['reference'],'شماره سند')
        if any(d['reference']==reference for d in records):raise ValueError('شماره سند صورت‌وضعیت تکراری است')
        date=valid_date(command['date'])
        if records and date<max(d['date'] for d in records):raise ValueError('تاریخ دوره از سند قبلی قدیمی‌تر است')
        audit_boq(p,require_pricebook=True)
        previous_q=cumulative_quantities(p);quantities=command['current_quantities']
        payable_rows=statement_rows(p)
        codes=[r.get('price_code') for r in payable_rows]
        if len(codes)!=len(set(codes)):raise ValueError('کد قیمت بین ردیف‌های BOQ مبهم است؛ نگاشت مستقل لازم است')
        if set(quantities)!=set(codes) or not codes:raise ValueError('مقدار صریح همه ردیف‌ها، حتی صفر، لازم است')
        multiplier,factor_digest=statement_factor_basis(p,t)
        lines=[]
        for row in payable_rows:
            code=row['price_code']
            lines.append({'code':code,'description':row.get('description',''),'unit':row['unit'],
                'contract_quantity':row['quantity'],'unit_price':wire(number(row['unit_price'],'نرخ')*multiplier),
                'previous_quantity':wire(previous_q.get(code,0)),'current_quantity':wire(number(quantities[code],'کارکرد'))})
        progress=build_progress(lines)
        rates={k:number(t[k],k) for k in ('retention_rate','advance_recovery_rate','tax_rate','insurance_rate')}
        recovered=sum((number(x['advance_recovery'],'استهلاک') for x in p.get('statement_periods',[])),number(0,'صفر'))
        for amendment in p.get('statement_amendments',[]):
            if amendment.get('status')=='POSTED':recovered+=number(amendment['deltas']['advance_recovery'],'اصلاح استهلاک',True)
        remaining=max(number(t['advance_paid'],'پیش‌پرداخت')-recovered,0)
        money=_money({r['code']:number(r['current_quantity'],'کارکرد') for r in lines},
                     {r['code']:number(r['unit_price'],'نرخ') for r in lines},rates,policy(p)['money'],
                     advance_cap=remaining,other_deduction_rate=t['other_deduction_rate'])
        m=policy(p)['money']
        no=max((x['number'] for x in p.get('statement_periods',[])),default=0)+1
        period=wire({'number':no,'lines':progress['lines'],**money,'rates':rates,
            'completed_total':progress['completed_total'],'remaining_contract':progress['remaining_contract'],
            'progress_percent':progress['progress_percent'],'money_policy':m,'contract_id':t['contract_id'],
            'currency':t['currency'],'reference':reference,'date':date,'financial_policy_status':'EXPLICIT_OWNER_POLICY',
            'numeric_encoding_version':2,'factor_basis':t['factor_basis'],'statement_multiplier':wire(multiplier),'factor_digest':factor_digest})
        for line,row in zip(period['lines'],payable_rows):
            line['line_id']=digest([p['id'],row['price_code'],row.get('source_ids',[]),row['unit']])
            line['source_ids']=deepcopy(row.get('source_ids',[]))
            line['source_rows']=deepcopy(row.get('source_rows',[]))
        d={'id':command['id'],'reference':reference,'date':date,'created_by':actor,'status':'DRAFT','period':period,
           'basis_digest':digest(_contract_basis(p)),'history_digest':digest(p.get('statement_periods',[])),
           'amendments_digest':digest(p.get('statement_amendments',[])),'terms_digest':digest(config),
           'factor_digest':digest(p.get('factor_review')),'events':[{'op':op,'actor':actor,'at':at}]}
        records.append(d);return p
    matches=[d for d in records if d['id']==command['id']]
    if len(matches)!=1:raise ValueError('سند صورت‌وضعیت یافت نشد')
    d=matches[0]
    transitions={'review':('DRAFT','REVIEWED','review'),'approve':('REVIEWED','APPROVED','approve'),'issue':('APPROVED','ISSUED','post')}
    if op not in transitions:raise ValueError('عملیات صورت‌وضعیت نامعتبر است')
    before,after,permission=transitions[op];authorize(p,actor,permission)
    if d['status']!=before or actor==d['created_by']:raise ValueError('وضعیت یا مسئول مستقل سند نامعتبر است')
    if op=='approve' and actor==d.get('reviewed_by'):raise ValueError('تأییدکننده باید مستقل از بازبین باشد')
    if (d['basis_digest']!=digest(_contract_basis(p)) or d['history_digest']!=digest(p.get('statement_periods',[]))
        or d['amendments_digest']!=digest(p.get('statement_amendments',[])) or d['terms_digest']!=digest(config)
        or d['factor_digest']!=digest(p.get('factor_review'))):raise ValueError('مبنای سند تغییر کرده؛ پیش‌نویس جدید لازم است')
    audit_boq(p,require_pricebook=True)
    statement_factor_basis(p,t)
    d['status']=after;d[{'review':'reviewed_by','approve':'approved_by','issue':'issued_by'}[op]]=actor
    d['events'].append({'op':op,'actor':actor,'at':at})
    if op=='issue':p.setdefault('statement_periods',[]).append(deepcopy(d['period']))
    return p


def workflow_guard(previous,updated,command):
    keys=('statement_workflow','statement_workflow_terms')
    changed=any(previous.get(k)!=updated.get(k) for k in keys)
    if previous.get('statement_workflow_terms') and previous.get('statement_periods')!=updated.get('statement_periods'):changed=True
    if not changed:return
    if not command or command.get('domain')!='statement':raise ValueError('تغییر صورت‌وضعیت فقط از گردش مجاز امکان‌پذیر است')
    expected=statement_dispatch(previous,command)
    clean=deepcopy(updated);clean.pop('_meta',None)
    if digest(clean)!=digest(expected):raise ValueError('محتوای صورت‌وضعیت با فرمان معتبر مطابقت ندارد')
