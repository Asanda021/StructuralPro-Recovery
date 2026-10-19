"""Snapshot-bound pre-integration audit; cannot grant financial authority.

The Chat engines and ownership guards remain authoritative and unchanged.
No draft, ledger, rate, amendment or database write is created here.
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

def preview(service,project_id,request,*,source_path,source_sha256):
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
