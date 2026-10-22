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
                    evidence_sha256, note, expected_digest):
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
    decision={k:deepcopy(proposal[k]) for k in ('project_id','building_id','floor_id','member_id','global_id','document')}
    user=workspace.users[reviewer]
    decision.update(proposal_id=proposal_id,status='approved',commit_allowed=False,payable_rows=[],
        review={'user_id':reviewer,'display_name':user.display_name,'role':user.role,'note':note.strip(),
                'evidence_path':str(evidence.resolve()),'evidence_sha256':evidence_sha256,
                'author':proposal['author'],'base_project_version':project['_meta']['version']})
    project.setdefault('ifc_identity_reviews',[]).append(decision)
    service.store.save(project_id,project,expected_digest=expected_digest,
                       ifc_command={'action':'review_identity','decision':decision})
    return deepcopy(decision)
