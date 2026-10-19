"""Read-only geometric crosswalk for an explicitly sourced beam/column joint.

Every orthogonal member prism is independently byte-hash-bound to its current
versioned record. These measurements are geometry observations, NOT extra
concrete, reinforcement takeoff, design verification or BOQ authorization.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Context, Decimal, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num, _digest
from core.takeoff.column_joint_preflight import _record, _rebar_claims

POLICY = 'column_joint_beam_panel_geometry_v1'
PRISM_POLICY = 'column_joint_member_prism_v1'
POINTER_KEY = 'column_joint_prism_v1'
_AXES = ('x_min_m', 'y_min_m', 'z_min_m', 'x_max_m', 'y_max_m', 'z_max_m')
_LINK = ('role', 'kind', 'floor_id', 'member_id', 'physical_id',
         'record_revision', 'record_sha256')
_POINTER = ('policy', 'path', 'sha256', 'reference',
            'coordinate_ref', 'vertical_datum_ref', 'physical_id')
_PRISM = ('policy', 'project_id', 'role', 'kind', 'floor_id', 'member_id',
          'physical_id', 'coordinate_ref', 'vertical_datum_ref',
          'geometry_source_ref', 'geometry_source_sha256',
          'prepared_by', 'reviewer') + _AXES
_ZONE = ('id', 'physical_id', 'detail_ref', 'approved_by') + _AXES
_DOC = ('policy', 'project_id', 'joint_id', 'coordinate_ref', 'vertical_datum_ref',
        'detail_ref', 'prepared_by', 'reviewer', 'links', 'panel_zone',
        'connection_volume_m3', 'panel_volume_m3', 'reinforcement_status',
        'ownership_status', 'ownership_reason')


def _box(data, label):
    coords = tuple(_num(data[k], label + ': ' + k) for k in _AXES)
    if any(coords[i + 3] <= coords[i] for i in range(3)):
        raise OwnershipError(label + ': منشور باید ابعاد مثبت و راست‌گوشه داشته باشد')
    return coords


def _volume(box):
    with localcontext(Context(prec=1024, Emax=999999, Emin=-999999)):
        return (box[3] - box[0]) * (box[4] - box[1]) * (box[5] - box[2])


def _intersection(first, second):
    low = tuple(max(first[i], second[i]) for i in range(3))
    high = tuple(min(first[i + 3], second[i + 3]) for i in range(3))
    if any(high[i] <= low[i] for i in range(3)):
        raise OwnershipError('تیر و ستون حجم مشترک سه‌بعدی مثبت ندارند؛ اتصال اثبات نشده است')
    return low + high


def _physical(data, kind):
    geometry = data.get('geometry')
    if not isinstance(geometry, dict):
        raise OwnershipError('هندسه عضو موجود نیست')
    names = [data.get('physical_id'), geometry.get('physical_id')]
    if kind == 'column':
        names.append(geometry.get('physical_column_id'))
    names = [_canonical(x) for x in names if x is not None]
    if not names or len(set(names)) != 1:
        raise OwnershipError('هویت فیزیکی عضو با Snapshot سازگار نیست')
    return names[0]


def _member_prism(project, link, document):
    record = _record(project, link)
    data = record['data']
    geometry = data['geometry']
    pointer = geometry.get(POINTER_KEY)
    _object(pointer, _POINTER, 'نشانی مدرک مستقل منشور عضو')
    if pointer['policy'] != PRISM_POLICY:
        raise OwnershipError('نسخه نشانی مدرک منشور نامعتبر است')
    for field in ('reference', 'coordinate_ref', 'vertical_datum_ref'):
        _id(pointer[field], field)
    if (_canonical(pointer['physical_id']) != _canonical(link['physical_id']) or
            _physical(data, link['kind']) != _canonical(link['physical_id'])):
        raise OwnershipError('مدرک منشور به هویت فیزیکی فعلی عضو متصل نیست')
    for key in ('coordinate_ref', 'vertical_datum_ref'):
        if pointer[key] != document[key]:
            raise OwnershipError('مختصات یا تراز عضو با مبنای مشترک تطابق ندارد')
    source = read_evidence(_id(pointer['path'], 'مسیر واقعی مدرک منشور'),
                           _hash(pointer['sha256'], 'SHA-256 مدرک منشور'))
    _object(source, _PRISM, 'مدرک منشور عضو')
    if source['policy'] != PRISM_POLICY:
        raise OwnershipError('نسخه مدرک مستقل عضو ناشناخته است')
    for field, expected in (
        ('project_id', document['project_id']), ('role', link['role']),
        ('kind', link['kind']), ('floor_id', link['floor_id']),
        ('member_id', link['member_id']), ('coordinate_ref', document['coordinate_ref']),
        ('vertical_datum_ref', document['vertical_datum_ref']),
    ):
        if _id(source[field], field) != expected:
            raise OwnershipError('هویت، مختصات یا تراز مدرک منشور با اتصال مغایر است')
    if (_canonical(source['physical_id']) != _canonical(link['physical_id']) or
            _canonical(source['physical_id']) != _canonical(pointer['physical_id'])):
        raise OwnershipError('شناسه فیزیکی مدرک منشور یکسان نیست')
    for field, record_field in (('geometry_source_ref', 'source_ref'),
                                ('geometry_source_sha256', 'source_sha256')):
        if field.endswith('sha256'):
            if _hash(source[field], field) != _hash(geometry.get(record_field), record_field):
                raise OwnershipError('منشأ هندسه به رکورد نسخه‌دار متصل نیست')
        elif _id(source[field], field) != _id(geometry.get(record_field), record_field):
            raise OwnershipError('مرجع منشأ هندسه عضو برابر نیست')
    prep = _canonical(source['prepared_by'])
    reviewer = _canonical(source['reviewer'])
    if prep == reviewer or reviewer == _canonical(document['prepared_by']):
        raise OwnershipError('بازبینی مستقل هندسه عضو احراز نشده است')
    if reviewer == _canonical(data.get('source', {}).get('approved_by') or source['prepared_by']):
        raise OwnershipError('بازبین همان تأییدکننده منبع عضو است')
    return _box(source, 'منشور '+link['role']), record


def preview(document, project):
    """Resolve current record + physical evidence on every call; never persist.

    This envelope DOES NOT state that site drawing or structural safety is verified.
    """
    _object(document, _DOC, 'قرارداد هندسی اتصال تیر و ستون')
    if document['policy'] != POLICY:
        raise OwnershipError('قرارداد تخصصی هندسه اتصال ناشناخته است')
    if not isinstance(project, dict) or _id(project.get('id'), 'پروژه') != _id(document['project_id'], 'پروژه'):
        raise OwnershipError('پروژه Snapshot با سند اتصال برابر نیست')
    for field in ('joint_id', 'coordinate_ref', 'vertical_datum_ref',
                  'detail_ref', 'prepared_by', 'reviewer', 'ownership_reason'):
        _id(document[field], field)
    if _canonical(document['prepared_by']) == _canonical(document['reviewer']):
        raise OwnershipError('بازبین اتصال از تهیه‌کننده مستقل نیست')
    if document['ownership_status'] != 'unresolved' or document['reinforcement_status'] != 'not_reconciled':
        raise OwnershipError('مالکیت مالی و میلگرد اتصال هنوز تأیید نهایی نشده‌اند')
    links = document['links']
    if not isinstance(links, list) or len(links) != 2:
        raise OwnershipError('دقیقاً یک ستون و یک تیر نیاز است')
    prism = {}; record = {}; ids = set()
    for link in links:
        _object(link, _LINK, 'عضو مرتبط')
        role = _id(link['role'], 'نقش عضو')
        if role in prism or (role == 'column' and link['kind'] != 'column') or (
                role == 'counterpart' and link['kind'] != 'beam') or role not in ('column', 'counterpart'):
            raise OwnershipError('نقش عضو باید یک ستون و یک تیر واقعی باشد')
        for field in ('kind', 'floor_id', 'member_id', 'physical_id'):
            _id(link[field], field)
        identity = _canonical(link['physical_id'])
        if identity in ids:
            raise OwnershipError('شناسه فیزیکی دو عضو یکسان است')
        ids.add(identity)
        prism[role], record[role] = _member_prism(project, link, document)
        source_approver = record[role]['data'].get('source', {}).get('approved_by')
        if source_approver and _canonical(source_approver) == _canonical(document['reviewer']):
            raise OwnershipError('بازبین اتصال با تأییدکننده عضو یکی است')
    if set(prism) != {'column', 'counterpart'}:
        raise OwnershipError('اتصال واقعی تیر–ستون کامل نیست')
    if links[0]['floor_id'] != links[1]['floor_id']:
        raise OwnershipError('اتصال میان‌طبقه‌ای خارج از قرارداد است')
    # Physical aliases and shared bar-piece identities from *all* registered
    # members must not be silently booked under the new joint.
    all_bars = set()
    for register_name in ('reviewed_structural_members', 'beam_detail_register'):
        members = project.get(register_name, {})
        if not isinstance(members, dict):
            raise OwnershipError('دفتر اعضا معتبر نیست')
        for row in members.values():
            if not isinstance(row, dict) or not isinstance(row.get('data'), dict):
                raise OwnershipError('رکورد عضو دیگر معتبر نیست')
            data = row['data'];geom = data.get('geometry', {})
            if isinstance(geom, dict) and row is not record['column'] and row is not record['counterpart']:
                claims = [data.get('physical_id'), geom.get('physical_id'),
                          geom.get('physical_column_id'), geom.get('physical_cap_id')]
                if any(x is not None and _canonical(x) in ids for x in claims):
                    raise OwnershipError('هویت فیزیکی مشترک به عضو سوم نیز تعلق دارد')
            claims = _rebar_claims(data)
            if all_bars.intersection(claims):
                raise OwnershipError('هویت میلگرد در چند رکورد ثبت شده و مالکیت حل نشده است')
            all_bars.update(claims)
    joint_box = _intersection(prism['column'], prism['counterpart'])
    _object(document['panel_zone'], _ZONE, 'چشمه اتصال')
    zone = document['panel_zone']
    for field in ('id', 'physical_id', 'detail_ref', 'approved_by'):
        _id(zone[field], field)
    zone_id = _canonical(zone['physical_id'])
    if zone_id in ids or zone_id in all_bars:
        raise OwnershipError('هویت چشمه اتصال با عضو یا میلگرد موجود مشترک است')
    zbox = _box(zone, 'چشمه اتصال')
    if any(zbox[i] < joint_box[i] or zbox[i + 3] > joint_box[i + 3] for i in range(3)):
        raise OwnershipError('چشمه مستند کاملاً داخل حجم مشترک تیر و ستون نیست')
    connection = _volume(joint_box)
    panel = _volume(zbox)
    if (_num(document['connection_volume_m3'], 'حجم ادعایی مشترک') != connection or
            _num(document['panel_volume_m3'], 'حجم ادعایی چشمه') != panel):
        raise OwnershipError('مقدار ادعایی با حجم مستقل هندسی تطابق ندارد')
    if _canonical(document['reviewer']) == _canonical(zone['approved_by']):
        raise OwnershipError('بازبین نهایی باید از تأییدکننده محدوده چشمه مستقل باشد')
    return {
        'policy': POLICY, 'status': 'BEAM_COLUMN_PANEL_PREVIEW_ONLY',
        'scope': 'orthogonal_sourced_prisms',
        'member_geometry_record_bound': True,
        'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
        'observations': [
            {'operation': 'beam_column_connection', 'volume_m3': format(connection, 'f'),
             'unit': 'm3', 'basis': 'rectangular_3d_intersection'},
            {'operation': 'panel_zone', 'volume_m3': format(panel, 'f'),
             'unit': 'm3', 'basis': 'documented_rectangular_subset'},
        ],
        'blockers': [
            'حجم‌های گزارش‌شده هندسی و غیرقابل پرداخت هستند؛ بتن مشترک نباید دوباره وارد متره شود',
            'مالکیت بتن و میلگرد مشترک تا تطبیق مستقل حل‌نشده است',
            'SHA-256 فقط تمامیت مدارک را کنترل می‌کند و اصالت نقشه یا طراحی را اثبات نمی‌کند',
        ],
    }


def preview_file(project, path, sha256):
    """Re-read independent source bytes on every call and return ephemeral audit."""
    return preview(read_evidence(path, sha256), project)
