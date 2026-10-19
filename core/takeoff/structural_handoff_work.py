"""Snapshot-bound pre-integration audit; cannot grant financial authority.

The Chat engines and ownership guards remain authoritative and unchanged.
Versioned audit provenance uses the existing project JSON; no payment ledger is created.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from core.takeoff.manual_formula_register import read

SCHEMA='structural_handoff_audit_work_v1'
KINDS=('shear_wall','stair','bored_pile')

def parse_request(content):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('کلید تکراری در سند ورودی')
            result[key]=value
        return result
    def nonfinite(_):raise ValueError('عدد نامتناهی مجاز نیست')
    # Decimal tokens remain exact strings; never pass a binary float to engines.
    return json.loads(content,parse_float=str,parse_constant=nonfinite,object_pairs_hook=pairs)

def _no_float(value):
    if isinstance(value,float):raise ValueError('عدد اعشاری باید رشته دقیق باشد')
    if isinstance(value,dict):
        for v in value.values():_no_float(v)
    elif isinstance(value,list):
        for v in value:_no_float(v)

def preview(service,project_id,request,*,source_path,source_sha256,evidence_files=None):
    from core.takeoff.building_six_family_ownership_chat import POLICY, audit
    if isinstance(request,dict) and request.get("policy")==POLICY:
        project,token=read(service,project_id)
        data,documents=_files(request,source_path,source_sha256,evidence_files)
        result=audit(request,basis(project),documents=documents)
        if service.store.current_digest(project_id)!=token or _files(request,source_path,source_sha256,evidence_files)[0]!=data:
            raise RuntimeError("پروژه یا مدرک هنگام ممیزی تغییر کرد")
        return {"schema":SCHEMA,"status":"BLOCKED_FOR_COMMIT","ready_for_boq":False,
                "commit_allowed":False,"rows":[],"project_id":project_id,
                "snapshot_digest":token,"source_sha256":source_sha256,
                "audit":result,"blockers":deepcopy(result["blockers"])}
    if isinstance(request, dict) and 'policy' in request:
        return _preview_contract(service, project_id, request, source_path=source_path, source_sha256=source_sha256)
    fields={'schema','inputs','source_ids','rebar_ownership','reviewer','review_reference'}
    if not isinstance(request,dict) or set(request)!=fields or request['schema']!=SCHEMA:
        raise ValueError('قرارداد ورودی پیش‌ارزیابی نامعتبر است')
    _no_float(request)
    path=Path(source_path)
    if not path.is_file() or path.stat().st_size>16*1024*1024:raise ValueError('سند ورودی معتبر لازم است')
    raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
    if not isinstance(source_sha256,str) or sha!=source_sha256.lower():raise ValueError('هش سند ورودی تغییر کرده است')
    if parse_request(raw.decode('utf-8-sig'))!=request:raise ValueError('ورودی و سند دارای هش یکسان نیستند')
    if not isinstance(request['inputs'],dict) or set(request['inputs'])!=set(KINDS):raise ValueError('ورودی هر سه موتور لازم است')
    if not isinstance(request['source_ids'],dict) or set(request['source_ids'])!=set(KINDS):raise ValueError('شناسه سه منبع لازم است')
    project,token=read(service,project_id)
    from core.takeoff.shear_wall_bridge_chat import compile_preview as wall
    from core.takeoff.stair_bridge_chat import compile_preview as stair
    from core.takeoff.bored_pile_bridge_chat import compile_preview as pile
    from core.takeoff.shared_rebar_ownership_chat import reconcile
    from core.takeoff.structural_four_package_preflight_chat import audit
    from core.takeoff.rebar_crosswalk_preflight_chat import template
    from core.takeoff.concrete_formwork_ownership_preflight_chat import request_template
    d=request['inputs'];reviewer=request['reviewer'];ref=request['review_reference']
    for kind in ('shear_wall','bored_pile'):
        if d[kind]['source']['source_id']!=request['source_ids'][kind]:raise ValueError('شناسه منبع و موتور ناسازگار است')
    previews={
        'shear_wall':wall(d['shear_wall'],project,reviewer=reviewer,review_reference=ref),
        'stair':stair(d['stair'],project,source_id=request['source_ids']['stair'],reviewer=reviewer,ownership_reference=ref),
        'bored_pile':pile(d['bored_pile'],project,independent_reviewer=reviewer,ownership_reference=ref),
    }
    owner=reconcile(request['rebar_ownership'],project)
    combined=audit(previews,request['source_ids'],owner,project)
    bars=template(previews,project_id);concrete=request_template(previews,project)
    if service.store.current_digest(project_id)!=token:raise RuntimeError('نسخه پروژه هنگام پیش‌ارزیابی تغییر کرد؛ دوباره محاسبه کنید')
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=sha:
        raise RuntimeError('سند ورودی هنگام پیش‌ارزیابی تغییر کرده است')
    rows=[]
    for kind,result in previews.items():
        for row in result['takeoff_candidates']:
            q=row['quantities'][0]
            rows.append({'engine':kind,'source_id':row['source_id'],'description':row['description'],
                         'quantity':q['amount'],'unit':q['unit'],'formula':q['formula']})
    return {'schema':SCHEMA,'status':'BLOCKED_FOR_COMMIT','commit_allowed':False,
            'project_id':project_id,'snapshot_digest':token,'source_sha256':sha,
            'combined':combined,'rebar_crosswalk_requests':bars,
            'concrete_formwork_requests':concrete,'rows':rows,
            'blockers':deepcopy(combined['blockers'])}


# Explicit allowlist: only existing immutable preview contracts are exposed.
# Payloads never choose arbitrary modules, functions, database writes or BOQ APIs.
_CONTRACT_MODULES = (
    'column_joint_preflight', 'column_joint_beam_panel',
    'column_joint_bar_crosswalk', 'column_joint_rebar_completion',
    'column_joint_footing_tie', 'column_joint_starter_development',
    'column_joint_interface_surface', 'phase1_shared_materials_audit',
    'phase1_multi_member_overlap', 'phase1_five_domain_claims',
)

def _preview_contract(service, project_id, request, *, source_path, source_sha256):
    from importlib import import_module
    from core.takeoff.bored_pile_ownership_preflight import read_evidence
    modules = [import_module('core.takeoff.' + name) for name in _CONTRACT_MODULES]
    module = next((m for m in modules if m.POLICY == request.get('policy')), None)
    if module is None:
        raise ValueError('قرارداد ممیزی در این فرم پشتیبانی نمی‌شود')
    document = read_evidence(source_path, source_sha256)
    if document != request:
        raise ValueError('محتوای فرم با سند مستقل برابر نیست')
    project, token = read(service, project_id)
    if module.__name__.endswith(('phase1_shared_materials_audit', 'phase1_five_domain_claims')):
        result = module.audit(project, document)
    else:
        result = module.preview(document, project)
    if (result.get('ready_for_boq') is not False or
            result.get('commit_allowed') is not False or result.get('rows') != []):
        raise ValueError('قرارداد پیش‌ممیزی نباید مجوز مالی صادر کند')
    if service.store.current_digest(project_id) != token:
        raise RuntimeError('نسخه پروژه هنگام ممیزی تغییر کرد؛ دوباره اجرا کنید')
    if read_evidence(source_path, source_sha256) != request:
        raise RuntimeError('مدرک هنگام ممیزی تغییر کرد؛ دوباره اجرا کنید')
    return {'schema': SCHEMA, 'status': 'BLOCKED_FOR_COMMIT',
            'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
            'project_id': project_id, 'snapshot_digest': token,
            'source_sha256': source_sha256, 'audit': deepcopy(result),
            'blockers': deepcopy(result.get('blockers', []))}


# Audit provenance inside the existing ProjectStore JSON, never a payable ledger.
_AUDITS = 'structural_handoff_audits'
_HISTORY = 'structural_handoff_history'


def basis(project):
    return {k: deepcopy(v) for k, v in project.items()
            if k not in ('_meta', _AUDITS, _HISTORY)}


def project_basis(service, project_id):
    return basis(read(service, project_id)[0])


def _hash(value):
    from core.takeoff.building_six_family_ownership_chat import _digest
    return _digest(value)


def _identity(value):
    from core.takeoff.building_six_family_ownership_chat import _name, _alias
    return _alias(_name(value, 'شناسه ممیزی'))


def _revision(value, current):
    if type(value) is not int or value < 0:
        raise ValueError('شماره نسخه باید عدد صحیح صریح باشد')
    if value != current:
        raise RuntimeError('نسخه ممیزی کهنه است؛ دوباره باز کنید')


def _files(request, source_path, source_sha256, evidence_files):
    import base64
    from core.takeoff.bored_pile_ownership_preflight import read_evidence
    from core.takeoff.building_six_family_ownership_chat import POLICY
    if not isinstance(request, dict) or request.get('policy') != POLICY:
        raise ValueError('قرارداد مالکیت شش خانواده لازم است')
    if read_evidence(source_path, source_sha256) != request:
        raise ValueError('محتوای درخواست با مدرک مستقل برابر نیست')
    if not isinstance(evidence_files, dict):
        raise ValueError('فایل‌های مدارک مستقل لازم است')
    try:
        required = {x['evidence_sha256'] for x in request['claims']}
        required.update(x['geometry_evidence_sha256'] for x in request['interfaces'])
    except (KeyError, TypeError) as exc:
        raise ValueError('فهرست مدارک مالکیت ناقص است') from exc
    if set(evidence_files) != required:
        raise ValueError('مدارک لازم و فایل‌های ارائه‌شده برابر نیستند')
    raw = Path(source_path).read_bytes()
    content = {}; encoded = {}; total = len(raw)
    for sha, path in evidence_files.items():
        p = Path(path)
        if not p.is_file() or not 0 < p.stat().st_size <= 4*1024*1024:
            raise ValueError('مدرک مستقل خوانا و محدود لازم است')
        value = p.read_bytes(); total += len(value)
        if hashlib.sha256(value).hexdigest() != sha:
            raise ValueError('SHA-256 مدرک مستقل نادرست است')
        content[sha] = value
        encoded[sha] = base64.b64encode(value).decode('ascii')
    if total > 16*1024*1024:
        raise ValueError('حجم مجموعه مدارک بیش از حد مجاز است')
    if hashlib.sha256(raw).hexdigest() != source_sha256:
        raise ValueError('سند هنگام خواندن تغییر کرده است')
    return {'request': deepcopy(request), 'source_path': str(Path(source_path).resolve()),
            'source_sha256': source_sha256, 'source_bytes': base64.b64encode(raw).decode('ascii'),
            'evidence_files': {k:str(Path(v).resolve()) for k,v in evidence_files.items()},
            'evidence_bytes': encoded}, content


def _validate_record(record):
    import base64
    try:
        if type(record['revision']) is not int or record['revision']<1:
            raise ValueError('نسخه رکورد ممیزی نامعتبر است')
        data=record['data']
        if record['input_digest'] != _hash(data):raise ValueError('هش ورودی ذخیره‌شده ناسازگار است')
        raw=base64.b64decode(data['source_bytes'], validate=True)
        if hashlib.sha256(raw).hexdigest()!=data['source_sha256'] or parse_request(raw.decode('utf-8-sig'))!=data['request']:
            raise ValueError('منشأ سند ذخیره‌شده ناسازگار است')
        for sha, value in data['evidence_bytes'].items():
            if hashlib.sha256(base64.b64decode(value,validate=True)).hexdigest()!=sha:
                raise ValueError('مدرک ذخیره‌شده ناسازگار است')
        if set(data['evidence_files'])!=set(data['evidence_bytes']):
            raise ValueError('فهرست مدارک ذخیره‌شده ناسازگار است')
        result=record['result']
        status='draft' if result is None else 'checked_nonfinancial' if result.get('document_consistent') else 'blocked'
        if record['status']!=status or (result is None and record['result_digest'] is not None):
            raise ValueError('وضعیت ممیزی ناسازگار است')
        if result is not None:
            if record['result_digest']!=_hash(result) or result.get('ready') is not False or result.get('commit_allowed') is not False or result.get('payable_rows')!=[]:
                raise ValueError('نتیجه ممیزی یا قفل مالی ناسازگار است')
    except (KeyError,TypeError,UnicodeError) as exc:
        raise ValueError('رکورد ممیزی ناقص است') from exc


def guard(previous, updated, command):
    """Called inside ProjectStore's existing SQLite/CAS transaction."""
    old=previous.get(_AUDITS,{}) ; new=updated.get(_AUDITS,{})
    history=previous.get(_HISTORY,[])
    if command is None:
        if old!=new or history!=updated.get(_HISTORY,[]):
            raise ValueError('تغییر سوابق ممیزی فقط از سرویس نسخه‌دار مجاز است')
        return
    if basis(previous)!=basis(updated):
        raise ValueError('ممیزی اجازه تغییر BOQ، قیمت یا اطلاعات پروژه را ندارد')
    ident=command['audit_id'];prior=old.get(ident)
    _identity(ident);_revision(command['expected_revision'], prior['revision'] if prior else 0)
    candidate=new.get(ident)
    if not candidate or candidate['revision']!=(prior['revision']+1 if prior else 1):
        raise ValueError('زنجیره نسخه ممیزی ناسازگار است')
    if {k:v for k,v in old.items() if k!=ident}!={k:v for k,v in new.items() if k!=ident}:
        raise ValueError('تغییر ممیزی دیگر مجاز نیست')
    if updated.get(_HISTORY,[]) != history+([{'audit_id':ident,'record':prior}] if prior else []):
        raise ValueError('حذف یا تغییر تاریخچه ممیزی مجاز نیست')
    if any(_identity(k)==_identity(ident) for k in old if k!=ident):
        raise ValueError('شناسه هم‌ارز ممیزی تکراری است')
    if any(v['data']['source_sha256']==candidate['data']['source_sha256'] for k,v in old.items() if k!=ident):
        raise ValueError('این منبع قبلاً ثبت شده است')
    _validate_record(candidate)
    data=candidate['data'];request=data['request']
    if request.get('project_id')!=previous.get('id') or request.get('project_sha256')!=_hash(basis(previous)):
        raise ValueError('منشأ Snapshot ممیزی ناسازگار است')
    if candidate['result'] is not None:
        import base64
        from core.takeoff.building_six_family_ownership_chat import audit
        documents={k:base64.b64decode(v,validate=True) for k,v in data['evidence_bytes'].items()}
        if candidate['result']!=audit(request,basis(previous),documents=documents):
            raise ValueError('نتیجه ذخیره‌شده با اجرای قرارداد اصلی برابر نیست')


