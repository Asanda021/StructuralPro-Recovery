"""Deep IFC/BIM normalization: spatial level, properties, quantities and duplicate safety."""
from __future__ import annotations
from typing import Any, Iterable
import math

QUANTITY_UNITS={"Length":"m","Width":"m","Height":"m","Area":"m2","NetArea":"m2",
                "GrossArea":"m2","Volume":"m3","NetVolume":"m3","GrossVolume":"m3","Count":"عدد"}

def normalize_ifc_rows(rows:Iterable[dict[str,Any]])->list[dict[str,Any]]:
    out=[]; seen=set()
    for r in rows:
        gid=str(r.get("global_id") or "")
        if not gid.strip():
            raise ValueError("شناسه GlobalId عنصر IFC نامشخص است")
        if gid in seen:
            raise ValueError(f"شناسه GlobalId تکراری IFC: {gid}")
        seen.add(gid)
        props=dict(r.get("properties") or {})
        quantities={}
        for k,v in dict(r.get("quantities") or {}).items():
            name=str(k).strip()
            if not name or name not in QUANTITY_UNITS:
                raise ValueError(f"نوع یا واحد کمیت IFC پشتیبانی نمی‌شود: {name or '<empty>'}")
            if isinstance(v, bool):
                raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}")
            try:
                value=float(v)
            except (TypeError,ValueError) as exc:
                raise ValueError(f"مقدار کمیت IFC نامعتبر است: {name}") from exc
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"مقدار کمیت IFC باید متناهی و نامنفی باشد: {name}")
            quantities[name]=value
        level=str(r.get("level") or props.get("Level") or props.get("Storey") or props.get("BuildingStorey") or "")
        out.append({"global_id":gid,"ifc_type":str(r.get("ifc_type") or ""),
                    "name":str(r.get("name") or ""), "level":level,
                    "properties":props,"quantities":quantities,
                    "quantity_units":{k:QUANTITY_UNITS[k] for k in quantities}})
    return out

def aggregate_ifc_quantities(rows:Iterable[dict[str,Any]])->dict[str,Any]:
    rows=normalize_ifc_rows(rows); totals={}; by_type={}; by_level={}
    for r in rows:
        t=r["ifc_type"] or "Unknown"; by_type[t]=by_type.get(t,0)+1
        lv=r["level"] or "بدون طبقه"; by_level[lv]=by_level.get(lv,0)+1
        for k,v in r["quantities"].items(): totals[k]=totals.get(k,0)+v
    return {"objects":len(rows),"by_type":by_type,"by_level":by_level,"quantity_totals":totals}

def map_ifc_to_boq(rows:Iterable[dict[str,Any]],mapping:dict[str,str]):
    result=[]; unmapped=[]
    for r in normalize_ifc_rows(rows):
        code=mapping.get(r["ifc_type"])
        if not code: unmapped.append(r["global_id"] or r["name"]); continue
        for key,value in r["quantities"].items():
            unit=QUANTITY_UNITS.get(key,"")
            result.append({"global_id":r["global_id"],"level":r["level"],"price_code":code,
                           "description":r["name"] or r["ifc_type"],"quantity":value,"unit":unit,
                           "source":f'ifc:{r["global_id"] or r["name"]}:{key}',"needs_confirmation":True})
    return {"rows":result,"unmapped":unmapped}



