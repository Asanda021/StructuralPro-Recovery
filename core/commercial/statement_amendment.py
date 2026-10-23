"""Additive statement corrections. Never replace issued statements or payable BOQ.

Authority is an explicit project-owner policy, not a fabricated reviewer or an
authentication service. Real projects without that policy remain blocked.
Money rounding is allowed only under the owner's recorded currency policy;
quantities and PDF representations are never rounded here.
"""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, localcontext, Inexact, Rounded, InvalidOperation
from pathlib import Path
import base64
import hashlib
import json
from uuid import uuid4

MONEY_KEYS=("gross_current","retention","advance_recovery","other_deductions","taxable_current","tax","insurance","payable_current")
RATE_KEYS=("retention_rate","advance_recovery_rate","tax_rate","insurance_rate")
ROUNDINGS={"ROUND_HALF_UP","ROUND_HALF_EVEN","ROUND_DOWN"}
SUBJECT_KEYS=("amendment_id","project_id","issued_period_no","sequence","created_by",
              "reason","source_documents","lines","deltas","effective_before","effective_after",
              "issued_statement_digest","contract_basis_digest","issued_history_digest",
              "posted_state_digest","policy_digest","money_policy")

def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)

def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def _text(value,label):
    if not isinstance(value,str) or not value.strip():raise ValueError(f"{label} باید صریح وارد شود")
    return value.strip()
def _int(value,label):
    if isinstance(value,bool) or not isinstance(value,int) or value<1:raise ValueError(f"{label} باید عدد صحیح مثبت باشد")
    return value
def number(value,label,negative=False):
    if isinstance(value,bool) or value is None:raise ValueError(f"{label}: عدد معتبر لازم است")
    try:n=Decimal(str(value))
    except (InvalidOperation,ValueError,TypeError) as e:raise ValueError(f"{label}: عدد معتبر لازم است") from e
    if not n.is_finite() or (n<0 and not negative):raise ValueError(f"{label}: عدد متناهی معتبر لازم است")
    if len(n.as_tuple().digits)>128 or abs(n.as_tuple().exponent)>128:
        raise ValueError(f"{label}: دقت خارج از محدوده محاسبه دقیق است؛ مقدار گرد نمی‌شود")
    return n
def legacy_float(value):
    """Existing float-based paths must fail rather than truncate amendment precision."""
    result=float(value)
    if not Decimal(str(result)).is_finite() or Decimal(str(result))!=value:
        raise ValueError("دقت اصلاحیه در مسیر عددی قدیمی قابل حفظ نیست؛ محاسبه متوقف شد")
    return result

def quantity_text(value):
    text=format(value,"f")
    return text.rstrip("0").rstrip(".") if "." in text else text

def documents(raw):
    if not isinstance(raw,list) or not raw:raise ValueError("مدارک اصلاحیه و SHA-256 الزامی‌اند")
    result=[];refs=set()
    for doc in raw:
        if not isinstance(doc,dict) or set(doc)!={"ref","path","sha256"}:raise ValueError("ساختار مدرک نامعتبر است")
        ref=_text(doc['ref'],'مرجع مدرک');path=Path(_text(doc['path'],'مسیر مدرک')).resolve()
        if ref in refs:raise ValueError("مرجع مدرک تکراری است")
        refs.add(ref)
        try:
            if path.stat().st_size>8*1024*1024:raise ValueError("مدرک بیش از حد بزرگ است؛ سند کوچک‌تر یا تفکیک‌شده لازم است")
            data=path.read_bytes()
        except OSError as e:raise ValueError("مدرک اصلاحیه قابل خواندن نیست") from e
        sha=hashlib.sha256(data).hexdigest()
        if sha!=doc['sha256']:raise ValueError("SHA-256 مدرک تغییر کرده یا نامعتبر است")
        result.append({'ref':ref,'path':str(path),'sha256':sha,'snapshot_base64':base64.b64encode(data).decode()})
    return result