def _write(service,pid,ident,project,token,data,expected_revision,result=None):
    records=project.setdefault(_AUDITS,{})
    prior=records.get(ident)
    _revision(expected_revision,prior['revision'] if prior else 0)
    if prior:project.setdefault(_HISTORY,[]).append({'audit_id':ident,'record':deepcopy(prior)})
    else:project.setdefault(_HISTORY,[])
    record={'revision':expected_revision+1,'status':'draft' if result is None else
            'checked_nonfinancial' if result['document_consistent'] else 'blocked',
            'data':deepcopy(data),'input_digest':_hash(data),'result':deepcopy(result),
            'result_digest':None if result is None else _hash(result)}
    records[ident]=record
    service.store.save(pid,project,expected_digest=token,
        structural_handoff_command={'audit_id':ident,'expected_revision':expected_revision})
    return deepcopy(record)


def save_draft(service,pid,ident,request,*,source_path,source_sha256,evidence_files,expected_revision):
    _identity(ident)
    project,token=read(service,pid)
    data,_=_files(request,source_path,source_sha256,evidence_files)
    if request.get('project_id')!=pid or request.get('project_sha256')!=_hash(basis(project)):
        raise ValueError('سند متعلق به Snapshot فعلی پروژه نیست')
    # Re-read after validation; a changed source never becomes an accepted draft.
    if _files(request,source_path,source_sha256,evidence_files)[0]!=data:
        raise RuntimeError('مدرک هنگام ثبت تغییر کرد')
    return _write(service,pid,ident,project,token,data,expected_revision)


