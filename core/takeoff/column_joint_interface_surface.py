"""Read-only rectangular construction-joint / repair *geometry* preflight.

A verified face contact is the only accepted substrate. Neither repair need,
condition of existing concrete, repair chemistry, nor ownership of paid volumes
can be inferred from this calculation. No new material/BOQ rows are produced.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Context, Decimal, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _id, _object, read_evidence, _hash,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_footing_tie import _face, _member_prism, preview as contact_preview

POLICY = 'column_joint_interface_surface_v1'
_HEADER = ('policy', 'project_id', 'joint_id', 'contact_document', 'prepared_by',
           'reviewer', 'joint', 'repair')
_POINTER = ('path', 'sha256', 'reference')
_RECT = ('x_min_m', 'y_min_m', 'z_min_m', 'x_max_m', 'y_max_m', 'z_max_m')
_JOINT = ('status', 'surface', 'declared_area_m2', 'surface_treatment_ref',
          'detail_ref', 'approved_by')
_REPAIR = ('status', 'surface', 'physical_patch_id', 'owner_role', 'thickness_m',
           'declared_volume_m3', 'detail_ref', 'approved_by', 'reason')


def _surface(rect, boxes, normal, plane):
    _object(rect, _RECT, 'سطح فیزیکی مستطیلی')
    axes = tuple(_num(rect[k], k) for k in _RECT)
    if axes[normal] != plane or axes[normal + 3] != plane:
        raise OwnershipError('سطح مستند باید دقیقاً روی وجه مشترک دو عضو باشد')
    dims = []
    for i in range(3):
        if i == normal:
            continue
        if axes[i+3] <= axes[i]:
            raise OwnershipError('ابعاد سطح مستند باید مثبت باشند')
        for box in boxes:
            if axes[i] < box[i] or axes[i+3] > box[i+3]:
                raise OwnershipError('کل سطح مستند باید داخل وجه واقعی هر دو عضو باشد')
        dims.append(axes[i+3]-axes[i])
    with localcontext(Context(prec=256,Emin=-999999,Emax=999999)):
        area=dims[0]*dims[1]
    return axes,area


def preview(document, project):
    _object(document, _HEADER, 'مدرک درز اجرایی و ترمیم موضعی')
    if document['policy'] != POLICY:
        raise OwnershipError('نسخه قرارداد سطح درز و ترمیم ناشناخته است')
    for k in ('project_id', 'joint_id', 'prepared_by', 'reviewer'):
        _id(document[k], k)
    if (not isinstance(project, dict) or project.get('id') != document['project_id'] or
        _canonical(document['prepared_by']) == _canonical(document['reviewer'])):
        raise OwnershipError('هویت پروژه یا استقلال بازبین نامعتبر است')
    pointer=document['contact_document']
    _object(pointer,_POINTER,'منبع اتصال واقعی')
    _id(pointer['reference'],'مرجع هندسی اتصال')
    contact=read_evidence(_id(pointer['path'],'مسیر فایل تماس'),
                          _hash(pointer['sha256'],'هش تماس'))
    if ((contact.get('project_id'),contact.get('joint_id')) !=
          (document['project_id'],document['joint_id'])):
        raise OwnershipError('سند درز/ترمیم به همین اتصال متعلق نیست')
    original=contact_preview(contact,project)
    if (original.get('status')!='COLUMN_FOUNDATION_FACE_PREVIEW_ONLY' or
        original.get('ready_for_boq') or original.get('commit_allowed') or original.get('rows')):
        raise OwnershipError('کنترل سطح اتصال نباید گیت مالی را باز کند')
    roles={}
    for link in contact['links']:
        if link['role'] in roles:raise OwnershipError('نقش عضو در Snapshot تکراری است')
        roles[link['role']]=_member_prism(project,link,contact)[0]
    if set(roles)!={'column','counterpart'}:
        raise OwnershipError('دو عضو واقعی اتصال موجود نیستند')
    kind=next(x['kind'] for x in contact['links'] if x['role']=='counterpart')
    normal,plane,contact_area=_face(roles['column'],roles['counterpart'],
                    kind=kind,contact_type=contact['contact_type'],
                    axis=contact['contact_axis'])
    joint=document['joint'];_object(joint,_JOINT,'درز اجرایی')
    if joint['status']!='documented':
        raise OwnershipError('درز اجرایی بدون مدرک مستقل قابل متره نیست')
    for k in ('detail_ref','approved_by','surface_treatment_ref'):_id(joint[k],k)
    if _canonical(joint['approved_by']) in (
            _canonical(document['prepared_by']),_canonical(document['reviewer'])):
        raise OwnershipError('تأییدکننده درز مستقل از تهیه‌کننده و ممیز نیست')
    _,joint_area=_surface(joint['surface'],tuple(roles.values()),normal,plane)
    if (_num(joint['declared_area_m2'],'مساحت اعلامی درز')!=joint_area or
        joint_area>contact_area):
        raise OwnershipError('مساحت درز از سطح تماس واقعی و مقدار مستند متفاوت است')
    repair=document['repair'];_object(repair,_REPAIR,'ترمیم موضعی')
    observations=[{'operation':'construction_joint_surface',
                   'area_m2':format(joint_area,'f'),'unit':'m2'}]
    if repair['status']=='not_applicable':
        _id(repair['reason'],'علت مستند نبود ترمیم')
        if (repair['surface']!={} or repair['physical_patch_id']!='' or
            repair['owner_role']!='' or repair['thickness_m']!='' or
            repair['declared_volume_m3']!='' or repair['detail_ref']!='' or
            repair['approved_by']!=''):
            raise OwnershipError('ترمیم غیرقابل کاربرد نباید دارای مقدار یا عضو مجعول باشد')
    elif repair['status']=='documented':
        if repair['reason']:
            raise OwnershipError('دلیل عدم کاربرد با ترمیم مستند تناقض دارد')
        for k in ('physical_patch_id','owner_role','detail_ref','approved_by'):
            _id(repair[k],k)
        if repair['owner_role'] not in roles:
            raise OwnershipError('طرف فیزیکی ترمیم باید ستون یا پی/شناژ باشد')
        if _canonical(repair['approved_by']) in (
                _canonical(document['prepared_by']),_canonical(document['reviewer'])):
            raise OwnershipError('تأییدکننده ترمیم مستقل از ممیز نیست')
        pid=_canonical(repair['physical_patch_id'])
        for registry in ('reviewed_structural_members','beam_detail_register'):
            for record in project.get(registry,{}).values():
                data=record.get('data',{})
                geom=data.get('geometry',{})
                if not isinstance(geom,dict):continue
                if any(value is not None and _canonical(value)==pid for value in (
                     data.get('physical_id'),geom.get('physical_id'),
                     geom.get('physical_column_id'),geom.get('physical_cap_id'))):
                    raise OwnershipError('شناسه فیزیکی ترمیم به عضو سازه‌ای دیگری تعلق دارد')
        _,repair_area=_surface(repair['surface'],tuple(roles.values()),normal,plane)
        thickness=_num(repair['thickness_m'],'عمق ترمیم',positive=True)
        target=roles[repair['owner_role']]
        # Rectangular repair volume is at most the documented member's normal
        # thickness. No claim is made that the concrete is actually damaged.
        if thickness>target[normal+3]-target[normal]:
            raise OwnershipError('عمق ترمیم از ضخامت عضو واقعی بیشتر است')
        with localcontext(Context(prec=256,Emin=-999999,Emax=999999)):
            amount=repair_area*thickness
        if _num(repair['declared_volume_m3'],'حجم اعلامی ترمیم') != amount:
            raise OwnershipError('حجم ترمیم مستند با عمق و سطح واقعی برابر نیست')
        observations.append({'operation':'repair_patch_geometric_envelope',
                             'area_m2':format(repair_area,'f'),
                             'depth_m':format(thickness,'f'),
                             'max_envelope_m3':format(amount,'f'),'unit':'m3',
                             'physical_patch_id':repair['physical_patch_id']})
    else:
        raise OwnershipError('وضعیت ترمیم باید صریح و مستند باشد')
    return {'policy':POLICY,'status':'CONSTRUCTION_JOINT_REPAIR_PREVIEW_ONLY',
            'ready_for_boq':False,'commit_allowed':False,'rows':[],
            'observations':deepcopy(observations),
            'blockers':[
                'سطح تماس هندسی، نیاز یا کیفیت اجرای درز اجرایی را اثبات نمی‌کند',
                'حجم ترمیم صرفاً پوش هندسی است و نوع مصالح، برداشت بتن یا پرداخت را تعیین نمی‌کند',
                'تطبیق هش و رکورد، اصالت نقشه یا تأیید مهندس نیست',
            ]}


def preview_file(project,path,sha256):
    return preview(read_evidence(path,sha256),project)