def check_documents(docs,live=True):
    if not docs:raise ValueError("مدارک اصلاحیه موجود نیست")
    for d in docs:
        try:data=base64.b64decode(d['snapshot_base64'],validate=True)
        except Exception as e:raise ValueError("نسخه محفوظ مدرک نامعتبر است") from e
        if hashlib.sha256(data).hexdigest()!=d['sha256']:raise ValueError("نسخه محفوظ مدرک تغییر کرده است")
    if live:
        documents([{k:d[k] for k in ('ref','path','sha256')} for d in docs])

def policy(project):
    p=project.get('statement_amendment_policy')
    if not isinstance(p,dict):raise ValueError("اصلاحیه مسدود است: سیاست مالی و مجوز مستند مالک تنظیم نشده است")
    if p['owner_id']!=(project.get('metadata') or {}).get('financial_owner_id'):
        raise ValueError("هویت مالک سیاست مالی با پروژه مطابقت ندارد")
    return p

def authorize(project,actor,permission):
    actor=_text(actor,'هویت مسئول');p=policy(project)
    if permission not in p['authorities'].get(actor,[]):raise ValueError("مسئول برای این عملیات مجوز مستند مالک ندارد")
    check_documents(p['source_documents'])
    return actor

def _period(project,no):
    no=_int(no,'شماره صورت‌وضعیت')
    matches=[x for x in project.get('statement_periods',[]) if x.get('number')==no]
    if len(matches)!=1 or not matches[0].get('lines'):raise ValueError("صورت‌وضعیت صادرشده معتبر یافت نشد")
    return matches[0]

def _basis(project):
    from core.projects.store import _contract_basis
    return hashlib.sha256(_contract_basis(project).encode()).hexdigest()

def _posted(project):return [d for d in project.get('statement_amendments',[]) if d.get('status')=='POSTED']
def _posted_digest(project):return digest([(d['amendment_id'],d['audit_hash']) for d in _posted(project)])
def _seal(doc):
    doc['content_digest']=digest({k:doc[k] for k in SUBJECT_KEYS})
    doc['audit_hash']=digest({k:v for k,v in doc.items() if k!='audit_hash'})
    return doc
def _verify(doc):
    if doc.get('content_digest')!=digest({k:doc[k] for k in SUBJECT_KEYS}):raise ValueError("اثر انگشت محتوای اصلاحیه نامعتبر است")
    if doc.get('audit_hash')!=digest({k:v for k,v in doc.items() if k!='audit_hash'}):raise ValueError("زنجیره ممیزی اصلاحیه نامعتبر است")

def _snapshot(project,doc):
    from core.reports.aec_office_package import audit_boq
    audit_boq(project,require_pricebook=True)
    _verify(doc);check_documents(doc['source_documents'])
    if digest(_period(project,doc['issued_period_no']))!=doc['issued_statement_digest'] or _basis(project)!=doc['contract_basis_digest']:
        raise ValueError("مبنای صادرشده تغییر کرده است؛ الحاقیه قرارداد لازم است")
    if digest(project.get('statement_periods',[]))!=doc['issued_history_digest'] or _posted_digest(project)!=doc['posted_state_digest']:
        raise ValueError("سوابق مالی پس از پیش‌نویس تغییر کرده‌اند؛ پیش‌نویس جدید لازم است")
    if digest(policy(project))!=doc['policy_digest']:raise ValueError("سیاست و مجوز مالی تغییر کرده است")

def cumulative_quantities(project):
    with localcontext() as ctx:
        ctx.prec=512;ctx.traps[Inexact]=True;ctx.traps[Rounded]=True
        result={}
        for period in project.get('statement_periods',[]):
            for line in period.get('lines',[]):
                code=line['code'];result[code]=result.get(code,Decimal(0))+number(line['current_quantity'],'کارکرد صادرشده')
        for d in _posted(project):
            _verify(d)
            for line in d['lines']:
                code=line['price_code'];result[code]=result.get(code,Decimal(0))+number(line['delta_quantity'],'مابه‌التفاوت',True)
        return result