def identity_guard(previous, updated, command=None):
    """Append-only IFC identity decisions in the canonical project transaction.

    Identity approval is deliberately NOT a quantity/material/payment approval.
    Legacy proposed records remain readable, but cannot be rewritten after review.
    """
    crosswalk_guard(previous,updated,command)
    old = previous.get('ifc_identity_proposals', [])
    new = updated.get('ifc_identity_proposals', [])
    if not isinstance(new, list) or new[:len(old)] != old:
        raise ValueError('تاریخچه پیشنهاد هویت IFC قابل بازنویسی نیست')
    before = previous.get('ifc_identity_reviews', [])
    after = updated.get('ifc_identity_reviews', [])
    if before == after:
        return
    if not isinstance(after, list) or after[:len(before)] != before or len(after) != len(before)+1:
        raise ValueError('تاریخچه بازبینی IFC فقط از مسیر رسمی قابل افزودن است')
    decision = after[-1]
    if not command or command.get('action') != 'review_identity' or command.get('decision') != decision:
        raise ValueError('ثبت بازبینی IFC نیازمند فرمان رسمی است')
    proposal = next((x for x in old if x.get('id') == decision.get('proposal_id')), None)
    if proposal is None or any(x.get('proposal_id') == proposal['id'] for x in before):
        raise ValueError('پیشنهاد IFC نامعتبر یا قبلاً بازبینی شده است')
    for key in ('project_id','building_id','floor_id','member_id','global_id','document'):
        if decision.get(key) != proposal.get(key):
            raise ValueError('تصمیم IFC با پیشنهاد اصلی تطبیق ندارد')
    if decision.get('status') != 'approved' or decision.get('commit_allowed') is not False or decision.get('payable_rows') != []:
        raise ValueError('بازبینی هویت IFC مجوز پرداخت نیست')


def review_identity(service, project_id, *, proposal_id, reviewer, evidence_path,
                    evidence_sha256, note, expected_digest, supersedes=None):
    """Review a proposed mapping using existing collaboration roles and source proof.

    Local role authorization is not professional licensure or a digital signature.
    A different revision/GlobalId requires a separate explicit proposal; split/merge
    cannot be approved by this one-to-one operation.
    """
    from copy import deepcopy
    from hashlib import sha256
    from pathlib import Path
    from core.projects.project_model import _identity
    from core.platform.concurrency import assert_unchanged
    from core.drawings.bim_adapter import BIMAdapter
    if not expected_digest or not isinstance(note,str) or not note.strip():
        raise ValueError('CAS و یادداشت بازبینی IFC الزامی است')
    service.store._cache.pop(str(project_id), None)
    project=deepcopy(service.store.get(project_id))
    if project is None:raise KeyError(project_id)
    assert_unchanged({k:v for k,v in project.items() if k!='_meta'},expected_digest)
    proposal=next((x for x in project.get('ifc_identity_proposals',[]) if x.get('id')==proposal_id),None)
    if proposal is None:raise ValueError('پیشنهاد IFC یافت نشد')
    workspace=service.collaboration
    for uid, permission in ((proposal['author'],'edit'),(reviewer,'review')):
        user=workspace.users.get(uid)
        if user is None or not workspace.roles[user.role].allows(permission):
            raise PermissionError('کاربر ثبت‌شده با نقش مجاز برای بازبینی IFC لازم است')
    if _identity(proposal['author'])==_identity(reviewer):
        raise ValueError('بازبین IFC باید مستقل از ثبت‌کننده باشد')
    if any(x['proposal_id']==proposal_id for x in project.get('ifc_identity_reviews',[])):
        raise ValueError('بازبینی IFC قبلاً ثبت شده است')
    evidence=Path(evidence_path)
    if not evidence.is_file() or not evidence.stat().st_size or sha256(evidence.read_bytes()).hexdigest()!=evidence_sha256:
        raise ValueError('مدرک تطبیق IFC مفقود یا تغییرکرده است')
    source=proposal['document']
    doc=BIMAdapter().read_document(source['source_path'],revision=source['revision'])
    if doc['source_sha256']!=source['source_sha256']:
        raise ValueError('فایل IFC پس از پیشنهاد تغییر کرده است')
    element=next((x for x in doc['elements'] if x['global_id']==proposal['global_id']),None)
    if element is None or element['storey_id']!=proposal['storey_id'] or element['placement_matrix_si']!=proposal['placement_matrix_si']:
        raise ValueError('هویت یا Placement عضو IFC تغییر کرده است')
    floors=project.get('floors',[]);members=project.get('members',[])
    floor=next((x for x in floors if _identity(x['id'])==_identity(proposal['floor_id'])),None)
    member=next((x for x in members if _identity(x['id'])==_identity(proposal['member_id'])),None)
    if floor is None or member is None or _identity(member['floor_id'])!=_identity(floor['id']):
        raise ValueError('FloorID یا MemberID معتبر پروژه لازم است')
    # Different source revisions are not silently treated as new physical owners.
    # A future quantity handoff must resolve revision ownership explicitly.
    for old in project.get('ifc_identity_reviews',[]):
        if old['document']['source_sha256']==source['source_sha256'] and _identity(old['member_id'])==_identity(proposal['member_id']):
            raise ValueError('همین عضو فیزیکی در این IFC قبلاً تطبیق شده است')
    prior=[x for x in project.get('ifc_identity_reviews',[]) if _identity(x['member_id'])==_identity(proposal['member_id']) and _identity(x['floor_id'])==_identity(proposal['floor_id'])]
    if prior:
        if supersedes!=prior[-1]['proposal_id']:
            raise ValueError('Revision هویت IFC نیازمند ارجاع صریح به آخرین تطبیق قبلی است')
    elif supersedes is not None:
        raise ValueError('مبنای Revision هویت IFC یافت نشد')
    decision={k:deepcopy(proposal[k]) for k in ('project_id','building_id','floor_id','member_id','global_id','document')}
    user=workspace.users[reviewer]
    decision.update(proposal_id=proposal_id,supersedes=supersedes,status='approved',commit_allowed=False,payable_rows=[],
        review={'user_id':reviewer,'display_name':user.display_name,'role':user.role,'note':note.strip(),
                'evidence_path':str(evidence.resolve()),'evidence_sha256':evidence_sha256,
                'author':proposal['author'],'base_project_version':project['_meta']['version']})
    project.setdefault('ifc_identity_reviews',[]).append(decision)
    service.store.save(project_id,project,expected_digest=expected_digest,
                       ifc_command={'action':'review_identity','decision':decision})
    return deepcopy(decision)


