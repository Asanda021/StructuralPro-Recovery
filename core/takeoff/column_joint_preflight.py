"""Phase-one read-only takeoff preflight for documented concrete column joints.

This is NOT a new structural financial register. It ties an explicitly documented
column and counterpart to their existing versioned SQLite snapshots, audits three
bounded material operations, and never produces payment / BOQ rows. The five
unsupported joint operations remain explicitly unaccepted.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _object, _id, _hash, _canonical, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _digest, _num

POLICY = 'column_joint_material_preflight_v1'
KINDS = ('critical_ties', 'embedded_plates', 'shear_connectors')
PENDING = ('column_to_footing', 'beam_column_connection', 'panel_zone',
           'construction_joint', 'repair_concrete')
ALL = KINDS + PENDING
_LINK = ('role','kind','floor_id','member_id','physical_id','record_revision','record_sha256')
_HEADER = ('policy','project_id','joint_id','coordinate_ref','detail_reference',
           'prepared_by','reviewer','links','operations')
_GROUP = ('status','detail_reference','reviewed_by','reason','pieces')
_COMMON = ('id','physical_id','source_ref','approved_by')
_FIELDS = {
    'critical_ties': ('count','cut_length_m','unit_weight_kg_m','unit_weight_ref'),
    'embedded_plates': ('count','length_m','width_m','thickness_m','density_kg_m3','density_ref'),
    'shear_connectors': ('count','unit_mass_kg','unit_mass_ref'),
}


def _number(value,label,*,integer=False):
    n = _num(value,label,positive=True)
    if integer and n != n.to_integral_value():
        raise OwnershipError(label+': تعداد باید عدد صحیح مستند باشد')
    return n


def _record(project, link):
    if link['role']=='column' and link['kind']!='column':
        raise OwnershipError('نقش ستون با نوع عضو متفاوت است')
    if link['role']=='counterpart' and link['kind'] not in (
        'tie_beam','isolated_footing','strip_footing','mat_footing','pile_cap','beam'):
        raise OwnershipError('نوع عضو مقابلِ اتصال ستون پشتیبانی نمی‌شود')
    registry_name = 'beam_detail_register' if link['kind']=='beam' else 'reviewed_structural_members'
    register = project.get(registry_name,{})
    if not isinstance(register,dict):
        raise OwnershipError('Snapshot دفتر اعضای سازه‌ای نامعتبر است')
    matching=[]
    for record in register.values():
        if not isinstance(record,dict) or not isinstance(record.get('data'),dict):
            raise OwnershipError('Snapshot عضو سازه‌ای نامعتبر است')
        data=record['data']
        identity = (data.get('kind'),data.get('floor_id'),data.get('member_id'))
        if registry_name=='beam_detail_register':
            identity=('beam',data.get('floor_id'),data.get('beam_id'))
        if identity==(link['kind'],link['floor_id'],link['member_id']):
            matching.append(record)
    if len(matching)!=1:
        raise OwnershipError('عضو نسخه‌دار ستون یا عضو مقابل یکتا و موجود نیست')
    record=matching[0]
    if (type(record.get('revision')) is not int or record['revision']<1 or
            record['revision']!=link['record_revision'] or
            record.get('status') not in ('draft','committed')):
        raise OwnershipError('نسخه یا وضعیت رکورد عضو با مدرک اتصال متفاوت است')
    if _hash(link['record_sha256'],'هش Snapshot')!=_digest(record):
        raise OwnershipError('رکورد ستون یا عضو مقابل بعد از تهیه سند تغییر کرده است')
    data=record['data']; geometry=data.get('geometry')
    if not isinstance(geometry,dict):
        raise OwnershipError('هندسه واقعی عضو در Snapshot وجود ندارد')
    variants=[data.get('physical_id'),geometry.get('physical_id')]
    if link['kind']=='column':variants.append(geometry.get('physical_column_id'))
    elif link['kind']=='pile_cap':variants.append(geometry.get('physical_cap_id'))
    stated=[_canonical(x) for x in variants if x is not None]
    if not stated or len(set(stated))!=1 or stated[0]!=_canonical(link['physical_id']):
        raise OwnershipError('هویت فیزیکی عضو در دفتر واقعی احراز نشد')
    return record


def _rebar_claims(data):
    """Compare only physical bar-piece identities; never infer them from mass."""
    found=set()
    for category in ('rebars','bars'):
        groups=data.get(category,{})
        if not isinstance(groups,dict):continue
        for group in groups.values():
            if not isinstance(group,dict):continue
            for piece in group.get('segments',[]):
                if isinstance(piece,dict):
                    for key in ('physical_id','id'):
                        if piece.get(key):found.add(_canonical(piece[key]))
    return found


def preview(document, project):
    """Return an evidence-only result: unsupported or ambiguous claims fail closed.

    This preflight does NOT establish all-body physical reconciliation, signed
    ownership, construction safety or acceptance of remaining joint components.
    """
    _object(document,_HEADER,'قرارداد اتصالات خاص ستون')
    if document['policy']!=POLICY:
        raise OwnershipError('نسخه قرارداد اتصالات خاص ستون نامعتبر است')
    if not isinstance(project,dict) or _id(project.get('id'),'پروژه')!=_id(document['project_id'],'پروژه'):
        raise OwnershipError('پروژه Snapshot با سند اتصال متفاوت است')
    for key in ('joint_id','coordinate_ref','detail_reference','prepared_by','reviewer'):
        _id(document[key],key)
    prepared=_canonical(document['prepared_by']);reviewer=_canonical(document['reviewer'])
    if prepared==reviewer:raise OwnershipError('تهیه‌کننده و بازبین مستقل نیستند')
    links=document['links']
    if not isinstance(links,list) or len(links)!=2:
        raise OwnershipError('یک ستون و دقیقاً یک عضو مقابل باید مستند باشند')
    indexed={};records={};physical=set();existing=set()
    for link in links:
        _object(link,_LINK,'لینک عضو سازه‌ای')
        role=_id(link['role'],'نقش')
        if role in indexed or role not in ('column','counterpart'):
            raise OwnershipError('نقش عضو تکراری یا ناشناخته است')
        for k in ('kind','floor_id','member_id','physical_id'):_id(link[k],k)
        rec=_record(project,link)
        if _canonical(link['physical_id']) in physical:
            raise OwnershipError('دو عضو به یک هویت فیزیکی مشترک اشاره می‌کنند')
        physical.add(_canonical(link['physical_id']))
        existing.update(_rebar_claims(rec['data']))
        # The source approver's name does not substitute for independent review.
        approved=rec['data'].get('source',{}).get('approved_by')
        if approved and _canonical(approved)==reviewer:
            raise OwnershipError('بازبین اتصال همان تأییدکننده منبع عضو است')
        indexed[role]=link;records[role]=rec
    if set(indexed)!=set(('column','counterpart')):
        raise OwnershipError('ستون و عضو مقابل ناقص‌اند')
    # A document is not permission to relabel another registered member.
    for name in ('reviewed_structural_members','beam_detail_register'):
        for record in project.get(name,{}).values():
            if record is records['column'] or record is records['counterpart']:
                continue
            geometry=record.get('data',{}).get('geometry',{})
            if not isinstance(geometry,dict):continue
            claims=[record['data'].get('physical_id'),geometry.get('physical_id'),
                    geometry.get('physical_column_id'),geometry.get('physical_cap_id')]
            if any(v is not None and _canonical(v) in physical for v in claims):
                raise OwnershipError('هویت ستون یا عضو مقابل در رکورد دیگری تکرار شده است')
    # Physical bar pieces may already belong to a *third* column or beam.
    # The two linked members alone are not a complete ownership inventory.
    for register_name in ('reviewed_structural_members','beam_detail_register'):
        others=project.get(register_name,{})
        if not isinstance(others,dict):
            raise OwnershipError('دفتر هویت فیزیکی پروژه نامعتبر است')
        for record in others.values():
            if not isinstance(record,dict) or not isinstance(record.get('data'),dict):
                raise OwnershipError('عضو دیگر دارای ساختار نامعتبر است')
            existing.update(_rebar_claims(record['data']))
    if document['links'][0]['floor_id']!=document['links'][1]['floor_id']:
        raise OwnershipError('اتصال میان طبقات به قرارداد مکانی مستقل نیاز دارد')
    ops=document['operations']
    if not isinstance(ops,dict) or set(ops)!=set(ALL):
        raise OwnershipError('تمام هشت عملیات اتصال باید وضعیت صریح داشته باشند')
    used=set();piece_ids=set();measurements=[]
    with localcontext(Context(prec=256,Emax=999999,Emin=-999999)):
        for op in ALL:
            group=ops[op];_object(group,_GROUP,'وضعیت گروه '+op)
            _id(group['detail_reference'],'مرجع جزئیات');_id(group['reviewed_by'],'بازبین جزء')
            if _canonical(group['reviewed_by'])==prepared:
                raise OwnershipError('تأییدکننده جزء و تهیه‌کننده سند یکسان‌اند')
            status=group['status'];pieces=group['pieces']
            if not isinstance(pieces,list) or len(pieces)>512:
                raise OwnershipError('فهرست قطعات نامعتبر یا نامحدود است')
            if status=='not_applicable':
                _id(group['reason'],'علت عدم کاربرد')
                if pieces:raise OwnershipError('عملیات غیرقابل کاربرد نباید قطعه داشته باشد')
                continue
            if status!='confirmed' or op in PENDING:
                raise OwnershipError('جزء خارج از قرارداد تخصصی یا هنوز بازبینی‌نشده است')
            if group['reason'] or not pieces:
                raise OwnershipError('عملیات تأییدشده باید قطعات مستند داشته باشد')
            for piece in pieces:
                _object(piece,_COMMON+_FIELDS[op], 'قطعه فیزیکی '+op)
                for key in _COMMON:_id(piece[key],key)
                ident=_canonical(piece['physical_id'])
                piece_id=_canonical(piece['id'])
                if piece_id in piece_ids:
                    raise OwnershipError('شناسه قطعه اتصال تکراری است')
                piece_ids.add(piece_id)
                if ident in used or ident in existing or ident in physical:
                    raise OwnershipError('هویت قطعه قبلاً در اتصال یا عضو سازه‌ای مصرف شده است')
                used.add(ident)
                count=_number(piece['count'],'تعداد',integer=True)
                if op=='critical_ties':
                    amount=count*_number(piece['cut_length_m'],'برش')*_number(piece['unit_weight_kg_m'],'وزن واحد')
                    _id(piece['unit_weight_ref'],'مرجع وزن واحد');unit='kg'
                elif op=='embedded_plates':
                    amount=(count*_number(piece['length_m'],'طول')*_number(piece['width_m'],'عرض')*
                            _number(piece['thickness_m'],'ضخامت')*_number(piece['density_kg_m3'],'چگالی'))
                    _id(piece['density_ref'],'مرجع چگالی');unit='kg'
                else:
                    amount=count*_number(piece['unit_mass_kg'],'جرم واحد')
                    _id(piece['unit_mass_ref'],'مرجع جرم');unit='kg'
                measurements.append({'operation':op,'piece_id':piece['id'],
                                     'physical_id':piece['physical_id'],
                                     'quantity':format(amount,'f'),'unit':unit,
                                     'source_ref':piece['source_ref']})
    return {'policy':POLICY,'status':'COLUMN_JOINT_PREVIEW_ONLY',
            'engineering_scope':'limited_documented_materials',
            'ready_for_boq':False,'commit_allowed':False,'rows':[],
            'measurements':deepcopy(measurements),
            'blockers':['پنج عملیات دیگر اتصال در این نسخه فقط با عدم کاربرد صریح پوشش داده می‌شوند',
                        'ممیزی هویت فیزیکی جانشین اثبات اصالت دیتایل، مالکیت پرداخت یا کنترل نقشه نیست']}


def preview_file(project, path, sha256):
    """Read actual bytes with checksum on every call; never persist the report."""
    return preview(read_evidence(path,sha256),project)
