"""Opt-in, revision-bound horizontal evidence for pile-cap/column spatial previews.

The evidence is an independent immutable-on-disk JSON file. The versioned
member draft pins its SHA and the source coordinates. A matching SHA is only
byte integrity, not drawing authenticity, engineering approval or BOQ consent.
Old members are never migrated or treated as geometrically verified.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _object, _id, _hash, _canonical, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num, _require_independent_joint_reviewer

POLICY = 'counterpart_rectangular_footprint_v1'
FOOTPRINT = 'spatial_footprint_v1'
_AXES = ('x_min_m', 'y_min_m', 'x_max_m', 'y_max_m',
         'top_elevation_m', 'bottom_elevation_m')
_DIMENSIONS = ('width_m', 'depth_m')
_BODY = ('policy', 'project_id', 'kind', 'floor_id', 'member_id', 'physical_id',
         'coordinate_ref', 'vertical_datum_ref', 'geometry_source_ref',
         'geometry_source_sha256', 'prepared_by', 'reviewer') + _AXES + _DIMENSIONS
_RECORD = ('policy', 'path', 'sha256', 'reference', 'coordinate_ref',
           'vertical_datum_ref') + _AXES + _DIMENSIONS
_KEYS = ('x_min_m', 'y_min_m', 'x_max_m', 'y_max_m')


def _geometry(doc, *, project_id, data):
    _object(doc, _BODY, 'مدرک مستقل پلان کلاهک/ستون')
    if doc['policy'] != POLICY:
        raise OwnershipError('قرارداد مرز افقی عضو پشتیبانی نمی‌شود')
    if doc['kind'] not in ('pile_cap', 'column') or doc['kind'] != data.get('kind'):
        raise OwnershipError('نوع عضو مدرک پلان با عضو واقعی سازگار نیست')
    for field, expected in (('project_id', project_id), ('floor_id', data.get('floor_id')),
                            ('member_id', data.get('member_id'))):
        if _id(doc[field], field) != _id(expected, field):
            raise OwnershipError('شناسه مدرک هندسی با رکورد عضو متفاوت است')
    g = data.get('geometry')
    if not isinstance(g, dict):
        raise OwnershipError('هندسه عضو نسخه‌دار موجود نیست')
    physical = (g.get('physical_cap_id') if doc['kind'] == 'pile_cap'
                else g.get('physical_column_id')) or g.get('physical_id') or data.get('physical_id')
    if _canonical(doc['physical_id']) != _canonical(physical):
        raise OwnershipError('شناسه فیزیکی مرز افقی با عضو واقعی متفاوت است')
    for field, source in (('geometry_source_ref', 'source_ref'),
                          ('geometry_source_sha256', 'source_sha256')):
        check = _hash if source == 'source_sha256' else _id
        if check(doc[field], field) != check(g.get(source), source):
            raise OwnershipError('مدرک مستقل با منبع هندسی رکورد مطابقت ندارد')
    if _canonical(doc['reviewer']) == _canonical(doc['prepared_by']):
        raise OwnershipError('بازبین هندسی نباید تهیه‌کننده مدرک باشد')
    _require_independent_joint_reviewer(_canonical(doc['reviewer']), data)
    for field in ('coordinate_ref', 'vertical_datum_ref'):
        _id(doc[field], field)
    axes = {k: _num(doc[k], k) for k in _AXES}
    if (axes['x_max_m'] <= axes['x_min_m'] or
            axes['y_max_m'] <= axes['y_min_m'] or
            axes['top_elevation_m'] <= axes['bottom_elevation_m']):
        raise OwnershipError('ابعاد یا تراز هندسی مدرک مستقل نامعتبر است')
    if (_num(doc['width_m'], 'عرض مقطع') != axes['x_max_m'] - axes['x_min_m'] or
            _num(doc['depth_m'], 'عمق مقطع') != axes['y_max_m'] - axes['y_min_m']):
        raise OwnershipError('ابعاد مقطع با حدود مستند X/Y برابر نیست')
    for field in ('top_elevation_m', 'bottom_elevation_m'):
        if axes[field] != _num(g.get(field), 'تراز رکورد عضو'):
            raise OwnershipError('تراز سند افقی با عضو واقعی برابر نیست')
    return axes


def _read(path):
    file = Path(path)
    if not file.is_file() or file.stat().st_size < 2 or file.stat().st_size > 4*1024*1024:
        raise OwnershipError('فایل واقعی مدرک مرز افقی عضو موجود نیست')
    raw = file.read_bytes()
    digest = sha256(raw).hexdigest()
    return read_evidence(str(file), digest), str(file.resolve()), digest


def bind_draft(draft, project_id, path, *, reference):
    """Prepare a *new* member draft; persistence must use the regular SQLite CAS API.

    Does not save or silently migrate a historical/committed record. Existing
    footprint evidence is immutable here; amendment requires an explicit flow.
    """
    if not isinstance(draft, dict) or draft.get('kind') not in ('pile_cap', 'column'):
        raise OwnershipError('فقط پیش‌نویس کلاهک یا ستون قابلیت اتصال مدرک افقی دارد')
    reference = _id(reference, 'مرجع هندسه مستند')
    if not isinstance(draft.get('geometry'), dict):
        raise OwnershipError('هندسه رکورد واقعی موجود نیست')
    if FOOTPRINT in draft['geometry']:
        raise OwnershipError('جایگزینی مدرک افقی نیازمند اصلاحیه نسخه‌دار مستقل است')
    doc, file, digest = _read(path)
    _geometry(doc, project_id=project_id, data=draft)
    candidate = deepcopy(draft)
    candidate['geometry'][FOOTPRINT] = {
        'policy': POLICY, 'path': file, 'sha256': digest, 'reference': reference,
        'coordinate_ref': doc['coordinate_ref'],
        'vertical_datum_ref': doc['vertical_datum_ref'],
        **{k: doc[k] for k in _AXES + _DIMENSIONS},
    }
    return candidate


def verify_record_bound(record, *, project_id, link, spatial_item,
                        coordinate_ref, vertical_datum_ref):
    """None for historical/unbound records; True only for file/record/link equality.

    A claimed footprint that is present but broken MUST raise; never silently
    downgrade tampered new-version evidence to a historic no-evidence result.
    """
    data = record.get('data', {})
    geometry = data.get('geometry', {})
    if not isinstance(geometry, dict) or FOOTPRINT not in geometry:
        return False
    payload = geometry[FOOTPRINT]
    _object(payload, _RECORD, 'مرز افقی ثبت‌شده در نسخه عضو')
    if payload['policy'] != POLICY:
        raise OwnershipError('نسخه مدرک افقی در رکورد ناشناخته است')
    _id(payload['reference'], 'مرجع مدرک مرز افقی')
    for key in ('coordinate_ref', 'vertical_datum_ref'):
        if _id(payload[key], key) != _id({'coordinate_ref':coordinate_ref,
                                        'vertical_datum_ref':vertical_datum_ref}[key], key):
            raise OwnershipError('مرجع مختصات یا مبنای تراز با رکورد شمع ناسازگار است')
    doc = read_evidence(_id(payload['path'], 'مسیر مدرک'),
                        _hash(payload['sha256'], 'SHA-256 مدرک مرز افقی'))
    axes = _geometry(doc, project_id=project_id, data=data)
    for field in ('coordinate_ref','vertical_datum_ref'):
        if doc[field] != payload[field]:
            raise OwnershipError('مرجع مختصات مدرک با Snapshot متفاوت است')
    if (doc['coordinate_ref'] != coordinate_ref or
            doc['vertical_datum_ref'] != vertical_datum_ref):
        raise OwnershipError('مختصات مدرک با مبنای مشترک پروژه یکسان نیست')
    for name in _AXES + _DIMENSIONS:
        value = _num(payload[name], 'مرز ذخیره‌شده')
        expected = axes[name] if name in axes else _num(doc[name], name)
        if value != expected:
            raise OwnershipError('مرز هندسی ثبت‌شده در رکورد با مدرک مستقل متفاوت است')
        if name in _DIMENSIONS:
            continue
        item_name = {'x_min_m':'other_x_min_m', 'y_min_m':'other_y_min_m',
                     'x_max_m':'other_x_max_m', 'y_max_m':'other_y_max_m',
                     'top_elevation_m':'other_top_m', 'bottom_elevation_m':'other_bottom_m'}[name]
        if value != _num(spatial_item[item_name], item_name):
            raise OwnershipError('مختصات مورد استفاده در حجم مشترک با مدرک نسخه‌دار تفاوت دارد')
    if (doc['kind'] != link['other_kind'] or
            doc['member_id'] != link['other_member_id'] or
            doc['physical_id'] != link['other_physical_id'] or
            doc['geometry_source_ref'] != link['geometry_reference'] or
            doc['geometry_source_sha256'] != link['geometry_sha256']):
        raise OwnershipError('هویت و منبع مدرک مرز افقی با قرارداد مشترک برابر نیست')
    return True
