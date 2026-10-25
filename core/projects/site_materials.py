"""Evidence-backed material planning over existing BOQ and project_materials.

This domain mutates an isolated payload only. Policy, replay, persistence and
financial handoff belong to the existing project command boundary.
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from core.commercial.exact_values import exact
from core.projects.controls import num, text, evidence, find, digest, boq_basis, references
from core.takeoff.units import normalize_unit

KEYS = ('project_materials', 'material_rules', 'material_requirements',
        'material_closures', 'purchase_drafts')
OPS = frozenset({'material_rule_create','material_rule_review','material_rule_approve','material_need','purchase_cancel',
                 'inventory_opening','inventory_receipt','inventory_consume','inventory_reserve',
                 'inventory_return','inventory_correct','inventory_close','purchase_draft',
                 'purchase_review','purchase_approve'})
ZERO = Decimal('0')


def _date(v):
    s = text(v, 'تاریخ')
    try:
        if date.fromisoformat(s).isoformat() != s:raise ValueError()
    except ValueError as exc:raise ValueError('تاریخ ISO معتبر لازم است') from exc
    return s


def _period(data):
    start, end = _date(data.get('period_start')), _date(data.get('period_end'))
    if start > end:raise ValueError('بازه تاریخ نامعتبر است')
    return start, end


def _new(p, key, data):
    id = text(data.get('id'), 'شناسه')
    if any(str(r.get('id')).strip().casefold() == id.casefold() for r in p.get(key, [])):
        raise ValueError('شناسه تکراری است')
    return id


def _rule_value(r):
    return {k:r.get(k) for k in ('material_code','specification','base_unit','material_unit','ratio','waste_percent','source_version','source')}


def _rule(p, id):
    r=find(p.get('material_rules',[]),id,'قاعده مصالح')
    evidence(r['source'])
    if r.get('project_id')!=p.get('id'):raise ValueError('قاعده به پروژه دیگر تعلق دارد')
    if r.get('status')!='approved' or r.get('approval_digest')!=digest(_rule_value(r)):
        raise ValueError('قاعده مصالح تأیید نشده یا تغییر کرده است')
    return r


def _identity(p, code, unit):
    rules=[r for r in p.get('material_rules',[]) if r.get('material_code')==code]
    if not rules or any(r['material_unit']!=unit for r in rules):
        raise ValueError('هویت یا واحد مصالح ناسازگار است')
    if len({r['specification'] for r in rules})!=1:
        raise ValueError('مشخصات فنی یک کد مصالح متعارض است')
    return rules[0]


def _boq(p, ids, item, unit):
    from core.reports.aec_office_package import audit_boq
    audit_boq(p)
    if not isinstance(ids,list) or not ids or len(set(ids))!=len(ids):
        raise ValueError('مجموعه منابع معتبر لازم است')
    candidates=[]
    for row in p.get('boq',[]):
        sources=set(row.get('source_ids') or [row.get('source_id')])
        if row.get('item_code')==item and normalize_unit(row.get('unit'))==unit and sources & set(ids):
            if sources!=set(ids):raise ValueError('تمام منابع ردیف تجمیعی الزامی است')
            candidates.append(row)
    if len(candidates)!=1:raise ValueError('ردیف BOQ یکتا موجود نیست')
    row=candidates[0]
    if row.get('status','active')!='active':raise ValueError('ردیف BOQ غیرفعال است')
    return row


def _quantity_approval(p, ids, row, approval, actor):
    from core.takeoff.manual_formula_amendments import effective_takeoffs
    records=[r for r in effective_takeoffs(p,p.get('takeoffs') or []) if r.get('source_id') in ids]
    reviewed=set()
    for key in ('beam_detail_register','reviewed_structural_members','reviewed_aec_systems'):
        registry=p.get(key) or {}
        if not isinstance(registry,dict):raise ValueError('دفتر بازبینی متره نامعتبر است')
        for entry in registry.values():
            if not isinstance(entry,dict):raise ValueError('رکورد بازبینی متره نامعتبر است')
            if entry.get('status') in {'approved','confirmed','committed'} or entry.get('approved_by'):
                reviewed.update(entry.get('source_ids') or [])
                reviewed.update(entry.get('committed_source_ids') or [])
                if entry.get('source_id'):reviewed.add(entry['source_id'])
    for record in records:
        if record.get('status') in {'draft','proposed','unreviewed','needs_review','review_required','rejected','blocked'}:
            raise ValueError('پیشنهاد متره باید ابتدا در مسیر اصلی بازبینی و ثبت شود')
        provenance=record.get('provenance') or {}
        mode=str(provenance.get('mode') or record.get('source_type') or '').lower()
        if 'ai' in mode and record.get('source_id') not in reviewed:
            raise ValueError('متره هوش مصنوعی فاقد ثبت بازبینی اصلی است')
    if records and all(r.get('status') in {'approved','confirmed'} or r.get('approved_by') or (r.get('review') or {}).get('approved_by') or r.get('source_id') in reviewed for r in records):return None
    if not isinstance(approval,dict):raise ValueError('تأیید مستند مقدار BOQ الزامی است')
    approved_by=text(approval.get('approved_by'),'تأییدکننده مستقل مقدار')
    if approved_by==actor or approval.get('basis_digest')!=boq_basis(p,row):raise ValueError('تأیید مقدار مستقل یا مبنای آن معتبر نیست')
    return {'source':evidence(approval.get('source')),'approved_by':approved_by,
            'source_version':text(approval.get('source_version'),'نسخه تأیید مقدار'),'basis_digest':approval['basis_digest']}


def _stale(p, n):
    try:
        if n.get('project_id')!=p.get('id'):return True
        r=_rule(p,n['rule_id'])
        row=_boq(p,n['source_ids'],n['item_code'],r['base_unit'])
        if n.get('quantity_approval'):evidence(n['quantity_approval']['source'])
        return n['rule_digest']!=digest(_rule_value(r)) or n['basis_digest']!=boq_basis(p,row)
    except (ValueError,KeyError,TypeError):return True


def _events(p,code,unit,as_of):
    rows=[r for r in p.get('project_materials',[]) if r.get('schema')=='site_material_v1'
          and r.get('material_code')==code and r.get('unit')==unit and r['date']<=as_of]
    for r in rows:
        if r.get('project_id')!=p.get('id'):raise ValueError('ارجاع سند به پروژه دیگر است')
        evidence(r['source'])
    reversed_ids={r['reference_id'] for r in rows if r['kind']=='correct'}
    return rows,[r for r in rows if r['kind']!='correct' and r['id'] not in reversed_ids]


def _ledger_digest(rows):return digest(rows)


def _sums(active):
    on_hand=ZERO;consumed={};reservations={}
    for e in active:
        q=num(e['quantity'],'مقدار');kind=e['kind'];rid=e.get('requirement_id')
        if kind in {'opening','receipt'}:on_hand+=q
        elif kind=='consume':on_hand-=q;consumed[rid]=consumed.get(rid,ZERO)+q
        elif kind=='reserve':reservations[rid]=reservations.get(rid,ZERO)+q
        elif kind=='return':
            if e['direction']=='stock_in':on_hand+=q;consumed[rid]=consumed.get(rid,ZERO)-q
            else:on_hand-=q
    outstanding={rid:max(ZERO,q-consumed.get(rid,ZERO)) for rid,q in reservations.items()}
    return on_hand,consumed,outstanding


def _stock(p,code,unit,as_of):
    rows,active=_events(p,code,unit,as_of)
    openings=[r for r in active if r['kind']=='opening']
    on_hand,consumed,reserved=_sums(active)
    known=False
    if len(openings)==1:
        opening=openings[0]
        for c in p.get('material_closures',[]):
            if c['material_code']==code and c['unit']==unit and c['period_start']<=opening['date'] and c['period_end']>=as_of:
                evidence(c['source'])
                covered,_=_events(p,code,unit,c['period_end'])
                if c['ledger_digest']==_ledger_digest(covered):known=True
    return {'known':known,'on_hand':on_hand,'consumed':consumed,'reserved':reserved,'rows':rows,'active':active}


def _workflow(p,key,op,data,actor):
    r=find(p.get(key,[]),data.get('id'),'سند')
    if key=='material_rules':
        evidence(r['source']);current=digest(_rule_value(r))
    else:
        n=find(p.get('material_requirements',[]),r['requirement_id'],'نیاز')
        current_view=_requirement_view(p,n,r['as_of'])
        if not current_view['current'] or current_view['shortage'] is None or digest(current_view)!=r['stock_digest']:
            raise ValueError('مبنای پیش‌نویس خرید تغییر کرده است')
        if r.get('price_source'):evidence(r['price_source'])
        current=digest({k:v for k,v in r.items() if k not in {'status','reviewed_by','approved_by','review_digest','approval_digest'}})
    if op.endswith('_review'):
        if r['status']!='draft' or actor==r['created_by']:raise ValueError('بازبینی مستقل پیش‌نویس الزامی است')
        r.update(status='reviewed',reviewed_by=actor,review_digest=current)
    else:
        if r['status']!='reviewed' or actor in {r['created_by'],r.get('reviewed_by')} or r['review_digest']!=current:
            raise ValueError('تأیید مستقل پس از بازبینی معتبر الزامی است')
        r.update(status='approved',approved_by=actor,approval_digest=current)
    return deepcopy(r)


@exact
def _requirement_view(p,n,as_of):
    v=deepcopy(n)
    superseded=any(r.get('supersedes')==n['id'] for r in p.get('material_requirements',[]))
    stale=_stale(p,n)
    v.update(current=not superseded and not stale,basis_stale=stale,superseded=superseded,
             consumed=None,reserved=None,on_hand=None,free_stock=None,shortage=None,stock_known=False)
    try:
        state=_stock(p,n['material_code'],n['unit'],as_of)
        consumed=state['consumed'].get(n['id'],ZERO)
        own=state['reserved'].get(n['id'],ZERO)
        total=sum(state['reserved'].values(),ZERO)
        v.update(consumed=str(consumed),reserved=str(own),stock_known=state['known'],
                 stock_source_ids=[r['id'] for r in state['rows']])
        if state['known']:
            v.update(on_hand=str(state['on_hand']),free_stock=str(state['on_hand']-total))
            if v['current']:
                free=max(ZERO,state['on_hand']-total)
                candidates=[r for r in p.get('material_requirements',[])
                            if r['material_code']==n['material_code'] and r['unit']==n['unit']
                            and not _stale(p,r) and not any(x.get('supersedes')==r['id'] for x in p.get('material_requirements',[]))]
                for candidate in sorted(candidates,key=lambda r:(r['period_start'],r['period_end'],r['id'])):
                    rid=candidate['id']
                    remaining=max(ZERO,num(candidate['quantity'],'نیاز')-state['consumed'].get(rid,ZERO))
                    unfunded=max(ZERO,remaining-state['reserved'].get(rid,ZERO))
                    allocated=min(free,unfunded);free-=allocated
                    if rid==n['id']:
                        v['allocated_free_stock']=str(allocated)
                        v['shortage']=str(unfunded-allocated)
    except (ValueError,KeyError,TypeError):v['stock_source_ids']=[]
    return v


def _purchase_view(p,r,as_of):
    out=deepcopy(r);current=False
    try:
        n=find(p.get('material_requirements',[]),r['requirement_id'],'نیاز')
        v=_requirement_view(p,n,max(as_of,r['as_of']))
        if r.get('price_source'):evidence(r['price_source'])
        fingerprint=digest({k:v for k,v in r.items() if k not in {'status','reviewed_by','approved_by','review_digest','approval_digest'}})
        current=(r.get('project_id')==p.get('id') and v['current'] and v['shortage'] is not None
                 and digest(v)==r['stock_digest'])
        if r['status']=='reviewed':current=current and r.get('review_digest')==fingerprint
        if r['status']=='approved':current=current and r.get('approval_digest')==fingerprint
    except (ValueError,KeyError,TypeError):pass
    out.update(current=bool(current),basis_stale=not current)
    return out


@exact
def snapshot(p,*,as_of,activity_id=None):
    as_of=_date(as_of)
    if activity_id is not None:find(p.get('project_schedule_tasks',[]),activity_id,'فعالیت')
    return {'project_id':p.get('id'),'as_of':as_of,
            'requirements':[_requirement_view(p,n,as_of) for n in p.get('material_requirements',[])
                            if activity_id is None or n['activity_id']==activity_id],
            'rules':deepcopy(p.get('material_rules',[])),
            'purchase_drafts':[_purchase_view(p,r,as_of) for r in p.get('purchase_drafts',[])],
            'formula':'remaining=max(need-net_consumed,0); outstanding_reserved=max(reserved-net_consumed,0); free=on_hand-all_outstanding_reserved; allocate free once in period_start/period_end/id order; shortage=max(remaining-own_outstanding_reserved-allocated_free,0)'}


@exact
def dispatch(p,op,data,actor,reason):
    actor=text(actor,'مسئول');text(reason,'دلیل')
    if data.get('project_id',p.get('id'))!=p.get('id'):raise ValueError('پروژه سند ناسازگار است')
    if op=='material_rule_create':
        id=_new(p,'material_rules',data)
        r={k:text(data.get(k),k) for k in ('material_code','specification','source_version')}
        r.update(id=id,project_id=p.get('id'),base_unit=normalize_unit(text(data.get('base_unit'),'واحد مبنا')),
                 material_unit=normalize_unit(text(data.get('material_unit'),'واحد مصالح')),
                 ratio=str(num(data.get('ratio'),'ضریب مصرف')),waste_percent=str(num(data.get('waste_percent'),'پرت مجاز')),
                 source=evidence(data.get('source')),status='draft',created_by=actor)
        if num(r['ratio'],'ضریب')<=0:raise ValueError('ضریب مصرف باید مثبت باشد')
        for old in p.get('material_rules',[]):
            if old['material_code']==r['material_code'] and (old['material_unit']!=r['material_unit'] or old['specification']!=r['specification']):raise ValueError('هویت مصالح متعارض است')
        p.setdefault('material_rules',[]).append(r)
        return deepcopy(r)
    if op in {'material_rule_review','material_rule_approve'}:return _workflow(p,'material_rules',op,data,actor)
    if op=='material_need':
        id=_new(p,'material_requirements',data);r=_rule(p,data.get('rule_id'))
        row=_boq(p,data.get('source_ids'),text(data.get('item_code'),'عملیات'),r['base_unit'])
        quantity_approval=_quantity_approval(p,data['source_ids'],row,data.get('quantity_approval'),actor)
        a=find(p.get('project_schedule_tasks',[]),data.get('activity_id'),'فعالیت')
        floors=references(p,'floors',data.get('floor_ids'),'طبقه');zones=references(p,'zones',data.get('zone_ids'),'زون')
        if not floors or not set(floors)<=set(a.get('floor_ids',[])) or not set(zones)<=set(a.get('zone_ids',[])):raise ValueError('مکان نیاز با فعالیت ناسازگار است')
        if any(not set(find(p['zones'],z,'زون').get('floor_ids',[]))<=set(floors) for z in zones):raise ValueError('زون با طبقه ناسازگار است')
        start,end=_period(data);supersedes=data.get('supersedes')
        identity=(set(data['source_ids']),row['item_code'],r['base_unit'],r['material_code'])
        for old in p.get('material_requirements',[]):
            if (set(old['source_ids']),old['item_code'],old['base_unit'],old['material_code'])==identity and not any(n.get('supersedes')==old['id'] for n in p.get('material_requirements',[])):
                if supersedes!=old['id']:raise ValueError('تخصیص فیزیکی مشترک تکراری است')
        if supersedes:
            old=find(p.get('material_requirements',[]),supersedes,'نسخه پیشین نیاز')
            if (set(old['source_ids']),old['item_code'],old['base_unit'],old['material_code'])!=identity:raise ValueError('هویت اصلاح نیاز ناسازگار است')
            _,active=_events(p,old['material_code'],old['unit'],'9999-12-31')
            if any(e.get('requirement_id')==supersedes for e in active):raise ValueError('نیاز دارای گردش انبار باید ابتدا با سند اصلاح رسیدگی شود')
        q=num(row['quantity'],'مقدار BOQ')*num(r['ratio'],'ضریب')*(1+num(r['waste_percent'],'پرت')/100)
        n={'id':id,'project_id':p.get('id'),'rule_id':r['id'],'rule_digest':digest(_rule_value(r)),
           'basis_digest':boq_basis(p,row),'source_ids':deepcopy(data['source_ids']),'item_code':row['item_code'],
           'base_unit':r['base_unit'],'base_quantity':str(num(row['quantity'],'مقدار BOQ')),'material_code':r['material_code'],
           'specification':r['specification'],'unit':r['material_unit'],'quantity':str(q),'activity_id':a['id'],
           'floor_ids':floors,'zone_ids':zones,'period_start':start,'period_end':end,'supersedes':supersedes,
           'quantity_approval':quantity_approval,'created_by':actor,'source':deepcopy(r['source'])}
        p.setdefault('material_requirements',[]).append(n);return deepcopy(n)
    if op=='inventory_close':
        id=_new(p,'material_closures',data);code=text(data.get('material_code'),'مصالح');unit=normalize_unit(data.get('unit'))
        _identity(p,code,unit);start,end=_period(data)
        if data.get('confirmed') is not True:raise ValueError('تأیید صریح کامل بودن دوره الزامی است')
        rows,_=_events(p,code,unit,end)
        c={'id':id,'project_id':p.get('id'),'material_code':code,'unit':unit,'period_start':start,'period_end':end,
           'source':evidence(data.get('source')),'ledger_digest':_ledger_digest(rows),'created_by':actor,'coverage':['receipt','consume','reserve','return','correct']}
        p.setdefault('material_closures',[]).append(c);return deepcopy(c)
    if op.startswith('inventory_'):return _post(p,op.removeprefix('inventory_'),data,actor)
    if op=='purchase_draft':
        id=_new(p,'purchase_drafts',data);n=find(p.get('material_requirements',[]),data.get('requirement_id'),'نیاز')
        as_of=_date(data.get('as_of'));v=_requirement_view(p,n,as_of)
        if not v['current'] or v['shortage'] is None or num(v['shortage'],'کسری')<=0:raise ValueError('کسری مثبت مستند و جاری لازم است')
        if any(x['requirement_id']==n['id'] and x['status'] in {'draft','reviewed','approved'} for x in p.get('purchase_drafts',[])):raise ValueError('پیش‌نویس خرید این نیاز موجود است')
        price=data.get('price');currency=None;proof=None
        if price is not None:
            price=str(num(price,'نرخ'));currency=text(data.get('currency'),'ارز');proof=evidence(data.get('price_source'))
        r={k:deepcopy(n[k]) for k in ('material_code','specification','unit','activity_id','floor_ids','zone_ids','period_start','period_end','rule_id','basis_digest','source_ids','source')}
        r.update(id=id,project_id=p.get('id'),requirement_id=n['id'],quantity=v['shortage'],as_of=as_of,stock_state=v,
                 stock_digest=digest(v),owner=text(data.get('owner'),'مالک خرید'),supplier=data.get('supplier'),price=price,
                 currency=currency,price_source=proof,status='draft',created_by=actor)
        p.setdefault('purchase_drafts',[]).append(r);return deepcopy(r)
    if op in {'purchase_review','purchase_approve'}:return _workflow(p,'purchase_drafts',op,data,actor)
    if op=='purchase_cancel':
        r=find(p.get('purchase_drafts',[]),data.get('id'),'درخواست خرید')
        if r['status']=='cancelled' or any(x['purchase_id']==r['id'] for x in p.get('site_purchase_handoffs',[])):raise ValueError('درخواست لغوشده یا منتقل‌شده قابل لغو نیست')
        r.update(status='cancelled',cancelled_by=actor,cancel_reason=reason);return deepcopy(r)
    raise ValueError('عملیات مصالح ناشناخته است')


@exact
def _post(p,kind,data,actor):
    if kind not in {'opening','receipt','consume','reserve','return','correct'}:raise ValueError('نوع گردش انبار نامعتبر است')
    id=_new(p,'project_materials',data);code=text(data.get('material_code'),'مصالح');unit=normalize_unit(data.get('unit'))
    spec=_identity(p,code,unit);when=_date(data.get('date'));reference=text(data.get('reference'),'شماره سند')
    proof=evidence(data.get('source'))
    if data.get('confirmed') is not True:raise ValueError('تأیید صریح سند انبار الزامی است')
    official=[r for r in p.get('project_materials',[]) if r.get('schema')=='site_material_v1']
    if any(r['reference']==reference for r in official):raise ValueError('شماره سند انبار تکراری است')
    rows,active=_events(p,code,unit,'9999-12-31');q=ZERO if kind=='correct' else num(data.get('quantity'),'مقدار');rid=data.get('requirement_id')
    ref=None;direction=None
    if kind=='correct':
        ref=find(active,data.get('reference_id'),'سند اصلاح')
        if any(r.get('reference_id')==ref['id'] for r in active):raise ValueError('سند دارای ارجاع باید ابتدا با اسناد وابسته اصلاح شود')
        if when<ref['date']:raise ValueError('اصلاح پیش از سند مبنا مجاز نیست')
        q=num(ref['quantity'],'مقدار');rid=ref.get('requirement_id')
    elif kind=='return':
        direction=data.get('direction');ref=find(active,data.get('reference_id'),'سند مرجوعی')
        target={'stock_in':'consume','stock_out':'receipt'}.get(direction)
        if target is None or ref['kind']!=target or when<ref['date']:raise ValueError('جهت یا سند مبنای مرجوعی نامعتبر است')
        returned=sum((num(r['quantity'],'مقدار') for r in active if r['kind']=='return' and r.get('reference_id')==ref['id']),ZERO)
        if q+returned>num(ref['quantity'],'مقدار'):raise ValueError('مقدار مرجوعی بیش از سند مبنا است')
        rid=ref.get('requirement_id')
    elif kind in {'consume','reserve'}:
        n=find(p.get('material_requirements',[]),rid,'نیاز')
        if n['material_code']!=code or n['unit']!=unit or n['project_id']!=p.get('id') or _stale(p,n):raise ValueError('نیاز یا مبنای گردش انبار معتبر نیست')
        if any(r.get('supersedes')==rid for r in p.get('material_requirements',[])):raise ValueError('نیاز اصلاح شده است')
        if not n['period_start']<=when<=n['period_end']:raise ValueError('تاریخ خارج از دوره نیاز است')
    elif kind=='opening':
        if any(r['kind']=='opening' for r in active):raise ValueError('موجودی افتتاحیه مستند قبلاً ثبت شده است')
        if any(r['date']<when for r in active):raise ValueError('افتتاحیه پس از گردش انبار مجاز نیست')
    if q<=0 and kind not in {'opening','correct'}:raise ValueError('مقدار باید مثبت باشد')
    e={'id':id,'schema':'site_material_v1','project_id':p.get('id'),'name':spec['specification'],
       'material_code':code,'quantity':str(q),'unit':unit,'date':when,'supplier':data.get('supplier'),
       'status':'confirmed','kind':kind,'reference':reference,'source':proof,'created_by':actor,
       'requirement_id':rid,'reference_id':ref['id'] if ref else None,'direction':direction}
    candidate=rows+[e];reversed_ids={r['reference_id'] for r in candidate if r['kind']=='correct'}
    effective=[r for r in candidate if r['kind']!='correct' and r['id'] not in reversed_ids]
    openings=[r for r in effective if r['kind']=='opening']
    if openings and any(r['date']<openings[0]['date'] for r in effective):raise ValueError('گردش پیش از افتتاحیه نامعتبر است')
    on_hand,consumed,reserved=_sums(effective)
    for n in p.get('material_requirements',[]):
        if n['material_code']==code and n['unit']==unit:
            used=consumed.get(n['id'],ZERO);held=reserved.get(n['id'],ZERO)
            if used<0 or used+held>num(n['quantity'],'نیاز'):raise ValueError('مصرف یا رزرو از نیاز بیشتر است')
    if openings:
        # Validate every chronological balance, including backdated corrections.
        for day in sorted({r['date'] for r in effective}):
            balance,_,held=_sums([r for r in effective if r['date']<=day])
            if balance<0 or sum(held.values(),ZERO)>balance:raise ValueError('موجودی یا رزرو منفی/نامعتبر است')
    p.setdefault('project_materials',[]).append(e);return deepcopy(e)