def _money(quantities,prices,rates,m,*,advance_cap=None,other_deduction_rate=0):
    import decimal
    # Currency rounding is explicit and recorded; intermediate arithmetic is exact.
    gross=sum((q*prices[code] for code,q in quantities.items()),Decimal(0))
    raw={'gross_current':gross,'retention':gross*rates['retention_rate'],
         'advance_recovery':gross*rates['advance_recovery_rate']}
    if advance_cap is not None:raw['advance_recovery']=min(raw['advance_recovery'],number(advance_cap,'مانده پیش‌پرداخت'))
    raw['other_deductions']=gross*number(other_deduction_rate,'سایر کسورات')
    raw['taxable_current']=gross-raw['retention']-raw['advance_recovery']-raw['other_deductions']
    if raw['taxable_current']<0:raise ValueError('جمع کسورات بیشتر از ناخالص است')
    raw['tax']=raw['taxable_current']*rates['tax_rate'];raw['insurance']=raw['taxable_current']*rates['insurance_rate']
    raw['payable_current']=raw['taxable_current']+raw['tax']-raw['insurance']
    if raw['payable_current']<0:raise ValueError('خالص منفی بدون اصلاحیه معتبر مجاز نیست')
    if m is None:return {k:format(v,'f') for k,v in raw.items()}
    quantum=Decimal(1).scaleb(-m['decimal_places'])
    with localcontext() as ctx:
        ctx.traps[Inexact]=False;ctx.traps[Rounded]=False
        return {k:format(v.quantize(quantum,rounding=getattr(decimal,m['rounding'])),'f') for k,v in raw.items()}

