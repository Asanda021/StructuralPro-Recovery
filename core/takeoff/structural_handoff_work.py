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
