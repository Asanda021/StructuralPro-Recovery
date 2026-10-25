"""Site operations use the existing project command journal and store transaction.

Actor declarations attribute local work; they do not authenticate human identity.
No operation here contacts suppliers or sends project data externally.
"""
from copy import deepcopy
from core.projects.controls import text,num,evidence,find,digest
from core.commercial.exact_values import exact

POLICY_KEYS=('site_policy_versions','site_purchase_handoffs')

def keys():
    from core.projects import site_resources,site_materials,site_office
    return POLICY_KEYS+site_resources.KEYS+site_materials.KEYS+site_office.KEYS

@exact
def dispatch(p,op,data,actor,reason):
    if data.get('project_id',p['id'])!=p['id']:raise ValueError('شناسه پروژه سند ناسازگار است')
    if op=='policy':
        versions=p.setdefault('site_policy_versions',[])
        owner=p.get('metadata',{}).get('financial_owner_id') or (versions[-1]['owner'] if versions else None)
        if owner is None:
            if data.get('establish_owner') is not True:raise ValueError('ثبت صریح مالک و مدرک لازم است')
            owner=text(data.get('owner'),'مالک')
        if actor!=owner or data.get('owner')!=owner:raise ValueError('فقط مالک ثبت‌شده می‌تواند مجوزها را تعیین کند')
        permissions=data.get('permissions')
        if not isinstance(permissions,dict) or set(permissions)!={'create','review','approve','issue','adjust','finance'}:raise ValueError('مجوزهای صریح همه عملیات لازم است')
        for names in permissions.values():
            if not isinstance(names,list) or not names or len(set(names))!=len(names):raise ValueError('فهرست مسئولان مجاز نامعتبر است')
            for name in names:text(name,'مسئول مجاز')
        r={'version':len(versions)+1,'owner':owner,'permissions':deepcopy(permissions),'source':evidence(data.get('source')),'reason':reason,'created_by':actor,'identity_limitation':'local attribution; not authenticated identity'}
        r['sha256']=digest(r);versions.append(r);return r
    versions=p.get('site_policy_versions',[])
    if not versions:raise ValueError('ابتدا مالک و مجوزهای مستند کارگاه ثبت شوند')
    permission='finance' if op=='purchase_commit' else 'review' if op.endswith('_review') else 'approve' if op.endswith('_approve') or op=='daily_transfer' else 'issue' if op.endswith('_issue') else 'adjust' if op.endswith(('_correct','_cancel','_amend')) else 'create'
    if actor not in versions[-1]['permissions'][permission]:raise ValueError('مسئول برای این عملیات مجوز ثبت‌شده ندارد')
    from core.projects import site_resources,site_materials
    if op=='purchase_commit':
        from core.projects.scheduling import WorkCalendar
        purchase=find(p.get('purchase_drafts',[]),data.get('id'),'درخواست خرید')
        if data.get('confirmed') is not True or purchase['status']!='approved':raise ValueError('تأیید صریح تبدیل درخواست مصوب لازم است')
        if any(x['purchase_id']==purchase['id'] for x in p.get('site_purchase_handoffs',[])):raise ValueError('درخواست قبلاً به دفتر مالی منتقل شده است')
        when=WorkCalendar.valid_date(data.get('date')).isoformat()
        if when<purchase['as_of'] or not site_materials._purchase_view(p,purchase,when)['current']:raise ValueError('مبنای مقدار یا موجودی درخواست در تاریخ تبدیل تغییر کرده یا نامشخص است')
        if purchase.get('price') is None or not purchase.get('supplier') or purchase.get('currency') not in {'IRR','IRT'}:raise ValueError('نرخ، واحد پول و تأمین‌کننده مستند لازم است')
        evidence(purchase['price_source'])
        amount=num(purchase['quantity'],'مقدار')*num(purchase['price'],'نرخ')
        if amount<=0:raise ValueError('مبلغ باید مثبت باشد')
        result={'purchase_id':purchase['id'],'ledger_id':data['ledger_id'],'amount':str(amount),'currency':purchase['currency'],'counterparty':text(purchase['supplier'],'تأمین‌کننده'),'date':WorkCalendar.valid_date(data.get('date')).isoformat(),'reference':'SITE-PR:'+purchase['id'],'description':'درخواست خرید '+purchase['id']+' — '+purchase['specification'],'source_documents':[{'ref':purchase['price_source']['reference'],'path':purchase['price_source']['path'],'sha256':purchase['price_source']['sha256']}],'created_by':actor,'reason':reason,'purchase_digest':digest(purchase)}
        p.setdefault('site_purchase_handoffs',[]).append(result);return result
    if op in site_resources.OPS:return site_resources.dispatch(p,op,data,actor,reason)
    if op in site_materials.OPS:return site_materials.dispatch(p,op,data,actor,reason)
    from core.projects import site_office
    return site_office.dispatch(p,op,data,actor,reason)