def _preview(project,no,raw_lines,docs):
    from core.takeoff.units import normalize_unit
    from core.reports.aec_office_package import audit_boq
    audit_boq(project,require_pricebook=True)
    issued=_period(project,no);p=policy(project);rates={k:number(issued['rates'][k],k) for k in RATE_KEYS}
    if any(v>1 for v in rates.values()):raise ValueError("نرخ صادرشده نامعتبر است")
    originals={};prices={};boq={}
    from core.commercial.statement import statement_rows
    for row in statement_rows(project):
        code=row['price_code']
        if code in boq:raise ValueError("کد قیمت میان چند گروه BOQ مبهم است")
        boq[code]=row
    for row in issued['lines']:
        code=row['code']
        if code in originals or code not in boq:raise ValueError("هویت ردیف صادرشده مبهم است")
        b=boq[code]
        if normalize_unit(row['unit'])!=normalize_unit(b['unit']) or number(row['unit_price'],'قیمت')!=number(b['unit_price'],'قیمت')*number(issued.get('statement_multiplier',1),'ضریب قرارداد'):
            raise ValueError("تغییر نرخ یا واحد قرارداد نیازمند الحاقیه معتبر است")
        originals[code]=number(row['current_quantity'],'کارکرد اصل');prices[code]=number(row['unit_price'],'قیمت تأییدشده')
    before=dict(originals)
    for d in _posted(project):
        _verify(d)
        if d['issued_period_no']==no:
            for line in d['lines']:before[line['price_code']]+=number(line['delta_quantity'],'اصلاحیه قبلی',True)
    if not isinstance(raw_lines,list) or not raw_lines:raise ValueError("ردیف اصلاحیه باید صریح وارد شود")
    after=dict(before);total=cumulative_quantities(project);seen=set();lines=[];refs={d['ref'] for d in docs}
    for raw in raw_lines:
        if not isinstance(raw,dict) or set(raw)!={'price_code','source_id','corrected_period_quantity','reason','detail_source_ref'}:
            raise ValueError("ردیف اصلاحیه به کد، منبع، مقدار اصلاحی و علت مستند نیاز دارد")
        code=_text(raw['price_code'],'کد قیمت');source=_text(raw['source_id'],'شناسه منبع')
        if code in seen or code not in originals:raise ValueError("ردیف اصلاحیه تکراری یا نامرتبط است")
        seen.add(code);b=boq[code]
        if source not in b.get('source_ids',[]):raise ValueError("شناسه فیزیکی متعلق به ردیف BOQ نیست")
        ref=_text(raw['detail_source_ref'],'مرجع دیتایل')
        if ref not in refs:raise ValueError("دیتایل به مدرک معتبر اصلاحیه متصل نیست")
        corrected=number(raw['corrected_period_quantity'],'مقدار اصلاحی');delta=corrected-before[code]
        if total[code]+delta<0 or total[code]+delta>number(b['quantity'],'سقف قرارداد'):
            raise ValueError("اصلاحیه از سقف قرارداد تجاوز می‌کند؛ الحاقیه مستقل لازم است")
        after[code]=corrected
        lines.append({'price_code':code,'source_id':source,'item_code':b['item_code'],'unit':normalize_unit(b['unit']),
                      'original_period_quantity':quantity_text(originals[code]),'effective_period_quantity':quantity_text(before[code]),
                      'corrected_period_quantity':quantity_text(corrected),'delta_quantity':quantity_text(delta),
                      'delta_gross':quantity_text(delta*prices[code]),
                      'reviewed_unit_price':quantity_text(prices[code]),'pricebook_sha256':project['user_pricebook_review']['sha256'],
                      'reason':_text(raw['reason'],'علت ردیف'),'detail_source_ref':ref})
    cap=None;other=0
    if issued.get('reference') and project.get('statement_workflow_terms'):
        terms=project['statement_workflow_terms']['terms'];other=terms['other_deduction_rate']
        used=sum((number(x['advance_recovery'],'استهلاک') for x in project.get('statement_periods',[]) if x['number']!=no),Decimal(0))
        for change in _posted(project):
            if change['issued_period_no']!=no:used+=number(change['deltas']['advance_recovery'],'اصلاح استهلاک',True)
        cap=max(number(terms['advance_paid'],'پیش‌پرداخت')-used,Decimal(0))
    # The historical effective money is authoritative; freed advance capacity
    # may change the new result, but must never rewrite the comparison baseline.
    money_before=summary(project,no)['net']
    money_after=_money(after,prices,rates,p['money'],advance_cap=cap,other_deduction_rate=other)
    return lines,money_before,money_after,{k:format(Decimal(money_after[k])-Decimal(money_before[k]),'f') for k in MONEY_KEYS}