def get_audit(service,pid,ident):
    project,_=read(service,pid)
    record=deepcopy(project.get(_AUDITS,{}).get(ident))
    if record is None:return None
    _validate_record(record)
    record['stale']=record['data']['request']['project_sha256']!=_hash(basis(project))
    return record


def run_audit(service,pid,ident,*,expected_revision):
    from core.takeoff.building_six_family_ownership_chat import audit
    project,token=read(service,pid)
    record=project.get(_AUDITS,{}).get(ident)
    if record is None:raise ValueError('پیش‌نویس ممیزی یافت نشد')
    _validate_record(record);_revision(expected_revision,record['revision'])
    d=record['data'];request=d['request']
    if request['project_sha256']!=_hash(basis(project)):
        raise RuntimeError('Snapshot پروژه کهنه است؛ مدرک و نسخه را بازبینی کنید')
    data,documents=_files(request,d['source_path'],d['source_sha256'],d['evidence_files'])
    if data!=d:raise ValueError('مدارک پیش‌نویس تغییر کرده است')
    result=audit(request,basis(project),documents=documents)
    if result.get('ready') is not False or result.get('commit_allowed') is not False or result.get('payable_rows')!=[]:
        raise ValueError('قفل مالی ممیزی نقض شده است')
    if _files(request,d['source_path'],d['source_sha256'],d['evidence_files'])[0]!=data:
        raise RuntimeError('مدرک هنگام ممیزی تغییر کرد')
    return _write(service,pid,ident,project,token,data,expected_revision,result)


def commit_audit(*args,**kwargs):
    raise ValueError('ثبت مالی مالکیت شش خانواده تا تکمیل شواهد مستقل هندسه و تأیید مالک مسدود است')