def _authorized(service, user_id, permission):
    user=service.collaboration.users.get(user_id)
    if user is None or not service.collaboration.roles[user.role].allows(permission):
        raise PermissionError('کاربر ثبت‌شده با نقش مجاز IFC لازم است')
    return user


def _binding(project, proposal_id):
    from pathlib import Path
    from hashlib import sha256
    from core.drawings.bim_adapter import BIMAdapter
    from core.projects.project_model import _identity
    decision=next((x for x in project.get('ifc_identity_reviews',[]) if x['proposal_id']==proposal_id),None)
    if decision is None:raise ValueError('تطبیق هویت IFC تأیید نشده است')
    if any(x.get('supersedes')==proposal_id for x in project.get('ifc_identity_reviews',[])):
        raise ValueError('Revision هویت IFC قدیمی است؛ از تطبیق جاری استفاده کنید')
    proof=decision['review'];path=Path(proof['evidence_path'])
    if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=proof['evidence_sha256']:
        raise ValueError('مدرک تطبیق IFC تغییر کرده یا مفقود است')
    member=next((x for x in project.get('members',[]) if _identity(x['id'])==_identity(decision['member_id'])),None)
    if member is None or _identity(member['floor_id'])!=_identity(decision['floor_id']):
        raise ValueError('عضو یا طبقه پروژه با تطبیق IFC ناسازگار است')
    source=decision['document'];doc=BIMAdapter().read_document(source['source_path'],revision=source['revision'])
    if doc['source_sha256']!=source['source_sha256']:raise ValueError('منبع IFC تغییر کرده است')
    element=next((x for x in doc['elements'] if x['global_id']==decision['global_id']),None)
    if element is None:raise ValueError('عضو IFC حذف شده است')
    return decision,element


