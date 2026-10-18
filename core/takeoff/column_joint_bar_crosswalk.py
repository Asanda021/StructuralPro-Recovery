"""Phase-one read-only crosswalk of *individual* beam/column joint bars.

Bar centre-lines are explicit orthogonal polylines, source-bound to existing
versioned member records and the separately verified beam/column panel geometry.
This is NOT a rebar design, lap/development-length check or payment workflow.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_beam_panel import (
    _member_prism, _box, _intersection, preview as geometry_preview,
)

POLICY = 'column_joint_bar_route_crosswalk_v1'
_DOC = ('policy','project_id','joint_id','geometry_document',
        'prepared_by','reviewer','bar_routes')
_POINTER = ('path','sha256','reference')
_ROUTE = ('id','physical_bar_id','owner_role','group_key','record_piece_id',
          'source_ref','detail_ref','approved_by','centerline_length_m',
          'length_in_panel_m','points')
_POINT = ('x_m','y_m','z_m')
_AXES = ('x','y','z')


def _centerline(route, prism, panel):
    points = route['points']
    if not isinstance(points, list) or not 2 <= len(points) <= 64:
        raise OwnershipError('مسیر میلگرد به ۲ تا ۶۴ نقطه واقعی نیاز دارد')
    vertices=[]
    for item in points:
        _object(item, _POINT, 'مختصات مرکز میلگرد')
        v=tuple(_num(item[key], key) for key in _POINT)
        if any(v[i] < prism[i] or v[i] > prism[i+3] for i in range(3)):
            raise OwnershipError('مسیر میلگرد خارج از منشور مستند عضو مالک است')
        vertices.append(v)
    segments=[]
    total=Decimal(0); inside=Decimal(0)
    with localcontext(Context(prec=256,Emax=999999,Emin=-999999)):
        for a,b in zip(vertices, vertices[1:]):
            changed=[i for i in range(3) if a[i]!=b[i]]
            if len(changed)!=1:
                raise OwnershipError('بخش مورب یا بی‌طولِ مسیر میلگرد در قرارداد راست‌گوشه مجاز نیست')
            axis=changed[0]
            lo,hi=sorted((a[axis],b[axis]))
            for x,y,j in segments:
                if j==axis and all(a[k]==x[k] for k in range(3) if k!=axis):
                    q0,q1=sorted((x[axis],y[axis]))
                    if min(hi,q1)>max(lo,q0):
                        raise OwnershipError('مسیر میلگرد روی طول مشترک دوباره پیمایش شده است')
            segments.append((a,b,axis))
            total+=hi-lo
            if all(panel[k]<=a[k]<=panel[k+3] for k in range(3) if k!=axis):
                inside+=max(Decimal(0), min(hi,panel[axis+3])-max(lo,panel[axis]))
    if inside<=0:
        raise OwnershipError('مرکز میلگرد هیچ طول مثبتی در چشمه مستند ندارد')
    if _num(route['centerline_length_m'],'طول مرکز میلگرد')!=total:
        raise OwnershipError('طول مستند مرکز میلگرد با نقاط مسیر برابر نیست')
    if _num(route['length_in_panel_m'],'طول عبور از چشمه')!=inside:
        raise OwnershipError('طول مستند عبور میلگرد از چشمه با هندسه برابر نیست')
    return format(total,'f'), format(inside,'f')


def _owner_piece(data, route):
    category = 'rebars' if route['owner_role']=='column' else 'bars'
    groups=data.get(category)
    if not isinstance(groups,dict):
        raise OwnershipError('دفتر اجزای آرماتور عضو مالک معتبر نیست')
    group=groups.get(route['group_key'])
    if not isinstance(group,dict) or not isinstance(group.get('segments'),list):
        raise OwnershipError('گروه میلگرد دارای ردیف‌های فیزیکی مستند نیست')
    matches=[part for part in group['segments'] if isinstance(part,dict) and
             part.get('id')==route['record_piece_id'] and
             part.get('physical_id')==route['physical_bar_id']]
    if len(matches)!=1:
        raise OwnershipError('میلگرد فیزیکی در دیتایل واقعی عضو مالک یکتا نیست')
    piece=matches[0]
    if (_id(piece.get('source_ref'),'منشأ قطعه میلگرد')!=route['source_ref'] or
            _num(piece.get('centerline_length_m'),'طول دیتایل اصلی')!=
            _num(route['centerline_length_m'],'طول مسیر')):
        raise OwnershipError('طول یا منبع میلگرد در رکورد مالک با مدرک مسیر برابر نیست')
    return piece


def _claim_count(project, physical_bar_id):
    count=0
    for book in ('reviewed_structural_members','beam_detail_register'):
        register=project.get(book,{})
        if not isinstance(register,dict):
            raise OwnershipError('دفتر اعضای سازه‌ای ناقص است')
        for record in register.values():
            if not isinstance(record,dict) or not isinstance(record.get('data'),dict):
                raise OwnershipError('رکورد عضو سازه‌ای نامعتبر است')
            data=record['data']
            for category in ('bars','rebars'):
                groups=data.get(category,{})
                if not isinstance(groups,dict):
                    raise OwnershipError('گروه آرماتور فاقد ساختار معتبر است')
                for group in groups.values():
                    if not isinstance(group,dict):
                        raise OwnershipError('گروه آرماتور رکورد ناسازگار است')
                    rows=group.get('segments',[])
                    if not isinstance(rows,list):
                        raise OwnershipError('قطعات میلگرد رکورد ناسازگار است')
                    for piece in rows:
                        if not isinstance(piece,dict):
                            raise OwnershipError('قطعه میلگرد رکورد ناسازگار است')
                        if piece.get('physical_id') is not None and _canonical(piece['physical_id'])==physical_bar_id:
                            count+=1
    return count


def preview(document, project):
    """Reconcile only explicit pieces; DO NOT assert all joint bars were included."""
    _object(document,_DOC,'سند مسیر میلگردهای اتصال')
    if document['policy']!=POLICY:
        raise OwnershipError('نسخه قرارداد مسیر میلگرد ناشناخته است')
    if not isinstance(project,dict) or document['project_id'] != _id(project.get('id'),'شناسه پروژه'):
        raise OwnershipError('هویت پروژه و سند میلگرد مغایر است')
    for field in ('project_id','joint_id','prepared_by','reviewer'):
        _id(document[field],field)
    if _canonical(document['reviewer'])==_canonical(document['prepared_by']):
        raise OwnershipError('بازبین مستقل سند مسیر میلگرد لازم است')
    pointer=document['geometry_document']
    _object(pointer,_POINTER,'مدرک مستقل هندسی اتصال')
    _id(pointer['path'],'مسیر مدرک هندسه')
    _id(pointer['reference'],'مرجع مدرک هندسه')
    geometry=read_evidence(pointer['path'],_hash(pointer['sha256'],'هش هندسه اتصال'))
    if geometry['project_id']!=document['project_id'] or geometry['joint_id']!=document['joint_id']:
        raise OwnershipError('مدرک مسیر میلگرد به همین اتصال مربوط نیست')
    geometry_result=geometry_preview(geometry,project)
    if (geometry_result.get('ready_for_boq') or geometry_result.get('commit_allowed') or
            geometry_result.get('rows') or geometry_result.get('status')!='BEAM_COLUMN_PANEL_PREVIEW_ONLY'):
        raise OwnershipError('گیت ممیزی هندسی اتصال ناخواسته باز شده است')
    roles={}
    for link in geometry['links']:
        role=link['role']
        if role in roles:raise OwnershipError('نقش عضو تکراری در هندسه')
        box,record=_member_prism(project,link,geometry)
        roles[role]=(box,record,link)
    if set(roles)!={'column','counterpart'}:
        raise OwnershipError('هر دو عضو نسخه‌دار برای مالکیت میلگرد لازم‌اند')
    joint=_intersection(roles['column'][0],roles['counterpart'][0])
    panel=_box(geometry['panel_zone'],'محدوده چشمه')
    if any(panel[i]<joint[i] or panel[i+3]>joint[i+3] for i in range(3)):
        raise OwnershipError('چشمه خارج از تقاطع واقعی اعضا قرار دارد')
    routes=document['bar_routes']
    if not isinstance(routes,list) or not 1<=len(routes)<=128:
        raise OwnershipError('فهرست مستند و محدود میلگردهای اتصال لازم است')
    observations=[];bar_ids=set();row_ids=set()
    for route in routes:
        _object(route,_ROUTE,'مدرک مسیر میلگرد فیزیکی')
        for field in ('id','physical_bar_id','owner_role','group_key','record_piece_id',
                      'source_ref','detail_ref','approved_by'):
            _id(route[field],field)
        role=route['owner_role']
        if role not in roles:
            raise OwnershipError('نقش مالک میلگرد باید ستون یا تیرِ واقعی باشد')
        physical=_canonical(route['physical_bar_id']);rid=_canonical(route['id'])
        if physical in bar_ids or rid in row_ids:
            raise OwnershipError('شناسه یا قطعه فیزیکی مسیر میلگرد تکراری است')
        if _canonical(route['approved_by']) in (_canonical(document['reviewer']),_canonical(document['prepared_by'])):
            raise OwnershipError('تأییدکننده مسیر میلگرد مستقل نیست')
        bar_ids.add(physical);row_ids.add(rid)
        box,record,_=roles[role]
        _owner_piece(record['data'],route)
        # A physical piece is not allowed to appear twice anywhere in the two
        # registers. Unknown legacy identities are not inferred from mass.
        if _claim_count(project,physical)!=1:
            raise OwnershipError('هویت فیزیکی میلگرد در دفتر اعضا تکراری یا مفقود است')
        total,in_panel=_centerline(route,box,panel)
        observations.append({'id':route['id'],'physical_bar_id':route['physical_bar_id'],
                             'owner_role':role,'centerline_length_m':total,
                             'length_in_panel_m':in_panel,'unit':'m'})
    return {'policy':POLICY,'status':'BAR_ROUTE_PREVIEW_ONLY',
            'geometry_record_bound':True, 'ownership_scope':'explicit_pieces_only',
            'ready_for_boq':False,'commit_allowed':False,'rows':[],
            'observations':deepcopy(observations),
            'blockers':['مالکیت بررسی‌شده فقط برای قطعات صریح است؛ کامل‌بودن میلگردهای اتصال احراز نشده',
                        'طول مهاری، قطر، خم، خاموت ناحیه بحرانی و کفایت لرزه‌ای از این مسیر نتیجه نمی‌شود',
                        'هش و Snapshot جایگزین اصالت نقشه یا تأیید مهندس مستقل نیست']}


def preview_file(project,path,sha256):
    """Use independently checked JSON bytes; result cannot be persisted or paid."""
    return preview(read_evidence(path,sha256),project)