def dispatch(previous,command):
    project=deepcopy(previous);project.pop('_meta',None)
    with localcontext() as ctx:
        ctx.prec=512;ctx.traps[Inexact]=True;ctx.traps[Rounded]=True
        op=command['op'];actor=_text(command['actor'],'مسئول');at=command['at']
        if op=='configure':
            if project.get('statement_amendment_policy'):raise ValueError("سیاست مالی ثبت‌شده قابل جایگزینی مستقیم نیست")
            if actor!=(project.get('metadata') or {}).get('financial_owner_id'):
                raise ValueError("مالک مالی پروژه صریح تعیین نشده یا مسئول مجاز نیست")
            raw=command['policy'];m=raw.get('money',{});authorities=raw.get('authorities')
            if set(m)!={'decimal_places','rounding','currency'} or isinstance(m['decimal_places'],bool) or not isinstance(m['decimal_places'],int) or not 0<=m['decimal_places']<=6 or m['rounding'] not in ROUNDINGS:
                raise ValueError("سیاست دقت و گردکردن پول باید توسط مالک صریح تعیین شود")
            _text(m['currency'],'واحد پول')
            if not isinstance(authorities,dict) or not authorities:raise ValueError("مجوزهای مسئولان باید صریح ثبت شوند")
            grants={}
            for name,permissions in authorities.items():
                name=_text(name,'هویت مسئول')
                if not isinstance(permissions,list) or not permissions or not set(permissions)<={'create','review','approve','post'}:raise ValueError("مجوز مسئول نامعتبر است")
                grants[name]=sorted(set(permissions))
            project['statement_amendment_policy']={'owner_id':actor,'money':deepcopy(m),'authorities':grants,
                                                 'source_documents':documents(command['source_documents']),'configured_at':at}
            return project
        docs=project.setdefault('statement_amendments',[])
        if op=='create':
            actor=authorize(project,actor,'create');no=_int(command['period_no'],'شماره دوره')
            source_docs=documents(command['source_documents']);lines,before,after,deltas=_preview(project,no,command['lines'],source_docs)
            if any(d['amendment_id']==command['id'] for d in docs):raise ValueError("شناسه اصلاحیه تکراری است")
            d={'amendment_id':command['id'],'project_id':project['id'],'issued_period_no':no,'sequence':len(docs)+1,
               'revision':1,'status':'DRAFT','created_by':actor,'created_at':at,'reason':_text(command['reason'],'علت اصلاحیه'),
               'source_documents':source_docs,'lines':lines,'deltas':deltas,'effective_before':before,'effective_after':after,
               'issued_statement_digest':digest(_period(project,no)),'contract_basis_digest':_basis(project),
               'issued_history_digest':digest(project.get('statement_periods',[])),'posted_state_digest':_posted_digest(project),
               'policy_digest':digest(policy(project)),'money_policy':deepcopy(policy(project)['money'])}
            docs.append(_seal(d));return project
        matches=[d for d in docs if d['amendment_id']==command['id']]
        if len(matches)!=1:raise ValueError("اصلاحیه یافت نشد")
        d=matches[0];_verify(d)
        if d['revision']!=command['expected_revision']:raise RuntimeError("نسخه اصلاحیه تغییر کرده است")
        if op=='edit':
            actor=authorize(project,actor,'create')
            if d['status']!='DRAFT' or actor!=d['created_by']:raise ValueError("فقط نویسنده می‌تواند پیش‌نویس را ویرایش کند")
            source_docs=documents(command['source_documents'])
            lines,before,after,deltas=_preview(project,d['issued_period_no'],command['lines'],source_docs)
            d.update(reason=_text(command['reason'],'علت اصلاحیه'),source_documents=source_docs,
                     lines=lines,effective_before=before,effective_after=after,deltas=deltas,
                     issued_statement_digest=digest(_period(project,d['issued_period_no'])),
                     contract_basis_digest=_basis(project),issued_history_digest=digest(project.get('statement_periods',[])),
                     posted_state_digest=_posted_digest(project),policy_digest=digest(policy(project)),
                     edited_by=actor,edited_at=at)
        elif op=='review':
            actor=authorize(project,actor,'review')
            if d['status']!='DRAFT' or actor==d['created_by']:raise ValueError("بازبینی مستقل پیش‌نویس لازم است")
            _snapshot(project,d);d.update(status='REVIEWED',reviewed_by=actor,reviewed_at=at)
        elif op=='approve':
            actor=authorize(project,actor,'approve')
            if d['status']!='REVIEWED' or actor in {d['created_by'],d['reviewed_by']}:raise ValueError("تأیید مستقل و مجاز بازبینی لازم است")
            if command['expected_content_digest']!=d['content_digest']:raise ValueError("اثر انگشت تأیید با محتوای بازبینی‌شده مطابقت ندارد")
            _snapshot(project,d);d.update(status='APPROVED',approved_by=actor,approved_at=at)
        elif op=='post':
            actor=authorize(project,actor,'post')
            if d['status']!='APPROVED':raise ValueError("اصلاحیه تأیید نشده یا قبلاً اعمال شده است")
            if actor==d['created_by']:raise ValueError("ثبت مستقل لازم است")
            authorize(project,d['reviewed_by'],'review');authorize(project,d['approved_by'],'approve')
            _snapshot(project,d);d.update(status='POSTED',posted_by=actor,posted_at=at)
        elif op=='reject':
            authorize(project,actor,'review')
            if d['status'] not in {'DRAFT','REVIEWED'}:raise ValueError("این اصلاحیه قابل رد مستقیم نیست")
            d.update(status='REJECTED',rejected_by=actor,rejected_at=at,rejection_reason=_text(command['reason'],'علت رد'))
        else:raise ValueError("فرمان اصلاحیه پشتیبانی نمی‌شود")
        d['revision']+=1;_seal(d);return project

