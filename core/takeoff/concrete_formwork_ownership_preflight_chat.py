"""Fail-closed, read-only concrete/formwork ownership preflight for StructuralPro.

Pure domain checks only. This module does not infer geometric intersections,
subtract concrete, decide whether a surface needs forms, write SQLite, generate
prices, grant engineering acceptance, or authorize financial commit.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, Context, Inexact, Rounded, localcontext
from collections.abc import Mapping
import hashlib
import json

POLICY = "concrete_formwork_ownership_preflight_chat_v1"
EVIDENCE_POLICY = "concrete_formwork_scope_evidence_v1"
ENGINES = ("shear_wall", "stair", "bored_pile")
ENGINE_POLICIES = {
    "shear_wall": "shear_wall_aec_bridge_chat_v1",
    "stair": "stair_bridge_chat_preflight_v1",
    "bored_pile": "bored_pile_aec_bridge_chat_v1",
}
EVIDENCE_FIELDS = frozenset({
    "schema", "project_id", "candidate_source_id", "candidate_sha256",
    "engine", "physical_component_id", "operation", "unit", "quantity_exact",
    "scope_id", "coordinate_ref", "geometry_document_sha256", "paying_source_id",
    "detail_ref", "prepared_by", "independent_reviewer", "interface_review_status",
})
HEX = frozenset("0123456789abcdef")


class OwnershipPreflightError(ValueError):
    """Invalid or unsafe source claim; never silently downgrade to zero."""


def ident(value, field):
    if not isinstance(value, str) or not value or value != value.strip() or any(ord(c)<32 for c in value):
        raise OwnershipPreflightError(field + ": شناسه/مرجع صریح معتبر الزامی است")
    return value


def sha(value, field):
    if not isinstance(value, str) or len(value) != 64 or not set(value) <= HEX:
        raise OwnershipPreflightError(field + ": SHA-256 کوچک معتبر الزامی است")
    return value


def amount(value):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise OwnershipPreflightError("مقدار باید رشته دهدهی یا Decimal دقیق باشد")
    if isinstance(value, str) and (not value or value != value.strip()):
        raise OwnershipPreflightError("مقدار اعشاری خالی یا دارای فاصله مجاز نیست")
    try:
        d = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise OwnershipPreflightError("مقدار دهدهی معتبر نیست") from exc
    if not d.is_finite() or d <= 0 or len(d.as_tuple().digits) > 150 or abs(d.adjusted()) > 150:
        raise OwnershipPreflightError("مقدار مثبت متناهی در دامنه معتبر الزامی است")
    return d


def canonical(obj):
    def norm(item):
        if isinstance(item, Decimal):
            if not item.is_finite():
                raise OwnershipPreflightError("عدد نامتناهی در سند")
            return format(item, 'f')
        if isinstance(item, float):
            raise OwnershipPreflightError("عدد float در سند غیرمجاز است")
        if isinstance(item, dict):
            if any(not isinstance(k,str) for k in item):
                raise OwnershipPreflightError("کلید غیرمتنی در سند")
            return {k:norm(v) for k,v in item.items()}
        if isinstance(item, (tuple,list)):
            return [norm(v) for v in item]
        if item is None or isinstance(item,(str,bool,int)):
            return item
        raise OwnershipPreflightError("نوع ناسازگار در سند")
    return json.dumps(norm(obj), sort_keys=True, ensure_ascii=False, separators=(',',':'), allow_nan=False)


def digest(obj):
    return hashlib.sha256(canonical(obj).encode('utf-8')).hexdigest()


def _operation(engine, code, unit):
    if not isinstance(code,str):
        raise OwnershipPreflightError("کد ریزکمیت نامعتبر است")
    is_concrete = (
        (engine == 'shear_wall' and code == 'shear_wall_concrete') or
        (engine == 'stair' and code.startswith('stair_') and code.endswith('_concrete')) or
        (engine == 'bored_pile' and code == 'bored_pile_concrete')
    )
    is_formwork = (
        (engine == 'shear_wall' and code in ('shear_wall_formwork_main','shear_wall_formwork_edge')) or
        (engine == 'stair' and code == 'stair_formwork') or
        (engine == 'bored_pile' and code == 'bored_pile_formwork')
    )
    if is_concrete and unit == 'm3':
        return 'concrete'
    if is_formwork and unit == 'm2':
        return 'formwork'
    raise OwnershipPreflightError('کد و واحد بتن/قالب منطبق نیستند')


def _claims(previews, project):
    if not isinstance(project,dict) or not isinstance(project.get('id'),str):
        raise OwnershipPreflightError('Snapshot معتبر پروژه الزامی است')
    project_id=ident(project['id'],'شناسه پروژه')
    if not isinstance(previews,dict) or set(previews)!=set(ENGINES):
        raise OwnershipPreflightError('هر سه پیش‌نمایش واقعی الزامی‌اند')
    existing=project.get('takeoffs') or []
    if not isinstance(existing,list):
        raise OwnershipPreflightError('ریزمتری‌های تاریخی نامعتبرند')
    old_ids=set()
    for row in existing:
        if not isinstance(row,dict) or not isinstance(row.get('source_id'),str):
            raise OwnershipPreflightError('ردیف تاریخی ناقص است')
        if row['source_id'] in old_ids:
            raise OwnershipPreflightError('تکرار شناسه در برداشت تاریخی')
        old_ids.add(row['source_id'])
    output={}
    for engine in ENGINES:
        p=previews[engine]
        if not isinstance(p,dict) or p.get('policy')!=ENGINE_POLICIES[engine] or p.get('status')!='preview_only_not_integrated' or p.get('commit_allowed') is not False:
            raise OwnershipPreflightError('قرارداد پیش‌نمایش تخصصی یا وضعیت ثبت ناامن است')
        rows=p.get('takeoff_candidates')
        if not isinstance(rows,list) or not rows:
            raise OwnershipPreflightError('برداشت موتور خالی/نامعتبر است')
        for row in rows:
            if not isinstance(row,dict) or not isinstance(row.get('params'),dict) or not isinstance(row.get('provenance'),dict):
                raise OwnershipPreflightError('ردیف فاقد هویت معتبر است')
            sid=ident(row.get('source_id'),'شناسه برداشت')
            if row.get('id') != sid or sid in old_ids or sid in output:
                raise OwnershipPreflightError('شناسه تکراری یا متعارض با داده تاریخی')
            q=row.get('quantities')
            if not isinstance(q,list) or len(q)!=1 or not isinstance(q[0],dict):
                raise OwnershipPreflightError('هر برداشت باید یک ریزکمیت داشته باشد')
            if q[0].get('unit')=='kg':
                if not isinstance(q[0].get('code'),str) or 'rebar' not in q[0]['code'] or q[0].get('role')!='work':
                    raise OwnershipPreflightError('ردیف غیر بتن/قالب خارج از قرارداد است')
                amount(q[0].get('amount'))
                continue
            op=_operation(engine,q[0].get('code'),q[0].get('unit'))
            if q[0].get('role')!='work':
                raise OwnershipPreflightError('ردیف غیرقابل پرداخت در خروجی مثبت وجود دارد')
            d=amount(q[0].get('amount'))
            component=ident(row['params'].get('physical_component_id') or row['params'].get('component_physical_id'),'هویت جزء')
            source=ident(row['provenance'].get('source_id'),'منبع اصلی موتور')
            origin=ident(row['params'].get('source_input_sha256'),'هش منبع محاسبه')
            sha(origin,'هش داده اصلی')
            params=row['params']
            deductions=params.get('intersections',[])
            if not isinstance(deductions,list) or any(not isinstance(x,dict) or not isinstance(x.get('id'),str) or not isinstance(x.get('source_ref'),str) or amount(x.get('volume_m3'))<=0 for x in deductions):
                raise OwnershipPreflightError('قرارداد کسورات مستند نامعتبر است')
            if len({x['id'] for x in deductions}) != len(deductions):
                raise OwnershipPreflightError('کسور فیزیکی تکراری است')
            if 'gross_concrete_m3' in params:
                if op!='concrete':
                    raise OwnershipPreflightError('حجم ناخالص فقط برای بتن مجاز است')
                gross=amount(params['gross_concrete_m3'])
                if gross < d:
                    raise OwnershipPreflightError('حجم ناخالص از خالص کمتر است')
                # Existing adapter declares its deductions in net concrete; never deduct twice.
                with localcontext(Context(prec=2048)) as ctx:
                    ctx.traps[Inexact]=True
                    ctx.traps[Rounded]=True
                    deduction=sum((amount(x['volume_m3']) for x in deductions),Decimal(0))
                    if gross-deduction != d:
                        raise OwnershipPreflightError('تطبیق حجم ناخالص، کسورات و خالص برقرار نیست')
            coordinate=params.get('coordinate_ref') or None
            if coordinate is not None:
                ident(coordinate,'دستگاه مختصات')
            # Preserve all row metadata in the fingerprint; preview is never rewritten.
            output[sid]={
                'project_id':project_id, 'engine':engine, 'candidate_source_id':sid,
                'candidate_sha256':digest(row), 'source_input_sha256':origin,
                'adapter_source_id':source,'physical_component_id':component,
                'operation':op,'unit':q[0]['unit'],'quantity_exact':format(d,'f'),
                'coordinate_ref_in_adapter':coordinate,
                'existing_deduction_ids':sorted(ident(x.get('id'),'شناسه کسر') for x in deductions),
            }
    if not output:
        raise OwnershipPreflightError('ردیف بتن یا قالب یافت نشد')
    return output


def request_template(previews,project):
    """Make data-entry requests, NOT guesses or acceptance certificates."""
    claims=_claims(previews,project)
    return {'policy':POLICY,'project_id':project['id'],'status':'NEEDS_DOCUMENTS',
            'commit_allowed':False,'requests':[
                {**claims[sid],'scope_id':None,'geometry_document_sha256':None,
                 'paying_source_id':None,'detail_ref':None,'independent_reviewer':None,
                 'interface_review_status':'NOT_REVIEWED',
                 'status':'NEEDS_VERIFIED_CONCRETE_OR_FORMWORK_SCOPE'}
                for sid in sorted(claims)]}


def audit(previews,project,ledger,documents):
    """Validate submitted source-bound evidence; always BLOCK commit.

    Ledger: {'policy':POLICY,'project_id':id,'mappings':
             [{'candidate_source_id':id,'evidence_sha256':sha}]}.
    Document bytes are UTF-8 JSON with exactly EVIDENCE_FIELDS.
    A successful match establishes *internal document consistency only*.
    """
    claims=_claims(previews,project)
    if not isinstance(ledger,dict) or set(ledger)!={'policy','project_id','mappings'} or ledger['policy']!=POLICY or ledger['project_id']!=project['id']:
        raise OwnershipPreflightError('دفتر ادعای مالکیت با پروژه سازگار نیست')
    mappings=ledger['mappings']
    if not isinstance(mappings,list) or not isinstance(documents,Mapping):
        raise OwnershipPreflightError('ورودی نگاشت و اسناد معتبر لازم است')
    used=set(); scopes={}; checked=[];unknown_coords=[]
    for mapping in mappings:
        if not isinstance(mapping,dict) or set(mapping)!={'candidate_source_id','evidence_sha256'}:
            raise OwnershipPreflightError('ساختار نگاشت مجاز نیست')
        sid=ident(mapping['candidate_source_id'],'شناسه منبع')
        if sid not in claims or sid in used:
            raise OwnershipPreflightError('نگاشت تکراری یا خارج از ریزمتره')
        used.add(sid)
        h=sha(mapping['evidence_sha256'],'هش سند')
        b=documents.get(h)
        if not isinstance(b,bytes) or hashlib.sha256(b).hexdigest()!=h:
            raise OwnershipPreflightError('سند یافت نشد یا محتوا با SHA-256 ناسازگار است')
        def no_duplicate_pairs(pairs):
            result={}
            for key,value in pairs:
                if key in result:
                    raise ValueError('duplicate JSON key')
                result[key]=value
            return result
        try:
            doc=json.loads(b.decode('utf-8'),parse_float=Decimal,parse_int=int,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')),
                           object_pairs_hook=no_duplicate_pairs)
        except (UnicodeDecodeError,ValueError,TypeError) as exc:
            raise OwnershipPreflightError('سند JSON خوانا و معتبر نیست') from exc
        if not isinstance(doc,dict) or set(doc)!=EVIDENCE_FIELDS or doc['schema']!=EVIDENCE_POLICY:
            raise OwnershipPreflightError('قرارداد سند ناشناخته یا ناقص است')
        c=claims[sid]
        for key in ('project_id','candidate_source_id','candidate_sha256','engine','physical_component_id','operation','unit'):
            if doc.get(key)!=c[key]:
                raise OwnershipPreflightError('سند به نسخه دیگری از ریزمتره تعلق دارد: '+key)
        if not isinstance(doc['quantity_exact'],str):
            raise OwnershipPreflightError('مقدار سند باید رشته دهدهی دقیق باشد')
        if amount(doc['quantity_exact'])!=amount(c['quantity_exact']):
            raise OwnershipPreflightError('مقدار سند و برداشت برابر نیست')
        ident(doc.get('scope_id'),'هویت محدوده بتن یا وجه قالب')
        coord=ident(doc.get('coordinate_ref'),'دستگاه مختصات سند')
        geometry_hash=sha(doc.get('geometry_document_sha256'),'هش نقشه/دیتایل هندسه')
        geometry_bytes=documents.get(geometry_hash)
        if not isinstance(geometry_bytes,bytes) or not geometry_bytes or hashlib.sha256(geometry_bytes).hexdigest()!=geometry_hash:
            raise OwnershipPreflightError('فایل بایتی نقشه/مدرک هندسی وجود ندارد یا هش آن معتبر نیست')
        if doc.get('paying_source_id')!=sid:
            raise OwnershipPreflightError('فقط همین ردیف می‌تواند مالک پرداخت اعلام‌شده باشد')
        ident(doc.get('detail_ref'),'ارجاع دیتایل')
        preparer=ident(doc.get('prepared_by'),'تهیه‌کننده')
        reviewer=ident(doc.get('independent_reviewer'),'بازبین مستقل')
        if preparer.casefold()==reviewer.casefold():
            raise OwnershipPreflightError('بازبین باید از تهیه‌کننده متفاوت باشد')
        if doc.get('interface_review_status')!='UNVERIFIED_NEEDS_CROSS_MEMBER_GEOMETRY':
            raise OwnershipPreflightError('این ابزار وضعیت تماس هندسی را تأییدشده نمی‌پذیرد')
        if c['coordinate_ref_in_adapter'] is not None and coord != c['coordinate_ref_in_adapter']:
            raise OwnershipPreflightError('مرجع مختصات سند با موتور مغایر است')
        if c['coordinate_ref_in_adapter'] is None:
            unknown_coords.append(sid)
        key=(c['operation'],doc['scope_id'])
        if key in scopes:
            raise OwnershipPreflightError('دو ردیف مثبت به یک حجم/وجه فیزیکی مشترک حق پرداخت می‌دهند')
        scopes[key]=sid
        checked.append({'candidate_source_id':sid,'engine':c['engine'],'operation':c['operation'],
                        'scope_id':doc['scope_id'],'quantity_exact':c['quantity_exact'],
                        'unit':c['unit'],'evidence_sha256':h,
                        'status':'DOCUMENT_CONSISTENT_NOT_ENGINEER_VERIFIED'})
    missing=sorted(set(claims)-used)
    blockers=[
        'اصالت مهندسی و اختیار امضای اسنادِ ارائه‌شده در Chat احراز نشده است',
        'اشتراک حجمی بتن، فصل مشترک/سطح تماس قالب و رکوردهای تاریخی باید با نقشه و هویت واقعی بررسی شوند',
        'این کنترل هیچ حجم یا سطحی را خودکار کسر، تقسیم یا به پرداخت مجاز تبدیل نمی‌کند',
        'گردش رسمی SQLite/CAS/اصلاحیه، BOQ و آزمون Windows هنوز متصل نشده‌اند',
    ]
    if missing:blockers.append('ردیف‌های بتن/قالب بدون سند تطبیق: '+str(len(missing)))
    if unknown_coords:blockers.append('مرجع مختصات در Adapter برای ردیف‌های زیر موجود نیست: '+str(len(unknown_coords)))
    if project.get('takeoffs'):blockers.append('هویت و سطوح برداشت‌های تاریخی باید مستقل تطبیق شوند')
    return {'policy':POLICY,'project_id':project['id'],'status':'BLOCKED_FOR_COMMIT',
            'commit_allowed':False,'candidate_count':len(claims),
            'candidate_count_by_operation':{op:sum(c['operation']==op for c in claims.values()) for op in ('concrete','formwork')},
            'document_consistent_count':len(checked),'undocumented_count':len(missing),
            'undocumented_source_ids':missing,'coordinate_unanchored_count':len(unknown_coords),
            'reviewed_evidence':checked,'blockers':blockers,
            'source_change_policy':'read_only_no_sqlite_no_pricebook_no_approval'}