def quantity_formula_data(service, project_id, proposal_id, quantity_name, *, author):
    """Explicit QTO → existing manual formula register, without material inference."""
    from hashlib import sha256
    import json
    from core.projects.project_model import _identity
    _authorized(service,author,'edit')
    project=service.open_project(project_id)
    decision,element=_binding(project,proposal_id)
    q=next((x for x in element['quantities'] if x['name']==quantity_name),None)
    if q is None:raise ValueError('کمیت صریح IFC یافت نشد')
    owner=[str(project_id),_identity(decision['floor_id']),_identity(decision['member_id']),q['unit']]
    sid='ifc-owner:'+sha256(json.dumps(owner,ensure_ascii=False).encode()).hexdigest()
    return {'family':'manual_workbench','title':'کمیت عمومی IFC — '+quantity_name,
        'floor':decision['floor_id'],'member':decision['member_id'],'unit':q['unit'],
        'expression':'Q','variables':{'Q':q['value_si']},'variable_units':{'Q':q['unit']},
        'unit_policy':'dimensional_decimal_v1','references':{},'source_id':sid,'deductions':[],
        'basis':'IFC explicit QTO; '+q['basis']+'; '+q['method']+'; not a material calculation',
        'ifc_evidence':{'proposal_id':proposal_id,'quantity_name':quantity_name,
            'qto_step_id':q['step_id'],'source_sha256':decision['document']['source_sha256'],
            'revision':decision['document']['revision'],'author':author}}


def validate_quantity_handoff(service, project, data, *, reviewer=None):
    from core.projects.project_model import _identity
    evidence=data.get('ifc_evidence')
    if evidence is None:return
    if not isinstance(evidence,dict):raise ValueError('مدرک IFC نامعتبر است')
    expected=quantity_formula_data(service,project['id'],evidence.get('proposal_id'),
        evidence.get('quantity_name'),author=evidence.get('author'))
    # Generic QTO is exactly one scalar in its SI unit. Changing operation code,
    # formula, location or data must not turn it into inferred material quantities.
    if data!=expected:raise ValueError('فرمول یا منشأ IFC با QTO تأییدشده مطابقت ندارد')
    if reviewer is not None:
        _authorized(service,reviewer,'review')
        if _identity(reviewer)==_identity(evidence['author']):
            raise ValueError('بازبین مقدار IFC باید مستقل از ثبت‌کننده باشد')


def physical_quantity_guard(project, incoming):
    """Conservative generic IFC ownership check across existing takeoff paths.

    Equal geometry/name is never identity. A reviewed internal member and unit
    identify the generic QTO claim. Other same-unit operations need an explicit
    specialist ownership contract instead of a second generic payment.
    """
    from core.projects.project_model import _identity
    def claim(row):
        params=row.get('params') or {}
        evidence=params.get('cad_evidence') or params.get('geometry_evidence') or params
        floor=evidence.get('floor_id') or params.get('floor') or row.get('system')
        member=evidence.get('member_id') or params.get('member') or row.get('member_code')
        for link in project.get('ifc_2d_crosswalks',[]):
            cad=params.get('cad_evidence') or {}
            same_cad=bool(cad.get('handle')) and cad.get('source_sha256')==link['drawing']['source_sha256'] and cad.get('handle')==link['drawing'].get('handle')
            same_item=row.get('drawing_session_id')==link['session_id'] and row.get('drawing_takeoff_id')==link['item_id']
            if same_cad or same_item:
                floor,member=link['floor_id'],link['member_id'];break
        if not floor or not member:return set()
        return {(_identity(floor),_identity(member),q.get('unit')) for q in row.get('quantities',[])}
    existing=list(project.get('takeoffs',[]))
    for row in incoming:
        is_ifc=bool((row.get('params') or {}).get('ifc_evidence') or (row.get('provenance') or {}).get('ifc_identity'))
        for old in existing:
            old_ifc=bool((old.get('params') or {}).get('ifc_evidence') or (old.get('provenance') or {}).get('ifc_identity'))
            if (is_ifc or old_ifc) and claim(row)&claim(old):
                raise ValueError('مالک کمیت IFC قبلاً از این یا منبع دیگری ثبت شده است؛ تطبیق یا اصلاحیه لازم است')


