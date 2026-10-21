"""Phase-one read-only column–footing / column–tie-beam face-contact audit.

Source-pinned orthogonal member prisms are reused from the existing column-joint
contract. No overlapping concrete volume, inferred lap, BOQ or SQLite mutation.
A valid contact observation does not certify connection design or payment.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Context, Decimal, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_beam_panel import _member_prism

POLICY = 'column_joint_footing_tie_face_v1'
FOUNDATIONS = frozenset(('isolated_footing', 'strip_footing', 'mat_footing'))
_LINK = ('role', 'kind', 'floor_id', 'member_id', 'physical_id',
         'record_revision', 'record_sha256')
_DOC = ('policy', 'project_id', 'joint_id', 'coordinate_ref', 'vertical_datum_ref',
        'detail_ref', 'prepared_by', 'reviewer', 'links', 'contact_type',
        'contact_axis', 'face_area_m2', 'starter_status', 'starter_reason',
        'starter_bars', 'ownership_status')
_POINT = ('x_m', 'y_m', 'z_m')
_BAR = ('id', 'physical_bar_id', 'owner_role', 'group_key', 'record_piece_id',
        'source_ref', 'detail_ref', 'approved_by', 'axis', 'start', 'end',
        'centerline_length_m')


def _position(point):
    _object(point, _POINT, 'مختصات انتهای میلگرد')
    return tuple(_num(point[key], key) for key in _POINT)


def _inside(point, box):
    return all(box[i] <= point[i] <= box[i + 3] for i in range(3))


def _face(first, other, *, kind, contact_type, axis):
    """Require two face-contacted, not penetrating, axis-aligned solid prisms."""
    expected = 'support_face' if kind in FOUNDATIONS else 'lateral_face'
    if contact_type != expected:
        raise OwnershipError('نوع تماس با خانواده پی یا شناژ سازگار نیست')
    if axis not in (('z',) if kind in FOUNDATIONS else ('x', 'y')):
        raise OwnershipError('محور تماس پی یا شناژ با قرارداد راست‌گوشه سازگار نیست')
    i = {'x': 0, 'y': 1, 'z': 2}[axis]
    # A shared *face* requires equality on the normal axis, and no positive
    # volume overlap. Adjacent edges or corners are NOT a contact surface.
    if first[i] == other[i + 3]:
        plane = first[i]
    elif first[i + 3] == other[i]:
        plane = first[i + 3]
    else:
        raise OwnershipError('دو عضو دارای سطح تماس وجه‌به‌وجه اثبات‌شده نیستند')
    transverse = [j for j in range(3) if j != i]
    dims = []
    for j in transverse:
        overlap = min(first[j + 3], other[j + 3]) - max(first[j], other[j])
        if overlap <= 0:
            raise OwnershipError('تماس خطی یا نقطه‌ای اتصال سطحی محسوب نمی‌شود')
        dims.append(overlap)
    if kind in FOUNDATIONS:
        if first[2] != other[5]:
            raise OwnershipError('انتهای زیرین ستون باید روی تراز فوقانی پی قرار بگیرد')
        # Supporting footprint must contain the full column footprint.
        if any(first[j] < other[j] or first[j + 3] > other[j + 3]
               for j in transverse):
            raise OwnershipError('مقطع ستون باید تماماً داخل سطح پی مستند باشد')
    else:
        # The tie-beam end section, not a partial undefined cut, must fit the
        # column face. A beam running through the column needs a new contract.
        if any(other[j] < first[j] or other[j + 3] > first[j + 3]
               for j in transverse):
            raise OwnershipError('مقطع انتهایی شناژ کامل روی وجه ستون قرار ندارد')
    with localcontext(Context(prec=256, Emin=-999999, Emax=999999)):
        area = dims[0] * dims[1]
    return i, plane, area


def _pieces(record):
    data = record['data']
    groups = data.get('rebars')
    if not isinstance(groups, dict):
        raise OwnershipError('دفتر آرماتور واقعی عضو مالک موجود نیست')
    return groups


def _physical_occurrences(project, physical):
    count = 0
    for registry in ('reviewed_structural_members', 'beam_detail_register'):
        records = project.get(registry, {})
        if not isinstance(records, dict):
            raise OwnershipError('دفتر اعضای سازه‌ای ناقص است')
        for record in records.values():
            if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                raise OwnershipError('رکورد عضو دیگر فاقد ساختار معتبر است')
            for category in ('rebars', 'bars'):
                groups = record['data'].get(category, {})
                if not isinstance(groups, dict):
                    raise OwnershipError('گروه میلگرد عضو دیگر نامعتبر است')
                for group in groups.values():
                    if not isinstance(group, dict):
                        raise OwnershipError('جزئیات میلگرد عضو دیگر نامعتبر است')
                    seg = group.get('segments', [])
                    if not isinstance(seg, list):
                        raise OwnershipError('فهرست میلگرد عضو دیگر نامعتبر است')
                    for part in seg:
                        if not isinstance(part, dict):
                            raise OwnershipError('قطعه میلگرد عضو دیگر نامعتبر است')
                        if part.get('physical_id') is not None and _canonical(part['physical_id']) == physical:
                            count += 1
    return count


def _bar_check(bar, *, roles, axis, plane, project, reviewer, prepared):
    _object(bar, _BAR, 'میلگرد انتظار اتصال')
    for key in ('id', 'physical_bar_id', 'owner_role', 'group_key', 'record_piece_id',
                'source_ref', 'detail_ref', 'approved_by', 'axis'):
        _id(bar[key], key)
    if bar['owner_role'] not in roles or bar['axis'] != 'xyz'[axis]:
        raise OwnershipError('نقش مالک یا محور مسیر میلگرد با تماس سازگار نیست')
    if _canonical(bar['approved_by']) in (reviewer, prepared):
        raise OwnershipError('تأییدکننده دیتایل میلگرد باید مستقل باشد')
    owner = roles[bar['owner_role']][1]
    group = _pieces(owner).get(bar['group_key'])
    if not isinstance(group, dict) or not isinstance(group.get('segments'), list):
        raise OwnershipError('دیتایل گروه میلگرد انتظار در عضو مالک ثبت نشده است')
    matching = [piece for piece in group['segments'] if isinstance(piece, dict)
                and piece.get('id') == bar['record_piece_id']
                and piece.get('physical_id') == bar['physical_bar_id']]
    if len(matching) != 1:
        raise OwnershipError('هویت قطعه میلگرد انتظار در رکورد عضو مالک یکتا نیست')
    part = matching[0]
    if (part.get('source_ref') != bar['source_ref'] or
            _num(part.get('centerline_length_m'), 'طول دیتایل عضو مالک') !=
            _num(bar['centerline_length_m'], 'طول ادعایی مسیر')):
        raise OwnershipError('طول یا منبع میلگرد با عضو مالک برابر نیست')
    physical = _canonical(bar['physical_bar_id'])
    if _physical_occurrences(project, physical) != 1:
        raise OwnershipError('میلگرد انتظار در عضو دیگری تکرار شده یا فاقد مالک فیزیکی است')
    start, end = _position(bar['start']), _position(bar['end'])
    if (not _inside(start, roles['counterpart'][0]) or
            not _inside(end, roles['column'][0])):
        raise OwnershipError('ابتدا و انتهای میلگرد در منشورهای دو عضو واقعی نیستند')
    if any(start[j] != end[j] for j in range(3) if j != axis):
        raise OwnershipError('مسیر مورب یا دارای خم در قرارداد میلگرد مستقیم مجاز نیست')
    # Strictly cross the face; endpoints lying exactly on the face cannot
    # prove any embedment and are not counted as evidence of connection.
    if (start[axis] - plane) * (end[axis] - plane) >= 0:
        raise OwnershipError('میلگرد از سطح مشترک با طول مثبت در دو سوی آن عبور نمی‌کند')
    with localcontext(Context(prec=256, Emin=-999999, Emax=999999)):
        length = abs(end[axis] - start[axis])
    if _num(bar['centerline_length_m'], 'طول مرکز میلگرد') != length:
        raise OwnershipError('طول واقعی میلگرد از مختصات با دیتایل برابر نیست')
    return {'physical_bar_id': bar['physical_bar_id'],
            'owner_role': bar['owner_role'], 'crossing_length_m': format(length, 'f'),
            'unit': 'm'}


def preview(document, project):
    """Compute a bounded contact-face observation; never authorize deductions."""
    _object(document, _DOC, 'مدرک اتصال ستون و پی/شناژ')
    if document['policy'] != POLICY:
        raise OwnershipError('نسخه قرارداد اتصال ستون و پی/شناژ معتبر نیست')
    if not isinstance(project, dict) or project.get('id') != _id(document['project_id'], 'پروژه'):
        raise OwnershipError('شناسه پروژه در Snapshot برابر نیست')
    for field in ('joint_id', 'coordinate_ref', 'vertical_datum_ref', 'detail_ref',
                  'prepared_by', 'reviewer'):
        _id(document[field], field)
    prepared = _canonical(document['prepared_by']); reviewer = _canonical(document['reviewer'])
    if prepared == reviewer or document['ownership_status'] != 'unresolved':
        raise OwnershipError('استقلال بازبین یا وضعیت مالکیت مشترک نامعتبر است')
    if not isinstance(document['links'], list) or len(document['links']) != 2:
        raise OwnershipError('دقیقاً دو عضو سازه‌ای با مدارک مستقل لازم‌اند')
    roles = {}; identity = set()
    for link in document['links']:
        _object(link, _LINK, 'رکورد اتصال ستون و عضو دیگر')
        role = _id(link['role'], 'نقش عضو')
        if role in roles or role not in ('column', 'counterpart'):
            raise OwnershipError('نقش عضو تکراری یا ناشناخته است')
        for key in ('kind', 'floor_id', 'member_id', 'physical_id'):
            _id(link[key], key)
        if (role == 'column' and link['kind'] != 'column') or (role == 'counterpart' and
                link['kind'] not in FOUNDATIONS | {'tie_beam'}):
            raise OwnershipError('نوع عضو مقابل باید پی منفرد/نواری/گسترده یا شناژ باشد')
        ident = _canonical(link['physical_id'])
        if ident in identity:
            raise OwnershipError('هویت فیزیکی دو عضو یکسان است')
        identity.add(ident)
        box, record = _member_prism(project, link, document)
        approver = record['data'].get('source', {}).get('approved_by')
        if approver and _canonical(approver) == reviewer:
            raise OwnershipError('بازبین همان تأییدکننده منبع هندسه است')
        roles[role] = (box, record, link)
    if set(roles) != {'column', 'counterpart'}:
        raise OwnershipError('ستون و عضو مقابل کامل نیستند')
    # Check that no third member aliases either structural physical identity.
    for registry in ('reviewed_structural_members', 'beam_detail_register'):
        members = project.get(registry, {})
        if not isinstance(members, dict):
            raise OwnershipError('دفتر اعضای سازه‌ای ناقص است')
        for record in members.values():
            if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                raise OwnershipError('رکورد عضو دیگری نامعتبر است')
            if record is roles['column'][1] or record is roles['counterpart'][1]:
                continue
            data = record['data']; geometry = data.get('geometry', {})
            if not isinstance(geometry, dict):
                continue
            aliases = [data.get('physical_id'), geometry.get('physical_id'),
                       geometry.get('physical_column_id'), geometry.get('physical_cap_id')]
            if any(x is not None and _canonical(x) in identity for x in aliases):
                raise OwnershipError('هویت فیزیکی ستون یا پی در رکورد دیگر تکرار شده است')
    kind = roles['counterpart'][2]['kind']
    axis, plane, area = _face(roles['column'][0], roles['counterpart'][0],
                              kind=kind, contact_type=document['contact_type'],
                              axis=document['contact_axis'])
    if _num(document['face_area_m2'], 'مساحت سطح تماس') != area:
        raise OwnershipError('مساحت ثبت‌شده با هندسه مستقل سطح تماس برابر نیست')
    bars = document['starter_bars']; status = document['starter_status']
    if not isinstance(bars, list) or len(bars) > 512:
        raise OwnershipError('فهرست میلگرد انتظار نامعتبر است')
    if status == 'not_applicable':
        if kind in FOUNDATIONS or bars:
            raise OwnershipError('برای اتصال ستون به پی، نبود میلگرد انتظار نباید به‌طور خودکار پذیرفته شود')
        _id(document['starter_reason'], 'دلیل مستقل عدم کاربرد میلگرد انتظار')
        observations = []
    elif status == 'documented':
        if not bars or document['starter_reason']:
            raise OwnershipError('میلگردهای انتظار به لیست مستند و بدون دلیل حذف نیاز دارند')
        ids = set(); piece_ids = set(); observations = []
        for bar in bars:
            # Validation takes place before recording any observational row.
            result = _bar_check(bar, roles=roles, axis=axis, plane=plane,
                                project=project, reviewer=reviewer, prepared=prepared)
            pid = _canonical(bar['physical_bar_id']); rid = _canonical(bar['id'])
            if pid in ids or rid in piece_ids or pid in identity:
                raise OwnershipError('قطعه یا هویت فیزیکی میلگرد انتظار تکراری است')
            ids.add(pid); piece_ids.add(rid); observations.append(result)
    else:
        raise OwnershipError('وضعیت میلگرد انتظار ناشناخته است')
    return {'policy': POLICY, 'status': 'COLUMN_FOUNDATION_FACE_PREVIEW_ONLY',
            'counterpart_kind': kind, 'contact_type': document['contact_type'],
            'contact_axis': document['contact_axis'],
            'face_area_m2': format(area, 'f'), 'shared_concrete_volume_m3': '0',
            'observations': deepcopy(observations),
            'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
            'blockers': [
                'تماس سطحی، طراحی اتصال و ظرفیت باربری یا لرزه‌ای را تأیید نمی‌کند',
                'مسیر میلگرد فقط هویت و عبور صریح از وجه را کنترل می‌کند؛ طول مهاری و خم آیین‌نامه‌ای سنجیده نشده است',
                'هیچ حجم بتنی یا وزن میلگرد جدید به پرداخت اضافه نمی‌شود؛ مالکیت مشترک حل‌نشده است',
                'SHA-256 تمامیت مدرک را نشان می‌دهد، نه اصالت نقشه یا تأیید طراح',
            ]}


def preview_file(project, path, sha256):
    """Always hash physical bytes; do not persist the transient result."""
    return preview(read_evidence(path, sha256), project)
