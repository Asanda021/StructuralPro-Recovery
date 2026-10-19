"""Read-only cross-member steel-stair support evidence preflight.

Reuses existing verified structural-record identity/revision guard. A checked
interface link is NOT geometric, structural, payment, or design acceptance.
There is no SQLite/BOQ mutation or commit path in this module.
"""
from __future__ import annotations

from hashlib import sha256

from core.takeoff.column_joint_preflight import _record
from core.takeoff.steel_stair_preflight import preview as preview_stair

POLICY = "steel_stair_support_crosswalk_chat_v1"
RECORD_FIELDS = frozenset(("role", "kind", "floor_id", "member_id", "physical_id",
                           "record_revision", "record_sha256"))
DOCUMENT_FIELDS = frozenset(("policy", "project_id", "building_id", "stair_id",
                             "floor_id", "source_sha256", "prepared_by",
                             "reviewer", "links"))
LINK_FIELDS = frozenset(("record", "interface_id", "interface_ref", "interface_sha256",
                         "contacts", "approved_by"))
CONTACT_FIELDS = frozenset(("physical_id", "scope_ref"))
LOAD_BEARING = frozenset(("stringers", "landings", "supports"))


def _id(value, label):
    if (not isinstance(value, str) or not value or value != value.strip()
            or any(ord(c) < 32 for c in value)):
        raise ValueError(f"{label}: شناسه مستند نامعتبر است")
    return value