def guard_change(previous,updated,command):
    keys=('statement_amendments','statement_amendment_policy')
    if all(previous.get(k)==updated.get(k) for k in keys):
        if previous.get('statement_amendment_policy') and (previous.get('metadata') or {}).get('financial_owner_id')!=(updated.get('metadata') or {}).get('financial_owner_id'):
            raise ValueError("تغییر مالک مالی نیازمند مجوز و گردش مستقل است")
        return
    if command is None:raise ValueError("تغییر مستقیم اسناد اصلاحیه مجاز نیست؛ سرویس مجاز لازم است")
    expected=dispatch(previous,command)
    actual=deepcopy(updated);actual.pop('_meta',None)
    if canonical(actual)!=canonical(expected):raise ValueError("داده اصلاحیه با فرمان و محاسبات معتبر مطابقت ندارد")

class StatementAmendmentService:
    def __init__(self,store):self.store=store
    def execute(self,pid,op,actor,expected_project_version,**data):
        version=_int(expected_project_version,'نسخه پروژه');p=self.store.get(pid)
        if p is None:raise KeyError(pid)
        if p['_meta']['version']!=version:raise RuntimeError("نسخه پروژه تغییر کرده است؛ دوباره بازخوانی کنید")
        command={**deepcopy(data),'op':op,'actor':actor,'at':datetime.now(timezone.utc).isoformat()}
        if op=='create':command['id']=uuid4().hex
        if 'expected_revision' in command:_int(command['expected_revision'],'نسخه اصلاحیه')
        from core.platform.concurrency import begin_write
        updated=dispatch(p,command)
        self.store.save(pid,updated,expected_digest=begin_write({k:v for k,v in p.items() if k!='_meta'}),amendment_command=command)
        if op=='configure':return deepcopy(updated['statement_amendment_policy'])
        return deepcopy(next(d for d in updated['statement_amendments'] if d['amendment_id']==command['id']))

def summary(project,no):
    with localcontext() as ctx:
        ctx.prec=512
        issued=_period(project,no);p=policy(project);m=p['money'];quantum=Decimal(1).scaleb(-m['decimal_places'])
        import decimal
        original={k:format(number(issued.get(k,0),k).quantize(quantum,rounding=getattr(decimal,m['rounding'])),'f') for k in MONEY_KEYS}
        changes={k:Decimal(0).quantize(quantum) for k in MONEY_KEYS};q={line['code']:number(line['current_quantity'],'کارکرد') for line in issued['lines']}
        posted=[]
        for d in _posted(project):
            _verify(d);check_documents(d['source_documents'],live=False)
            if d['issued_period_no']==no:
                if d['issued_statement_digest']!=digest(issued):raise ValueError("اصل صورت‌وضعیت تغییر کرده است")
                posted.append(d['amendment_id'])
                for k in MONEY_KEYS:changes[k]+=number(d['deltas'][k],k,True)
                for line in d['lines']:q[line['price_code']]+=number(line['delta_quantity'],'مابه‌التفاوت',True)
        return {'issued_period_no':no,'original':original,'amendment_deltas':{k:format(v,'f') for k,v in changes.items()},
                'net':{k:format(Decimal(original[k])+changes[k],'f') for k in MONEY_KEYS},'posted_amendment_ids':posted,
                'lines':[{'price_code':code,'original_quantity':quantity_text(number(line['current_quantity'],'کارکرد')),
                          'net_quantity':quantity_text(q[code])} for line in issued['lines'] for code in [line['code']]]}
