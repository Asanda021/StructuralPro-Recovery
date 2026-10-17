"""Read-only, evidence-bound candidate-to-physical-rebar crosswalk preflight.

Does not invent shared bar IDs, attest engineering authenticity, write SQLite,
produce a payable BOQ, or clear existing blockers in Work's AEC workflows.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Mapping

POLICY = 'rebar_candidate_crosswalk_preflight_chat_v1'
EVIDENCE = 'rebar_candidate_evidence_record_v1'
EXPECTED = ('shear_wall', 'stair', 'bored_pile')
POLICIES = {'shear_wall':'shear_wall_aec_bridge_chat_v1',
            'stair':'stair_bridge_chat_preflight_v1',
            'bored_pile':'bored_pile_aec_bridge_chat_v1'}
HEX = set('0123456789abcdef')
DOC_KEYS = frozenset(('schema','project_id','owner_source_fingerprint_sha256',
                      'candidate_source_id','candidate_sha256','adapter_source_id',
                      'component_physical_id','physical_bar_id','physical_piece_id',
                      'paying_source_id','mass_kg','detail_ref','prepared_by',
                      'independent_reviewer'))

class CrosswalkError(ValueError):
    pass


def _str(x, title):
    if not isinstance(x, str) or not x or x.strip() != x:
        raise CrosswalkError(title + ': شناسه یا مرجع غیرخالی لازم است')
    return x


def _hash(x, title):
    if not isinstance(x, str) or len(x)!=64 or set(x) - HEX:
        raise CrosswalkError(title + ': هش SHA-256 کوچک معتبر لازم است')
    return x


def _amount(x):
    if isinstance(x,(bool,float)) or not isinstance(x,(int,str,Decimal)):
        raise CrosswalkError('عدد نباید float یا غیرصریح باشد')
    try: d=Decimal(x)
    except (InvalidOperation,ValueError) as e: raise CrosswalkError('عدد نامعتبر') from e
    if not d.is_finite() or d <= 0 or len(d.as_tuple().digits) > 100 or abs(d.adjusted())>100:
        raise CrosswalkError('مقدار میلگرد مثبت و متناهی در دامنه معتبر لازم است')
    return d


def _canonical(obj):
    def default(o):
        if isinstance(o,Decimal):return format(o,'f')
        raise CrosswalkError('نوع ناشناخته در سند')
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),default=default)


def _fingerprint(obj):
    return hashlib.sha256(_canonical(obj).encode('utf-8')).hexdigest()


def _candidates(previews, project_id):
    if not isinstance(previews,dict) or set(previews)!=set(EXPECTED):
        raise CrosswalkError('سه موتور شناخته‌شده الزامی‌اند')
    out={}
    for kind in EXPECTED:
        p=previews[kind]
        if not isinstance(p,dict) or p.get('policy')!=POLICIES[kind] or p.get('status')!='preview_only_not_integrated' or p.get('commit_allowed') is not False:
            raise CrosswalkError('قرارداد موتور یا حالت پیش‌نمایش نامعتبر است')
        candidates=p.get('takeoff_candidates')
        if not isinstance(candidates,list) or not candidates:
            raise CrosswalkError('ردیف‌های موتور ارائه نشده‌اند')
        for row in candidates:
            if not isinstance(row,dict) or not isinstance(row.get('params'),dict) or not isinstance(row.get('provenance'),dict):
                raise CrosswalkError('ساختار ردیف معتبر نیست')
            if row.get('id')!=row.get('source_id'):raise CrosswalkError('هویت ردیف و منبع یکسان نیست')
            sid=_str(row['source_id'],'شناسه ریزردیف')
            if sid in out:raise CrosswalkError('شناسه ریزردیف تکراری میان موتورهای سازه‌ای')
            q=row.get('quantities')
            if not isinstance(q,list) or len(q)!=1 or not isinstance(q[0],dict):
                raise CrosswalkError('ریزکمیت ناقص است')
            if q[0].get('unit')!='kg':continue
            if 'rebar' not in str(q[0].get('code','')) or q[0].get('role')!='work':
                raise CrosswalkError('ردیف kg در قرارداد میلگرد مشترک قابل شناسایی نیست')
            comp=row['params'].get('physical_component_id') or row['params'].get('component_physical_id')
            root_source=_str(row['provenance'].get('source_id'),'شناسه منبع موتور')
            _str(comp,'شناسه فیزیکی ریزردیف')
            out[sid]={'candidate_source_id':sid,'candidate_sha256':_fingerprint(row),
                      'adapter_source_id':root_source,'component_physical_id':comp,
                      'mass_kg':format(_amount(q[0].get('amount')),'f'),
                      'engine':kind,'project_id':project_id}
    return out


def template(previews, project_id):
    """Exact source-bound requests, never guessed physical bars or approved quantities."""
    _str(project_id,'شناسه پروژه')
    c=_candidates(previews,project_id)
    return {'schema':'rebar_crosswalk_unverified_template_v1','project_id':project_id,
            'commit_allowed':False,'unverified_candidate_count':len(c),
            'requests':[dict(c[sid],physical_bar_id=None,physical_piece_id=None,
                             paying_source_id=None,detail_ref=None,
                             evidence_sha256=None,independent_reviewer=None,
                             status='NEEDS_DOCUMENTED_IDENTITY') for sid in sorted(c)]}


def audit(previews:dict, ownership:dict, crosswalk:dict, documents:Mapping[str,bytes], *,project_id:str, ownership_source_data:dict|None=None, ownership_source_document:bytes|None=None):
    """Confirm *document consistency*, not engineering correctness or payment.

    Crosswalk is {policy,project_id,owner_source_fingerprint_sha256,mappings:[
    {candidate_source_id,evidence_sha256}]}. Evidence bytes must be a JSON document
    with DOC_KEYS; all identifying quantities must match the real preview and the
    explicitly reviewed ownership record. A hash alone proves integrity, not truth.
    """
    _str(project_id,'شناسه پروژه')
    candidates=_candidates(previews,project_id)
    if not isinstance(ownership,dict) or ownership.get('policy')!='shared_rebar_ownership_chat_v1' or ownership.get('project_id')!=project_id or ownership.get('status')!='preview_only_not_integrated' or ownership.get('commit_allowed') is not False:
        raise CrosswalkError('دفتر مالکیت باید پیش‌نمایش متعلق به همین پروژه باشد')
    owner_sha=_hash(ownership.get('source_fingerprint_sha256'),'هش دفتر مالکیت')
    paid=ownership.get('physical_bar_paid_once')
    if not isinstance(paid,list) or not isinstance(ownership.get('blockers'),list) or not ownership['blockers']:
        raise CrosswalkError('مالکیت فاقد نتیجه معتبر یا دلایل مسدودسازی است')
    owner_by_bar={}
    for item in paid:
        if not isinstance(item,dict): raise CrosswalkError('ادعای مالکیت دارای ساختار نامعتبر است')
        bar=_str(item.get('physical_bar_id'),'میلگرد فیزیکی دفتر')
        if bar in owner_by_bar:raise CrosswalkError('میلگرد در دفتر مالکیت دوبار مالک دارد')
        _str(item.get('physical_piece_id'),'قطعه میلگرد دفتر')
        _str(item.get('paying_source_id'),'مالک پرداخت دفتر')
        if item.get('unit')!='kg':raise CrosswalkError('واحد دفتر مالکیت نامعتبر است')
        _amount(item.get('mass_kg'))
        owner_by_bar[bar]=item
    if not isinstance(crosswalk,dict) or set(crosswalk)!= {'policy','project_id','owner_source_fingerprint_sha256','mappings'} or crosswalk['policy']!=POLICY or crosswalk['project_id']!=project_id or crosswalk['owner_source_fingerprint_sha256']!=owner_sha:
        raise CrosswalkError('Crosswalk با پروژه یا نسخه دفتر مالکیت منطبق نیست')
    mappings=crosswalk.get('mappings')
    if isinstance(mappings,list) and mappings:
        if not isinstance(ownership_source_data,dict):
            raise CrosswalkError('مدرک پایه دفتر مالکیت برای هر نگاشت الزامی است')
        from core.takeoff.shared_rebar_ownership_chat import reconcile
        verified_owner=reconcile(ownership_source_data,{'id':project_id,'takeoffs':[]},
                                 source_document=ownership_source_document)
        if (verified_owner['source_fingerprint_sha256'] != owner_sha or
            verified_owner['physical_bar_paid_once'] != paid):
            raise CrosswalkError('خروجی دفتر مالکیت با ادعاهای منبع مطابقت ندارد')
    if not isinstance(mappings,list) or not isinstance(documents,Mapping):
        raise CrosswalkError('فهرست نگاشت یا فایل شواهد نامعتبر است')
    used_rows=set();used_bars=set();checked=[]
    for m in mappings:
        if not isinstance(m,dict) or set(m)!={'candidate_source_id','evidence_sha256'}:
            raise CrosswalkError('ورودی نگاشت باید به شناسه ردیف و هش سند محدود باشد')
        sid=_str(m['candidate_source_id'],'شناسه ردیف نگاشت')
        if sid in used_rows or sid not in candidates:raise CrosswalkError('ردیف تکراری یا ناشناخته است')
        used_rows.add(sid)
        h=_hash(m['evidence_sha256'],'هش سند نگاشت')
        content=documents.get(h)
        if not isinstance(content,bytes) or hashlib.sha256(content).hexdigest()!=h:
            raise CrosswalkError('سند نگاشت وجود ندارد یا هش آن نادرست است')
        try: d=json.loads(content.decode('utf-8'))
        except (UnicodeError,json.JSONDecodeError) as e:raise CrosswalkError('سند نگاشت JSON معتبر نیست') from e
        if not isinstance(d,dict) or set(d)!=DOC_KEYS or d.get('schema')!=EVIDENCE:
            raise CrosswalkError('ساختار سند نگاشت نامعتبر است')
        c=candidates[sid]
        for k in ('project_id','candidate_source_id','candidate_sha256','adapter_source_id','component_physical_id'):
            if d.get(k)!=c[k]:raise CrosswalkError('سند با هویت ریزردیف یا هش محاسبه منطبق نیست: '+k)
        if d.get('owner_source_fingerprint_sha256')!=owner_sha:raise CrosswalkError('سند به نسخه دیگری از دفتر مالکیت متصل است')
        bar=_str(d.get('physical_bar_id'),'شناسه میلگرد در سند')
        if bar in used_bars:raise CrosswalkError('یک میلگرد فیزیکی دوبار قابل پرداخت معرفی شده است')
        used_bars.add(bar)
        owner=owner_by_bar.get(bar)
        if owner is None:raise CrosswalkError('میلگرد سند در دفتر مالکیت وجود ندارد')
        if d.get('physical_piece_id')!=owner['physical_piece_id'] or d.get('paying_source_id')!=owner['paying_source_id']:
            raise CrosswalkError('مالک پرداخت یا قطعه فیزیکی در سند و دفتر متفاوت است')
        if d['paying_source_id']!=c['adapter_source_id']:
            raise CrosswalkError('این ردیف مالک پرداخت نیست؛ ارجاع اطلاعاتی نباید پرداخت دوم بسازد')
        if _amount(d.get('mass_kg'))!=_amount(c['mass_kg']) or _amount(owner['mass_kg'])!=_amount(c['mass_kg']):
            raise CrosswalkError('جرم دقیق موتور، مدرک و دفتر مالکیت مغایر است')
        _str(d.get('detail_ref'),'مدرک دیتایل')
        preparer=_str(d.get('prepared_by'),'تهیه‌کننده')
        reviewer=_str(d.get('independent_reviewer'),'بازبین سند')
        if preparer.casefold()==reviewer.casefold():raise CrosswalkError('بازبین مستقل باید از تهیه‌کننده متفاوت باشد')
        checked.append({'candidate_source_id':sid,'physical_bar_id':bar,'evidence_sha256':h,
                        'kg_exact':c['mass_kg'],'status':'DOCUMENT_CONSISTENT_NOT_ENGINEER_APPROVED'})
    missing=sorted(set(candidates)-used_rows)
    return {'policy':POLICY,'project_id':project_id,'status':'BLOCKED_FOR_COMMIT','commit_allowed':False,
            'kg_rows':len(candidates),'document_consistent_rows':len(checked),
            'undocumented_rows':len(missing),'undocumented_source_ids':missing,
            'document_consistent_links':checked,'ownership_snapshot_sha256':owner_sha,
            'blockers':['مدرک دارای هش معتبر معادل تأیید اصالت طراحی یا امضای مهندس نیست',
                        'تمام اسناد مهندسی، میلگردهای مشترک، و ردیف‌های تاریخی در SQLite باید مستقل تطبیق شوند',
                        'اتصال گردش واقعی CAS/اصلاحیه/BOQ و پذیرش Windows هنوز انجام نشده است',
                        'ردیف‌های فاقد نگاشت مستند: '+str(len(missing))],
            'source_change_policy':'read_only_no_mutation_or_payment'}