def _strict(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError(f"{label}: قرارداد داده ناقص یا دارای فیلد اضافی است")


def _bytes_sha(blob, expected, label):
    if (not isinstance(expected, str) or len(expected) != 64
            or any(x not in '0123456789abcdef' for x in expected)):
        raise ValueError(f"{label}: هش SHA-256 نامعتبر است")
    if not isinstance(blob, bytes) or not blob or len(blob) > 4 * 1024 * 1024:
        raise ValueError(f"{label}: فایل واقعی ۱ بایت تا ۴ مگابایت لازم است")
    if sha256(blob).hexdigest() != expected:
        raise ValueError(f"{label}: بایت‌های مدرک با SHA-256 متفاوت‌اند")


def _project_physical(project):
    """Only member-level physical identifiers; not complete geometry or ownership."""
    seen = {}
    for register_name in ('reviewed_structural_members', 'beam_detail_register'):
        register = project.get(register_name, {})
        if not isinstance(register, dict):
            raise ValueError('دفتر عضو سازه‌ای نامعتبر است')
        for key, record in register.items():
            if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                raise ValueError('رکورد عضو سازه‌ای خراب است')
            data = record['data']
            geometry = data.get('geometry', {})
            if geometry is None:
                geometry = {}
            if not isinstance(geometry, dict):
                raise ValueError('ساختار هندسی عضو سازه‌ای خراب است')
            ids = [data.get('physical_id')] + [geometry.get(k) for k in (
                'physical_id', 'physical_column_id', 'physical_cap_id')]
            identities = {_id(x, 'شناسه فیزیکی رکورد') for x in ids if x is not None}
            if len(identities) > 1:
                raise ValueError('هویت فیزیکی یک عضو در فیلدهای مختلف ناسازگار است')
            for physical_id in identities:
                if physical_id in seen:
                    raise ValueError('یک هویت فیزیکی سازه در دو رکورد مستقل ثبت شده است')
                seen[physical_id] = (register_name, key)
    return seen


def _existing_part_ids(project):
    existing = project.get('takeoffs') or []
    if not isinstance(existing, list):
        raise ValueError('دفتر ریزمتره تاریخی نامعتبر است')
    ids = set()
    for row in existing:
        if not isinstance(row, dict):
            raise ValueError('ریزردیف متره تاریخی نامعتبر است')
        params = row.get('params') or {}
        if not isinstance(params, dict):
            raise ValueError('هویت قطعه در متره تاریخی نامعتبر است')
        for field in ('physical_component_id', 'physical_piece_id', 'physical_id',
                      'physical_key', 'physical_bar_id'):
            if field in params and params[field] is not None:
                ids.add(_id(params[field], 'هویت قطعه قبلی'))
    return ids


def audit(document, stair_document, project, *, drawing_bytes, interface_bytes):
    """Check bounded crosswalk; never authorize pay or claim complete supports."""
    result = {'policy': POLICY, 'kind': 'stair_metal', 'support_evidence_checked': False,
              'ready': False, 'commit_allowed': False, 'payable_rows': [],
              'bound_supports': [], 'blockers': []}
    try:
        _strict(document, DOCUMENT_FIELDS, 'سند رابط پله فولادی')
        if document['policy'] != POLICY:
            raise ValueError('نسخه قرارداد رابط پله فولادی معتبر نیست')
        if not isinstance(project, dict) or not isinstance(stair_document, dict):
            raise ValueError('نسخه واقعی پروژه و دیتایل پله لازم است')
        for name, given in (('project_id', project.get('id')),
                            ('building_id', stair_document.get('building_id')),
                            ('floor_id', stair_document.get('floor_id')),
                            ('stair_id', stair_document.get('system_id')),
                            ('source_sha256', stair_document.get('source', {}).get('sha256'))):
            if _id(document[name], name) != _id(given, name):
                raise ValueError(f'{name}: هویت یا نسخه دیتایل پله متفاوت است')
        _id(document['prepared_by'], 'تهیه‌کننده')
        _id(document['reviewer'], 'بازبین')
        if document['prepared_by'] == document['reviewer']:
            raise ValueError('بازبین مستقل از تهیه‌کننده نیست')
        _bytes_sha(drawing_bytes, document['source_sha256'], 'فایل واقعی نقشه پله')
        stair = preview_stair(stair_document)
        if (not stair.get('engineering_ready') or stair.get('ready') is not False
                or stair.get('commit_allowed') is not False or stair.get('payable_rows') != []):
            raise ValueError('پیش‌ارزیابی مستقل پله معتبر یا غیرمالی نیست')
        candidates = stair['candidates']
        stair_ids = {_id(x['physical_id'], 'شناسه قطعه پله'): x for x in candidates}
        required_ids = {x['physical_id'] for x in candidates if x['component'] in LOAD_BEARING}
        if not required_ids:
            raise ValueError('جزء سازه‌ای لازم برای لینک تکیه‌گاه شناسایی نشد')
        project_members = _project_physical(project)
        if any(p in project_members or p in _existing_part_ids(project) for p in stair_ids):
            raise ValueError('هویت قطعه پله قبلاً در دفتر سازه یا متره مصرف شده است')
        links = document['links']
        if not isinstance(links, list) or not 0 < len(links) <= 32:
            raise ValueError('سند رابط باید لینک تکیه‌گاه مستقل داشته باشد')
        if not isinstance(interface_bytes, dict):
            raise ValueError('بایت‌های واقعی مدارک رابط لازم است')
        contact_seen = set()
        interface_seen = set()
        support_seen = set()
        verified = []
        for link in links:
            _strict(link, LINK_FIELDS, 'رابط تکیه‌گاه')
            _strict(link['record'], RECORD_FIELDS, 'لینک رکورد واقعی سازه')
            identifier = _id(link['interface_id'], 'شناسه رابط')
            if identifier in interface_seen:
                raise ValueError('رابط تکیه‌گاه با شناسه تکراری')
            interface_seen.add(identifier)
            record = link['record']
            if (record['role'] == 'column') != (record['kind'] == 'column'):
                raise ValueError('نقش ستون با نوع عضو متناظر نیست')
            physical_support = _id(record['physical_id'], 'عضو تکیه‌گاه')
            if physical_support in support_seen or physical_support in stair_ids:
                raise ValueError('هویت تکیه‌گاه مشترک یا تکراری است')
            support_seen.add(physical_support)
            original = _record(project, record)  # Existing real snapshot/CAS/digest verifier.
            if physical_support not in project_members:
                raise ValueError('عضو تکیه‌گاه در دفتر نسخه‌دار سازه شناسایی نشد')
            _id(link['interface_ref'], 'مرجع دیتایل اتصال')
            _id(link['approved_by'], 'بازبین دیتایل اتصال')
            if link['approved_by'] == document['prepared_by']:
                raise ValueError('بررسی اتصال توسط تهیه‌کننده مستقل نیست')
            if original['data'].get('source', {}).get('approved_by') == document['reviewer']:
                raise ValueError('بازبین رابط با تأییدکننده رکورد عضو یکی است')
            document_hash = link['interface_sha256']
            _bytes_sha(interface_bytes.get(document_hash), document_hash, 'مدرک واقعی رابط')
            contacts = link['contacts']
            if not isinstance(contacts, list) or not contacts:
                raise ValueError('لینک رابط فاقد قطعه فیزیکی پله است')
            on_link = set()
            for contact in contacts:
                _strict(contact, CONTACT_FIELDS, 'شناسه و دامنه قطعه متصل')
                pid = _id(contact['physical_id'], 'شناسه قطعه متصل')
                scope = _id(contact['scope_ref'], 'دامنه فیزیکی اتصال')
                if pid not in stair_ids or stair_ids[pid]['scope_ref'] != scope:
                    raise ValueError('قطعه پله یا دامنه آن با دیتایل واقعی منطبق نیست')
                if pid in on_link or pid in contact_seen:
                    raise ValueError('قطعه باربر پله در چند رابط تکیه‌گاهی تکرار شده است')
                on_link.add(pid)
                contact_seen.add(pid)
            verified.append({'interface_id': identifier, 'support_member_id': record['member_id'],
                             'support_physical_id': physical_support,
                             'stair_physical_ids': sorted(on_link),
                             'record_revision': record['record_revision'],
                             'record_sha256': record['record_sha256'],
                             'interface_sha256': document_hash})
        if not required_ids.issubset(contact_seen):
            raise ValueError('اتصال تمام قطعات باربر پله به تکیه‌گاه‌های مستند احراز نشد')
        result['support_evidence_checked'] = True
        result['bound_supports'] = verified
        result['blockers'].append('تطبیق نسخه و بایت‌های مدارک انجام شد؛ هندسه تماس، ظرفیت، مالکیت سراسری و پرداخت همچنان فاقد پذیرش مستقل است')
    except (KeyError, ValueError, TypeError, AttributeError, ArithmeticError) as exc:
        result['blockers'].append(str(exc))
    return result
