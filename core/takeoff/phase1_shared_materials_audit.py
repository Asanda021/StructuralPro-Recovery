"""P1 #2: immutable cross-family material-alias preflight (not a payment ledger).

Identical material physical IDs may appear under multiple member/quantity families.
Read-only lookup covers beam, reviewed structural and reviewed AEC registers.
Without source geometry, complete historical register and validated allocation,
that collision is a blocker; no payable deductions or 'all clear' are produced.
"""
from __future__ import annotations
from copy import deepcopy
from core.takeoff.bored_pile_ownership_preflight import OwnershipError, _id, _object, _canonical
from core.takeoff.bored_pile_joint_crosswalk import _digest

POLICY='phase1_shared_material_claims_v1'
CLASSES=('concrete','formwork','rebar')
_DOC=('policy','project_id','prepared_by','reviewer','claims')
_CLAIM=('material_kind','physical_material_id','member_kind','floor_id','member_id',
        'source_ref','detail_ref','member_record_sha256','member_revision')
_REGISTERS=('reviewed_structural_members','beam_detail_register','reviewed_aec_systems')


def audit(project,document):
    _object(document,_DOC,'ممیزی مشترک بتن قالب و میلگرد')
    if document['policy']!=POLICY or not isinstance(project,dict) or project.get('id')!=document['project_id']:
        raise OwnershipError('پروژه یا قرارداد ادعاهای مصالح مغایر است')
    for field in ('project_id','prepared_by','reviewer'):_id(document[field],field)
    if _canonical(document['prepared_by'])==_canonical(document['reviewer']):
        raise OwnershipError('بازبین مستقل است')
    claims=document['claims']
    if not isinstance(claims,list) or not 1<=len(claims)<=512:
        raise OwnershipError('ادعاهای محدود و صریح مصالح لازم است')
    seen=set();member_claims={};identities=set()
    for claim in claims:
        _object(claim,_CLAIM,'ادعای منبع مصالح')
        for field in ('material_kind','physical_material_id','member_kind','floor_id',
                      'member_id','source_ref','detail_ref'):
            _id(claim[field],field)
        if claim['material_kind'] not in CLASSES:
            raise OwnershipError('جنس مصالح خارج از بتن، قالب یا میلگرد است')
        identity=_canonical(claim['physical_material_id'])
        if identity in seen:
            raise OwnershipError('هویت فیزیکی مصالح در دو عضو یا ردیف دوباره ادعا شده است')
        seen.add(identity)
        key=(claim['member_kind'],claim['floor_id'],claim['member_id'])
        identity_key=(claim['material_kind'],identity)
        if identity_key in identities:
            raise OwnershipError('هویت واقعی یک مصالح دوباره تخصیص یافته است')
        identities.add(identity_key)
        matches=[]
        for book in _REGISTERS:
            register=project.get(book,{})
            if not isinstance(register,dict):raise OwnershipError('دفتر اعضا نامعتبر است')
            for record in register.values():
                if not isinstance(record,dict) or not isinstance(record.get('data'),dict):
                    raise OwnershipError('رکورد عضو موجود ساختار معتبر ندارد')
                data=record['data']
                # Roofs, facades and other AEC systems use system_id, not
                # structural member_id. A claim must bind to exactly one saved
                # record, even when two registries contain similar labels.
                actual=('beam' if book=='beam_detail_register' else data.get('kind'),
                        data.get('floor_id'),
                        data.get('beam_id') if book=='beam_detail_register'
                        else data.get('system_id') if book=='reviewed_aec_systems'
                        else data.get('member_id'))
                if actual==key:matches.append(record)
        if len(matches)!=1:raise OwnershipError('عضو مالک منحصربه‌فرد در Snapshot پیدا نشد')
        record=matches[0]
        if (type(claim['member_revision']) is not int or
                claim['member_revision']!=record.get('revision') or
                claim['member_record_sha256']!=_digest(record)):
            raise OwnershipError('نسخه یا SHA-256 عضو مالک با مدرک مصالح مغایر است')
        member_claims[identity]={'material_kind':claim['material_kind'],
                                 'member_kind':claim['member_kind'],'member_id':claim['member_id']}
    blockers=['مالکیت و کسورات مالی سه مصالح هنوز در تمام دفترها و نقشه واقعی تأیید نشده است']
    # Historical BOQ and takeoff entries can contain aggregates without a
    # comparable physical ID. Even a distinct current claim is no clearance.
    for book in ('boq','takeoffs'):
        rows=project.get(book,[])
        if not isinstance(rows,list):raise OwnershipError('دفتر مالی معتبر نیست')
        if rows:
            blockers.append('دفتر '+book+' دارای '+str(len(rows))+' ردیف تاریخی/فعال است؛ تطبیق مالی مستقل لازم است')
        for row in rows:
            if not isinstance(row,dict):raise OwnershipError('ردیف مالی دارای ساختار نامعتبر است')
            params=row.get('params') or {}
            if not isinstance(params,dict):raise OwnershipError('شناسه فیزیکی ردیف مالی نامعتبر است')
            ids=[params.get(k) for k in ('physical_material_id','component_physical_id','physical_bar_id')]
            ids+=[row.get('physical_material_id'),row.get('physical_bar_id')]
            if any(isinstance(v,str) and _canonical(v) in seen for v in ids):
                blockers.append('شناسه مصالح در '+book+' نیز وجود دارد؛ خطر دوباره‌شماری قطعی بررسی شود')
    return {'policy':POLICY,'status':'SHARED_MATERIALS_PREVIEW_ONLY',
            'verified_registered_claim_count':len(claims),
            'material_classes':list(CLASSES),'claims':deepcopy(member_claims),
            'ready_for_boq':False,'commit_allowed':False,'rows':[],
            'blockers':blockers}
