"""Read-only six-family material/physical-identity reconciliation for phase 1.

Consumes version-pinned REAL project registry snapshots and external documentary
claims. Never assumes geometry, creates a BOQ row, or authorizes payment.
Existing specialist engines remain calculation authorities.
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation, Inexact, Rounded, localcontext
from hashlib import sha256
import json
import unicodedata

POLICY = 'six_family_physical_ownership_chat_v1'
FAMILIES = frozenset(('foundation', 'tie_beam', 'column', 'beam', 'slab', 'stair'))
KIND_TO_FAMILY = {
    'isolated_footing': 'foundation', 'strip_footing': 'foundation',
    'mat_footing': 'foundation', 'pile_cap': 'foundation', 'foundation': 'foundation',
    'tie_beam': 'tie_beam', 'column': 'column', 'beam': 'beam',
    'solid_slab': 'slab', 'joist_block': 'slab', 'joist_foam': 'slab',
    'waffle': 'slab', 'waffle_one_way': 'slab', 'waffle_two_way': 'slab',
    'stair': 'stair',
}
REGISTERS = frozenset(('reviewed_structural_members', 'beam_detail_register', 'reviewed_aec_systems'))
OPERATIONS = {'concrete': 'm3', 'rebar': 'kg', 'formwork': 'm2'}
LINK_FIELDS = frozenset(('family','kind','floor_id','member_id','physical_member_id',
                         'source_id','registry','record_key','record_revision','record_sha256'))
CLAIM_FIELDS = frozenset(('source_id','operation','physical_id','scope_id',
                          'role','payer_source_id','quantity_exact','unit',
                          'detail_ref','evidence_sha256','prepared_by','reviewed_by'))
INTERFACE_FIELDS = frozenset(('member_left','member_right','operation',
                              'interface_id','coordinate_ref','detail_ref',
                              'geometry_evidence_sha256','prepared_by','reviewed_by',
                              'assessment'))
DOC_FIELDS = frozenset(('policy','project_id','building_id','project_sha256',
                        'links','claims','interfaces'))
PHYSICAL_FIELDS = ('physical_id','physical_component_id','physical_piece_id',
                   'physical_bar_id','physical_key')


class SixFamilyOwnershipError(ValueError):
    """Missing or contradictory cross-family source, component or payer evidence."""


def _strict(value, keys, label):
    if not isinstance(value, dict) or set(value) != keys:
        raise SixFamilyOwnershipError(f'{label}: قرارداد ناقص یا کلید ناشناخته')


def _alias(value):
    return unicodedata.normalize('NFKC', value).replace('ي', 'ی').replace('ك', 'ک').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩', '01234567890123456789')).casefold()


def _name(value, label):
    if not isinstance(value, str) or not value or value != value.strip() or any(unicodedata.category(ch) in ('Cc','Cf') for ch in value):
        raise SixFamilyOwnershipError(f'{label}: شناسه/مرجع صریح معتبر لازم است')
    return value


def _hash(value, label):
    if not isinstance(value, str) or len(value) != 64 or any(x not in '0123456789abcdef' for x in value):
        raise SixFamilyOwnershipError(f'{label}: SHA-256 معتبر لازم است')
    return value


def _digest(value):
    """Same canonical record digest as the existing bored-pile joint crosswalk."""
    try:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(',', ':'), allow_nan=False,
                             default=lambda x: str(x) if isinstance(x, Decimal) and x.is_finite() else _unsupported(x))
    except (TypeError, ValueError, OverflowError) as exc:
        raise SixFamilyOwnershipError('Snapshot ناسازگار با SHA-256') from exc
    return sha256(payload.encode('utf-8')).hexdigest()


def _unsupported(value):
    raise TypeError(f'نوع داده ناسازگار: {type(value).__name__}')


def _number(value, label):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise SixFamilyOwnershipError(f'{label}: فقط مقدار Decimal صریح')
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SixFamilyOwnershipError(f'{label}: عدد نامعتبر') from exc
    if not d.is_finite() or d <= 0 or len(d.as_tuple().digits) > 120 or abs(d.adjusted()) > 120:
        raise SixFamilyOwnershipError(f'{label}: مثبت متناهی و در دامنه معتبر لازم است')
    return d


def _bytes(sha, documents, label):
    _hash(sha, label)
    content = documents.get(sha)
    if not isinstance(content, bytes) or not content or len(content) > 4 * 1024 * 1024:
        raise SixFamilyOwnershipError(f'{label}: فایل معتبر تا چهار مگابایت لازم است')
    if sha256(content).hexdigest() != sha:
        raise SixFamilyOwnershipError(f'{label}: مغایرت بایت با هش')


def _member(project, link):
    _strict(link, LINK_FIELDS, 'لینک عضو')
    for key in ('family','kind','floor_id','member_id','physical_member_id','source_id','registry','record_key'):
        _name(link[key], key)
    if link['family'] not in FAMILIES or KIND_TO_FAMILY.get(link['kind']) != link['family']:
        raise SixFamilyOwnershipError('خانواده و نوع عضو سازه‌ای ناسازگار')
    if link['registry'] not in REGISTERS:
        raise SixFamilyOwnershipError('دفتر نسخه‌دار نامعتبر است')
    if (link['kind'] == 'beam') != (link['registry'] == 'beam_detail_register'):
        raise SixFamilyOwnershipError('تیر باید از دفتر اصلی تیر نسخه‌دار خوانده شود')
    if link['kind'] in ('stair','solid_slab','joist_block','joist_foam','waffle','waffle_one_way','waffle_two_way'):
        if link['registry'] != 'reviewed_aec_systems':
            raise SixFamilyOwnershipError('سقف یا پله باید به رکورد AEC واقعی متصل باشد')
    registry = project.get(link['registry'])
    if not isinstance(registry, dict) or link['record_key'] not in registry:
        raise SixFamilyOwnershipError('دفتر واقعی عضو یا رکورد مورد نظر موجود نیست')
    rec = registry[link['record_key']]
    if not isinstance(rec, dict) or not isinstance(rec.get('data'), dict):
        raise SixFamilyOwnershipError('ساختار رکورد عضو نامعتبر است')
    if (type(link['record_revision']) is not int or link['record_revision'] < 1 or
            type(rec.get('revision')) is not int or rec['revision'] < 1 or
            rec['revision'] != link['record_revision'] or
            rec.get('status') not in ('draft','committed')):
        raise SixFamilyOwnershipError('Revision یا وضعیت رکورد عضو تغییر کرده است')
    if _hash(link['record_sha256'],'هش نسخه عضو') != _digest(rec):
        raise SixFamilyOwnershipError('رکورد سازه بعد از تهیه مدرک تغییر کرده است')
    data = rec['data']
    kind = 'beam' if link['registry'] == 'beam_detail_register' else data.get('kind')
    member_id = data.get('beam_id' if link['registry'] == 'beam_detail_register' else
                         'system_id' if link['registry'] == 'reviewed_aec_systems' else 'member_id')
    if (kind, data.get('floor_id'), member_id) != (link['kind'], link['floor_id'], link['member_id']):
        raise SixFamilyOwnershipError('شناسه واقعی عضو و لینک اظهارشده متفاوت است')
    source = data.get('source') or {}
    source_id = source.get('source_id') if isinstance(source, dict) else None
    if source_id != link['source_id']:
        raise SixFamilyOwnershipError('شناسه منبع رکورد با سند مالکیت متفاوت است')
    geometry = data.get('geometry') or {}
    if not isinstance(geometry, dict):
        raise SixFamilyOwnershipError('هندسه ثبت‌شده خراب است')
    ids = [data.get('physical_id')] + [geometry.get(k) for k in ('physical_id','physical_column_id','physical_cap_id')]
    present = {_name(x,'شناسه فیزیکی عضو') for x in ids if x is not None}
    if len(present) != 1 or link['physical_member_id'] not in present:
        raise SixFamilyOwnershipError('هویت فیزیکی عضو در Snapshot یکتا و قابل بازیابی نیست')
    return rec


def audit(document, project, *, documents):
    """Pure conservative collision analysis; never a payment or design authorization.

    Missing physical geometry never implies that different scope IDs cannot
    overlap. Even complete synthetic documentary claims remain non-payable.
    """
    result = {'policy': POLICY, 'document_consistent': False, 'ready': False,
              'commit_allowed': False, 'payable_rows': [], 'physical_owner_count': 0,
              'material_rows_by_operation': {}, 'blocked_historical_rows': [],
              'blocked_historical_boq_rows': [],
              'unresolved_interfaces': [], 'blockers': [], 'totals_not_payable': {}}
    try:
        _strict(document, DOC_FIELDS, 'سند مشترک شش خانواده')
        if document['policy'] != POLICY or not isinstance(project, dict) or not isinstance(documents, dict):
            raise SixFamilyOwnershipError('قرارداد/پروژه/مدارک معتبر نیست')
        _name(document['project_id'],'پروژه'); _name(document['building_id'],'ساختمان')
        if document['project_id'] != project.get('id'):
            raise SixFamilyOwnershipError('Snapshot متعلق به پروژه دیگری است')
        if project.get('building_id') is not None and document['building_id'] != project['building_id']:
            raise SixFamilyOwnershipError('شناسه ساختمان پروژه و سند مشترک متفاوت است')
        if _hash(document['project_sha256'],'Snapshot پروژه') != _digest(project):
            raise SixFamilyOwnershipError('Snapshot پروژه یا دفترهای عضو تغییر کرده‌اند')
        links = document['links']
        if not isinstance(links, list) or not 6 <= len(links) <= 1000:
            raise SixFamilyOwnershipError('حداقل شش عضو از شش خانواده لازم است')
        sources = {}; members = {}; families = set()
        physical_members = set(); aliases = set(); linked_keys = set()
        for link in links:
            _member(project, link)
            source = link['source_id']; physical = link['physical_member_id']
            if (source in sources or physical in physical_members or
                    _alias(source) in aliases or _alias(physical) in aliases):
                raise SixFamilyOwnershipError('منبع یا عضو فیزیکی در چند دفتر تکرار شده است')
            sources[source] = link
            members[physical] = source
            physical_members.add(physical); families.add(link['family'])
            aliases.add(_alias(source)); aliases.add(_alias(physical))
            linked_keys.add((link['registry'],link['record_key']))
        if families != FAMILIES:
            raise SixFamilyOwnershipError('پوشش هر شش خانواده پی، شناژ، ستون، تیر، سقف، پله اجباری است')
        # Never silently treat an omitted existing member as outside the project.
        for register_name in REGISTERS:
            for record_key, record in (project.get(register_name) or {}).items():
                if not isinstance(record,dict) or not isinstance(record.get('data'),dict):
                    raise SixFamilyOwnershipError('Snapshot یکی از اعضای سازه‌ای نامعتبر است')
                data = record['data']
                kind = 'beam' if register_name == 'beam_detail_register' else data.get('kind')
                if kind in KIND_TO_FAMILY and (register_name,record_key) not in linked_keys:
                    raise SixFamilyOwnershipError('عضو سازه‌ای موجود در دفتر مشترک شش خانواده جا افتاده است')
        member_aliases = {_alias(x) for x in physical_members}
        claims = document['claims']
        if not isinstance(claims, list) or not claims or len(claims) > 20000:
            raise SixFamilyOwnershipError('فهرست مستند بتن/قالب/میلگرد لازم است')
        groups = defaultdict(list)
        per_member_op = set()
        operation_by_physical = {}; canonical_physical = {}; canonical_scope = {}
        for claim in claims:
            _strict(claim, CLAIM_FIELDS, 'ادعای مالکیت ریزمتره')
            for key in ('source_id','operation','physical_id','scope_id','role','payer_source_id',
                        'unit','detail_ref','prepared_by','reviewed_by'):
                _name(claim[key], key)
            if claim['source_id'] not in sources or claim['payer_source_id'] not in sources:
                raise SixFamilyOwnershipError('عضو صاحب ادعا یا مالک پرداخت در Snapshot نیست')
            op = claim['operation']
            if op not in OPERATIONS or claim['unit'] != OPERATIONS[op]:
                raise SixFamilyOwnershipError('واحد بتن/قالب/میلگرد با عملیات ناسازگار است')
            if claim['role'] not in ('payer','reference'):
                raise SixFamilyOwnershipError('نقش فقط پرداخت‌کننده یا ارجاعی است')
            if (claim['role'] == 'payer') != (claim['source_id'] == claim['payer_source_id']):
                raise SixFamilyOwnershipError('ادعای پرداخت یا ارجاع به مالک صحیح متصل نیست')
            if claim['prepared_by'].casefold() == claim['reviewed_by'].casefold():
                raise SixFamilyOwnershipError('بازبین مستقل از تهیه‌کننده نیست')
            _number(claim['quantity_exact'], 'ریزکمیت')
            _bytes(claim['evidence_sha256'], documents,'مدرک ریزقلم')
            physical = claim['physical_id']; memberop = (claim['source_id'],op,_alias(physical))
            if _alias(physical) in member_aliases:
                raise SixFamilyOwnershipError('قطعه و خود عضو سازه‌ای نباید هویت مشترک داشته باشند')
            if _alias(physical) in canonical_physical and canonical_physical[_alias(physical)] != physical:
                raise SixFamilyOwnershipError('شناسه فیزیکی با هویت نوشتاری معادل تکرار شده است')
            canonical_physical[_alias(physical)] = physical
            if memberop in per_member_op:
                raise SixFamilyOwnershipError('یک عضو ریزقلم فیزیکی را تکرار کرده است')
            per_member_op.add(memberop)
            if physical in operation_by_physical and operation_by_physical[physical] != op:
                raise SixFamilyOwnershipError('شناسه فیزیکی میان مصالح مختلف مبهم است')
            operation_by_physical[physical] = op
            groups[(op, physical)].append(claim)
        paid_scope = set(); totals = defaultdict(list)
        row_counts = defaultdict(int)
        for (op, physical), attached in groups.items():
            payers = [x for x in attached if x['role'] == 'payer']
            if len(payers) != 1:
                raise SixFamilyOwnershipError('هر قطعه فیزیکی باید دقیقاً یک مالک پرداخت داشته باشد')
            canonical = payers[0]
            if any(x['payer_source_id'] != canonical['source_id'] or
                   x['scope_id'] != canonical['scope_id'] or
                   _number(x['quantity_exact'],'مقدار مشترک') != _number(canonical['quantity_exact'],'مقدار پرداخت')
                   for x in attached):
                raise SixFamilyOwnershipError('منبع پرداخت، محدوده یا مقدار ادعاهای مشترک با هم نمی‌خواند')
            scope = (op, canonical['scope_id'])
            norm_scope = (op, _alias(canonical['scope_id']))
            if norm_scope in paid_scope:
                raise SixFamilyOwnershipError('دو قطعه، حجم/وجه/قطعه میلگرد مشترک را دوبار حساب می‌کنند')
            paid_scope.add(norm_scope)
            totals[op].append(_number(canonical['quantity_exact'], 'مقدار پرداخت'))
            row_counts[op] += 1
        # Existing takeoffs must not silently make an otherwise unique new payer valid.
        history = project.get('takeoffs') or []
        if not isinstance(history, list):
            raise SixFamilyOwnershipError('دفتر تاریخی ریزمتره خراب است')
        historical_unknown = []
        for index,row in enumerate(history):
            if not isinstance(row, dict):
                raise SixFamilyOwnershipError('ردیف تاریخچه معتبر نیست')
            params = row.get('params') or {}
            if not isinstance(params, dict):
                raise SixFamilyOwnershipError('پارامترهای قدیمی خراب است')
            ids = [x for x in [row.get(k) for k in PHYSICAL_FIELDS] +
                   [params.get(k) for k in PHYSICAL_FIELDS] if x is not None]
            ids = {_name(x,'شناسه فیزیکی تاریخی') for x in ids}
            if len(ids) > 1:
                raise SixFamilyOwnershipError('هویت‌های فیزیکی متعارض در ردیف تاریخی')
            if ids and _alias(next(iter(ids))) in canonical_physical:
                raise SixFamilyOwnershipError('قطعه جدید قبلاً در تاریخچه ریزمتره وجود دارد')
            if not ids:
                historical_unknown.append(index)
        history_boq = project.get('boq') or []
        if not isinstance(history_boq, list):
            raise SixFamilyOwnershipError('دفتر تاریخی BOQ خراب است')
        old_boq_unidentified = []
        for index,row in enumerate(history_boq):
            if not isinstance(row, dict):
                raise SixFamilyOwnershipError('ساختار ردیف تاریخی BOQ خراب است')
            params = row.get('params') or {}
            if not isinstance(params,dict):
                raise SixFamilyOwnershipError('شناسه BOQ تاریخی نامعتبر است')
            ids = [v for v in [row.get(k) for k in PHYSICAL_FIELDS] +
                   [params.get(k) for k in PHYSICAL_FIELDS] if v is not None]
            ids = {_name(v,'شناسه فیزیکی BOQ') for v in ids}
            if len({_alias(x) for x in ids}) > 1:
                raise SixFamilyOwnershipError('هویت‌های متعارض در BOQ قبلی')
            if ids and _alias(next(iter(ids))) in canonical_physical:
                raise SixFamilyOwnershipError('قطعه در BOQ پیشین وجود دارد؛ پرداخت دوم ممنوع')
            if not ids:
                old_boq_unidentified.append(index)
        # Interface evidence is mandatory for any cross-member joint explicitly
        # declared; it cannot establish actual geometric disjointness.
        interfaces = document['interfaces']
        if not isinstance(interfaces, list) or len(interfaces) > 20000:
            raise SixFamilyOwnershipError('فهرست فصل مشترک‌های سازه‌ای معتبر نیست')
        seen_interfaces = set(); unresolved = []
        for entry in interfaces:
            _strict(entry, INTERFACE_FIELDS, 'فصل مشترک اعضا')
            for k in ('member_left','member_right','operation','interface_id','coordinate_ref','detail_ref','prepared_by','reviewed_by','assessment'):
                _name(entry[k], k)
            if (entry['member_left'] not in members or entry['member_right'] not in members or
                    entry['member_left'] == entry['member_right'] or entry['operation'] not in OPERATIONS):
                raise SixFamilyOwnershipError('عضو یا نوع عملیات فصل مشترک معتبر نیست')
            if entry['prepared_by'].casefold() == entry['reviewed_by'].casefold():
                raise SixFamilyOwnershipError('تهیه‌کننده و بازبین فصل مشترک مستقل نیستند')
            key = (frozenset((entry['member_left'],entry['member_right'])),entry['operation'])
            if key in seen_interfaces:
                raise SixFamilyOwnershipError('فصل مشترک میان همان دو عضو و مصالح تکرار شده است')
            seen_interfaces.add(key)
            _bytes(entry['geometry_evidence_sha256'], documents, 'مدرک هندسه فصل مشترک')
            if entry['assessment'] != 'UNVERIFIED_NEEDS_GEOMETRY':
                raise SixFamilyOwnershipError('این ابزار اجازه اعلام رفع تعارض هندسی را ندارد')
            unresolved.append(entry['interface_id'])
        with localcontext() as ctx:
            ctx.prec = 1024
            ctx.traps[Inexact] = True
            ctx.traps[Rounded] = True
            exact_totals = {op: format(sum(values, Decimal(0)), 'f') for op, values in sorted(totals.items())}
            result.update(document_consistent=True,
                          physical_owner_count=len(groups),
                          material_rows_by_operation=dict(row_counts),
                          totals_not_payable=exact_totals,
                          blocked_historical_rows=historical_unknown,
                          blocked_historical_boq_rows=old_boq_unidentified,
                          unresolved_interfaces=unresolved)
        result['blockers'].extend([
            'تطبیق شناسه و مالک پرداخت فقط در مدارک ارائه‌شده انجام شد؛ کامل‌بودن همه اعضای ساختمان اثبات نشده است',
            'هم‌پوشانی واقعی حجم بتن، وجه قالب و قطعات میلگرد با هندسه و نقشه واقعی حل نشده است',
            'اعتبار امضای مهندسی، تعلق مدارک به ساختمان، و صلاحیت بازبین احراز نشده است',
            'ثبت مالی، SQLite/CAS، اصلاحیه و انتقال به BOQ همچنان غیرمجاز است',
        ])
        if old_boq_unidentified:
            result['blockers'].append(f'{len(old_boq_unidentified)} ردیف BOQ تاریخی فاقد شناسه فیزیکی و قابل تبرئه نیستند')
        if historical_unknown:
            result['blockers'].append(f'{len(historical_unknown)} ردیف تاریخی فاقد شناسه فیزیکی و قابل تأیید نیستند')
        if not unresolved:
            result['blockers'].append('هیچ فصل مشترک هندسی مستقل ارائه نشد؛ نبود تماس اعضا نتیجه‌گیری نمی‌شود')
    except (SixFamilyOwnershipError, KeyError, TypeError, OverflowError, ArithmeticError) as exc:
        result['blockers'].append(str(exc))
    return result