def crosswalk_guard(previous,updated,command):
    old=previous.get('ifc_2d_crosswalks',[]);new=updated.get('ifc_2d_crosswalks',[])
    if old==new:return
    if not isinstance(new,list) or new[:len(old)]!=old or len(new)!=len(old)+1:
        raise ValueError('تاریخچه Crosswalk IFC قابل بازنویسی نیست')
    if not command or command.get('action')!='crosswalk' or command.get('record')!=new[-1]:
        raise ValueError('Crosswalk IFC فقط از مسیر بازبینی رسمی ثبت می‌شود')


def save_crosswalk(service,project_id,*,proposal_id,session_id,item_id,author,reviewer,
                   evidence_path,evidence_sha256,expected_digest):
    """Reviewed reference-point mapping, not automatic geometric equivalence.

    The explicit SI rigid transform is supplied in a SHA-bound evidence document.
    One reference point is checked against both source records. Independent human
    review is responsible for physical identity and the remaining transform basis.
    It cannot authorize materials, mesh quantities or a second payment.
    """
    import json
    from pathlib import Path
    from hashlib import sha256
    from copy import deepcopy
    from decimal import Decimal,localcontext
    from core.platform.concurrency import assert_unchanged
    from core.projects.project_model import _identity
    from core.drawings.takeoff_session import DrawingTakeoffSession
    _authorized(service,author,'edit');review_user=_authorized(service,reviewer,'review')
    if _identity(author)==_identity(reviewer):raise ValueError('بازبین Crosswalk IFC باید مستقل باشد')
    if not expected_digest:raise ValueError('CAS برای Crosswalk IFC الزامی است')
    service.store._cache.pop(str(project_id),None);project=deepcopy(service.store.get(project_id))
    assert_unchanged({k:v for k,v in project.items() if k!='_meta'},expected_digest)
    binding,element=_binding(project,proposal_id)
    record=service.load_drawing_takeoff_session(project_id,session_id)
    session=DrawingTakeoffSession.from_dict(record['session']);item=session.find(item_id)
    source=Path(session.drawing_source)
    if source.suffix.lower() not in ('.pdf','.dxf','.dwg') or sha256(source.read_bytes()).hexdigest()!=session.source_sha256:
        raise ValueError('منبع دوبعدی Crosswalk IFC نامعتبر یا تغییرکرده است')
    owner=item.cad_evidence or item.geometry_evidence or {}
    if _identity(owner.get('floor_id'))!=_identity(binding['floor_id']) or _identity(owner.get('member_id'))!=_identity(binding['member_id']):
        raise ValueError('عضو و طبقه دوبعدی با تطبیق IFC یکسان نیست')
    if not item.geometry:raise ValueError('نقطه مرجع دوبعدی معتبر لازم است')
    cal=session.calibrations.get(item.page)
    if cal is None:raise ValueError('مقیاس معتبر منبع دوبعدی لازم است')
    from core.drawings.takeoff_bridge import session_to_boq_rows,verified_measurement_identities
    rows=session_to_boq_rows(record['session'],session_id=session_id,selected_item_ids=[item_id])
    verified_measurement_identities(record,rows)
    proof=Path(evidence_path)
    if not proof.is_file() or sha256(proof.read_bytes()).hexdigest()!=evidence_sha256:
        raise ValueError('مدرک Crosswalk IFC تغییر کرده یا مفقود است')
    evidence=json.loads(proof.read_text(encoding='utf-8-sig'))
    expected={'policy':'reviewed_reference_point_v1','project_id':project_id,'proposal_id':proposal_id,
        'session_id':session_id,'item_id':item_id,'ifc_sha256':binding['document']['source_sha256'],
        'drawing_sha256':session.source_sha256}
    if any(evidence.get(k)!=v for k,v in expected.items()):raise ValueError('مدرک Crosswalk با منابع IFC و دوبعدی تطبیق ندارد')
    for key in ('physical_identity_reference','unit_evidence_reference'):
        if not isinstance(evidence.get(key),str) or not evidence[key].strip():raise ValueError('مدرک هویت و واحد Crosswalk IFC الزامی است')
    with localcontext() as context:
        context.prec=80
        def values(key,n):
            raw=evidence.get(key)
            if not isinstance(raw,list) or len(raw)!=n or any(not isinstance(x,str) for x in raw):raise ValueError('مختصات مدرک Crosswalk IFC نامعتبر است')
            out=[Decimal(x) for x in raw]
            if any(not x.is_finite() or len(x.as_tuple().digits)>32 or (x and abs(x)>Decimal('1e12')) for x in out):raise ValueError('دامنه مختصات Crosswalk IFC نامعتبر است')
            return out
        origin=values('ifc_origin_m',3);anchor=values('drawing_anchor_xy',2)
        if origin!=[Decimal(x) for x in element['origin_m']]:raise ValueError('مبدأ IFC در مدرک Crosswalk نادرست است')
        a,b,c,d,tx,ty=values('ifc_to_drawing_si',6)
        if a*a+c*c!=1 or b*b+d*d!=1 or a*b+c*d!=0 or abs(a*d-b*c)!=1:
            raise ValueError('تبدیل Crosswalk IFC باید صلب و با واحد SI معتبر باشد')
        scale=Decimal(str(cal.meters_per_pixel))
        actual=[Decimal(str(x))*scale for x in item.geometry[0]]
        if item.cad_evidence:
            origin_xy=item.cad_evidence.get('scene_origin',[0,0])
            actual=[v+Decimal(str(origin_xy[i])) for i,v in enumerate(actual)]
        if anchor!=actual or [a*origin[0]+b*origin[1]+tx,c*origin[0]+d*origin[1]+ty]!=anchor:
            raise ValueError('نقطه مرجع IFC و منبع دوبعدی با تبدیل مستند تطبیق ندارد')
    if any(x['session_id']==session_id and x['item_id']==item_id for x in project.get('ifc_2d_crosswalks',[])):
        raise ValueError('همین جزء دوبعدی قبلاً Crosswalk IFC دارد')
    result={'id':sha256((proposal_id+session_id+item_id+evidence_sha256).encode()).hexdigest(),
        'project_id':project_id,'proposal_id':proposal_id,'global_id':binding['global_id'],
        'floor_id':binding['floor_id'],'member_id':binding['member_id'],
        'ifc_document':deepcopy(binding['document']),'session_id':session_id,'item_id':item_id,
        'drawing':{'path':str(source.resolve()),'source_sha256':session.source_sha256,'page':item.page,
            'handle':(item.cad_evidence or {}).get('handle'),'session_revision':record['revision'],
            'item_digest':sha256(json.dumps(item.to_dict(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()},
        'evidence_path':str(proof.resolve()),'evidence_sha256':evidence_sha256,'coordinate_evidence':evidence,
        'author':author,'reviewer':reviewer,'reviewer_role':review_user.role,'status':'approved',
        'commit_allowed':False,'payable_rows':[]}
    project.setdefault('ifc_2d_crosswalks',[]).append(result)
    service.store.save(project_id,project,expected_digest=expected_digest,ifc_command={'action':'crosswalk','record':result})
    return deepcopy(result)


def validate_specialist_detail(service,project,data):
    """Attach explicit external column detail to the existing specialist engine.

    Geometry comparison is diagnostic; all payable concrete/form/rebar inputs
    remain the independently reviewed, SHA-bound detail, never mesh inference.
    """
    from pathlib import Path
    from hashlib import sha256
    import json
    from decimal import Decimal
    from core.projects.project_model import _identity
    meta=(data.get('source') or {}).get('ifc_identity')
    if meta is None:return
    if service is None:raise ValueError('مسیر تخصصی IFC به سرویس بازبینی واقعی نیاز دارد')
    _authorized(service,meta.get('author'),'edit');_authorized(service,meta.get('reviewer'),'review')
    if _identity(meta['author'])==_identity(meta['reviewer']):raise ValueError('بازبین دیتایل IFC باید مستقل باشد')
    binding,element=_binding(project,meta['proposal_id'])
    if data.get('kind')!='column' or element['ifc_type']!='IfcColumn' or data.get('measurement_policy')!='column_specialist_v1':
        raise ValueError('این اتصال تخصصی IFC فقط قرارداد ستون موجود را می‌پذیرد')
    if _identity(data.get('floor_id'))!=_identity(binding['floor_id']) or _identity(data.get('member_id'))!=_identity(binding['member_id']):
        raise ValueError('دیتایل تخصصی با عضو و طبقه IFC یکسان نیست')
    path=Path(meta['detail_path'])
    if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=meta['detail_sha256']:
        raise ValueError('مدرک دیتایل تخصصی IFC تغییر کرده یا مفقود است')
    expected=json.loads(path.read_text(encoding='utf-8-sig'))
    if expected!={k:v for k,v in data.items() if k!='source'}:
        raise ValueError('ورودی تخصصی با مدرک IFC تأییدشده یکسان نیست')
    if Decimal(str(data.get('geometry',{}).get('count',0)))!=1:
        raise ValueError('هر تطبیق IFC تخصصی فقط یک عضو فیزیکی مستقل است')
    from core.drawings.bim_quantities import compare_volume_qto
    comparison=compare_volume_qto(binding['document']['source_path'],revision=binding['document']['revision'],global_id=binding['global_id'])
    if not comparison['within_tolerance']:raise ValueError('QTO و هندسه IFC برای دیتایل تخصصی سازگار نیستند')
    from core.takeoff.reviewed_structural import preview_member
    report=preview_member(data,service.takeoff)
    if not report['ready']:raise ValueError('دیتایل تخصصی IFC ناقص است: '+'؛ '.join(report['blockers']))
    concrete=[r for r in report['rows'] if r['unit']=='m3']
    if len(concrete)!=1:raise ValueError('حجم مستند ستون IFC احراز نشد')
    quantity=Decimal(str(concrete[0]['quantity']));observed=Decimal(comparison['net_volume_m3'])
    if abs(quantity-observed)>Decimal('0.00000001')+abs(quantity)*Decimal('0.00000001'):
        raise ValueError('حجم دیتایل مستقل با هندسه IFC سازگار نیست')


def save_column_detail(service,project_id,*,proposal_id,detail_path,detail_sha256,author,reviewer,expected_revision=0):
    from pathlib import Path
    from hashlib import sha256
    import json
    path=Path(detail_path)
    if sha256(path.read_bytes()).hexdigest()!=detail_sha256:raise ValueError('دیتایل IFC تغییر کرده است')
    data=json.loads(path.read_text(encoding='utf-8-sig'))
    if 'source' in data:raise ValueError('مدرک دیتایل باید مستقل از منشأ اتصال IFC باشد')
    binding,_=_binding(service.open_project(project_id),proposal_id)
    data['source']={'mode':'manual','source_id':'ifc-column:'+str(project_id)+':'+binding['floor_id']+':'+binding['member_id'],
        'plan_ref':binding['document']['source_sha256'],'detail_ref':detail_sha256,
        'ifc_identity':{'proposal_id':proposal_id,'author':author,'reviewer':reviewer,
            'detail_path':str(path.resolve()),'detail_sha256':detail_sha256}}
    validate_specialist_detail(service,service.open_project(project_id),data)
    return service.save_structural_member_draft(project_id,data,expected_revision=expected_revision,reason='دیتایل مستقل و مستند IFC؛ موتور تخصصی ستون موجود')
