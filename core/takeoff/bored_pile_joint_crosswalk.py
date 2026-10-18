"""Read-only bored-pile/pile-cap/column geometric and rebar ownership crosswalk.

This is *not* an authorization engine. A document SHA is an integrity check,
not proof of engineering authorship, ledger completeness or entitlement.
No settlement, BOQ rows, register or SQLite data are mutated here.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, audit as ownership_audit,
)

POLICY = 'bored_pile_joint_crosswalk_v1'
_REG = 'reviewed_structural_members'
_EXTERNAL_KINDS = frozenset(('pile_cap', 'column'))
_JOINT_KEYS = ('policy', 'project_id', 'floor_id', 'group_id', 'input_sha256',
               'ownership_sha256', 'coordinate_ref', 'vertical_datum_ref',
               'prepared_by', 'reviewer', 'interfaces', 'bar_transfers')
_LINK_KEYS = ('pile_id', 'other_kind', 'other_floor_id', 'other_member_id',
              'other_physical_id', 'other_record_sha256', 'other_revision',
              'geometry_reference', 'geometry_sha256', 'spatial_status',
              'pile_top_m', 'pile_bottom_m', 'other_top_m', 'other_bottom_m',
              'overlap_volume_m3', 'deduction_id', 'allocation_owner')
_BAR_KEYS = ('pile_id', 'bar_piece_id', 'other_kind', 'other_floor_id',
             'other_member_id', 'other_bar_physical_id', 'payer_kind',
             'source_ref', 'source_sha256')


def _num(value, label, *, positive=False):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise OwnershipError(label + ': Decimal یا متن صریح لازم است؛ float ممنوع')
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise OwnershipError(label + ': مقدار عددی نامعتبر') from exc
    if not number.is_finite() or len(number.as_tuple().digits) > 60 or abs(number.adjusted()) > 60:
        raise OwnershipError(label + ': دامنه/دقت یا عدد نامتناهی نامعتبر')
    if positive and number <= 0:
        raise OwnershipError(label + ': مقدار مثبت لازم است')
    return number


def _digest(payload):
    """Deterministic JSON content hash; only a version pin, not a signature."""
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         allow_nan=False, separators=(',', ':'), default=_decimal_text).encode('utf-8')
    except (TypeError, ValueError, OverflowError) as exc:
        raise OwnershipError('رکورد پروژه برای محاسبه SHA-256 قابل بازخوانی نیست') from exc
    return sha256(raw).hexdigest()


def _decimal_text(value):
    if isinstance(value, Decimal) and value.is_finite():
        return str(value)
    raise TypeError('JSON value not supported')


def _resolve_target(project, entry):
    register = project.get(_REG)
    if not isinstance(register, dict):
        raise OwnershipError('دفتر واقعی اعضای سازه در Snapshot موجود نیست')
    exact = []
    for record in register.values():
        if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
            raise OwnershipError('ساختار دفتر واقعی اعضای سازه نامعتبر است')
        d = record['data']
        if (d.get('kind'), d.get('floor_id'), d.get('member_id')) == (
            entry['other_kind'], entry['other_floor_id'], entry['other_member_id']
        ):
            exact.append(record)
    if len(exact) != 1:
        raise OwnershipError('عضو کلاهک/ستون متناظر در پروژه یکتا و قابل شناسایی نیست')
    record = exact[0]
    revision = record.get('revision')
    if type(revision) is not int or revision < 1 or revision != entry['other_revision']:
        raise OwnershipError('نسخه واقعی عضو مرتبط با مدرک مشترک یکسان نیست')
    if record.get('status') not in ('draft', 'committed'):
        raise OwnershipError('وضعیت رکورد مرتبط نامعتبر است')
    if _hash(entry['other_record_sha256'], 'هش رکورد مرتبط') != _digest(record):
        raise OwnershipError('رکورد کلاهک/ستون پس از تهیه مدرک مشترک تغییر کرده است')
    d = record['data']
    geometry = d.get('geometry')
    if not isinstance(geometry, dict):
        raise OwnershipError('هندسه عضو مرتبط موجود نیست')
    # Existing member stores may not contain physical identity. Do not guess it
    # from member_id, source_id, position or an unverified filename.
    physical_candidates = [d.get('physical_id'), geometry.get('physical_id'),
                           geometry.get('physical_cap_id') if d['kind'] == 'pile_cap'
                           else geometry.get('physical_column_id')]
    physical = [_canonical(v) for v in physical_candidates if v is not None]
    if not physical or len(set(physical)) != 1 or physical[0] != _canonical(entry['other_physical_id']):
        raise OwnershipError('هویت فیزیکی واقعی کلاهک/ستون در دفتر پروژه احراز نشده است')
    return record


def _count_shared_piece(record, bar_id):
    """Require a single explicit physical bar in the real counterpart record."""
    detail = record.get('data', {})
    rebars = detail.get('rebars')
    if not isinstance(rebars, dict):
        return False
    matches = 0
    for group in rebars.values():
        if not isinstance(group, dict):
            continue
        series = group.get('series', [])
        if not isinstance(series, list):
            continue
        for bar in series:
            if not isinstance(bar, dict):
                continue
            ids = bar.get('bar_piece_ids')
            if not isinstance(ids, list):
                continue
            matches += sum(_canonical(v) == _canonical(bar_id) for v in ids)
    return matches



def _require_independent_joint_reviewer(reviewer, *source_records):
    """Disallow self-review by any preparer/approver in either member's evidence.

    Source author identities are assertions from signed/recorded evidence;
    this check cannot prove a person's real-world identity or authority.
    """
    for source in source_records:
        pending = [source]
        while pending:
            node = pending.pop()
            if isinstance(node, dict):
                for key in ('approved_by', 'prepared_by'):
                    actor = node.get(key)
                    if actor is not None and _canonical(actor) == reviewer:
                        raise OwnershipError('بازبین قرارداد مشترک از تهیه‌کننده یا تأییدکننده مستقل نیست')
                pending.extend(node.values())
            elif isinstance(node, (list, tuple)):
                pending.extend(node)


def audit_joint_contract(data, compiled, ownership_document, ownership_sha256,
                         joint_document, project):
    """Check actual register links and documented deductions, without paying.

    A successful crosswalk is still a preliminary observation. It cannot certify
    that the project ledger or historical bills are globally complete.
    """
    _object(joint_document, _JOINT_KEYS, 'قرارداد مالکیت مشترک')
    if joint_document['policy'] != POLICY:
        raise OwnershipError('نسخه قرارداد مشترک شمع نامعتبر است')
    if not isinstance(project, dict) or project.get('id') != data['project_id']:
        raise OwnershipError('Snapshot واقعی پروژه با ورودی شمع تطابق ندارد')
    for key in ('project_id', 'floor_id', 'group_id'):
        if _id(joint_document[key], key) != _id(data[key], key):
            raise OwnershipError('هویت سند اتصال مشترک با ورودی شمع مغایر است')
    if _hash(joint_document['input_sha256'], 'SHA-256 ورودی') != compiled['source_sha256']:
        raise OwnershipError('مدرک مشترک با نسخه موتور شمع تطابق ندارد')
    if _hash(joint_document['ownership_sha256'], 'SHA-256 مالکیت') != _hash(ownership_sha256, 'SHA-256 مالکیت'):
        raise OwnershipError('مدرک مشترک به نسخه فعلی مالکیت شمع وصل نیست')
    for key in ('coordinate_ref', 'vertical_datum_ref'):
        if _id(joint_document[key], key) != _id(data['datum'][key], key):
            raise OwnershipError('مبنای مختصات/تراز در قرارداد مشترک مغایر است')
    for key in ('prepared_by', 'reviewer'):
        _id(joint_document[key], key)
    prepared = _canonical(joint_document['prepared_by'])
    reviewer = _canonical(joint_document['reviewer'])
    if reviewer == prepared or reviewer == _canonical(ownership_document['reviewer']):
        raise OwnershipError('بازبین قرارداد مشترک مستقل نیست')
    _require_independent_joint_reviewer(reviewer, data, ownership_document)

    preliminary = ownership_audit(data, compiled, ownership_document)
    if preliminary['ready_for_boq'] or preliminary['commit_allowed']:
        raise OwnershipError('ممیزی مقدماتی به اشتباه به پرداخت مجوز داده است')
    allocations = {(a['pile_id'], a['operation'], a['physical_id']): a
                   for a in ownership_document['allocations']}
    piles = {p['id']: p for p in data['piles']}
    links = joint_document['interfaces']
    if not isinstance(links, list):
        raise OwnershipError('جدول ارتباط فیزیکی باید صریح باشد')
    required = set()
    for pile in data['piles']:
        iface = pile['interface']
        for kind, name in (('pile_cap', iface['pile_cap_id']), ('column', iface['column_id'])):
            if name != 'none':
                required.add((pile['id'], kind, name))
    seen = set()
    counterpart = {}
    deductions = {}
    matched_deductions = set()
    audit_links = []
    seen_target_physical = set()
    for entry in links:
        _object(entry, _LINK_KEYS, 'رابط عضو مشترک')
        pile_id = _id(entry['pile_id'], 'شناسه شمع')
        kind = _id(entry['other_kind'], 'نوع عضو')
        other = _id(entry['other_member_id'], 'عضو مرتبط')
        if kind not in _EXTERNAL_KINDS or (pile_id,kind,other) not in required:
            raise OwnershipError('اتصال عضو در دیتایل واقعی شمع وجود ندارد')
        link_key = (pile_id,kind,other)
        if link_key in seen:
            raise OwnershipError('اتصال مشترک عضو تکراری است')
        seen.add(link_key)
        _id(entry['other_floor_id'], 'طبقه عضو مرتبط')
        _id(entry['other_physical_id'], 'هویت فیزیکی مرتبط')
        _id(entry['geometry_reference'], 'مرجع جانمایی مشترک')
        _hash(entry['geometry_sha256'], 'هش جانمایی مشترک')
        status = entry['spatial_status']
        if status not in ('documented_no_overlap', 'documented_deduction'):
            raise OwnershipError('وضعیت مکانی نامعلوم برای تطبیق مشترک کافی نیست')
        record = _resolve_target(project, entry)
        _require_independent_joint_reviewer(reviewer, record)
        target_physical = _canonical(entry['other_physical_id'])
        # The same physical target cannot be relabelled as several members.
        owner_key = (kind, entry['other_floor_id'], other)
        for other_key, physical in seen_target_physical:
            if physical == target_physical and other_key != owner_key:
                raise OwnershipError('یک هویت فیزیکی خارجی به چند عضو متفاوت تخصیص یافته است')
        seen_target_physical.add((owner_key, target_physical))
        counterpart_geometry = record['data']['geometry']
        if (counterpart_geometry.get('source_ref') != entry['geometry_reference'] or
                counterpart_geometry.get('source_sha256') != entry['geometry_sha256']):
            raise OwnershipError('مرجع و هش سند هندسی در رکورد واقعی عضو مرتبط ثبت نشده است')
        otherkey=(kind,entry['other_floor_id'],other)
        counterpart[otherkey]=record
        pile = piles[pile_id]
        top = _num(entry['pile_top_m'],'تراز بالای شمع')
        bottom = _num(entry['pile_bottom_m'],'تراز پایین شمع')
        otop = _num(entry['other_top_m'],'تراز بالای عضو دیگر')
        obottom = _num(entry['other_bottom_m'],'تراز پایین عضو دیگر')
        if top != _num(pile['top_elevation_m'],'تراز دیتایل شمع') or bottom != _num(pile['bottom_elevation_m'],'تراز دیتایل شمع') or top <= bottom or otop <= obottom:
            raise OwnershipError('ترازهای مستند یا جهت هندسی عضو ناسازگارند')
        # Independent target heights must also be bound to the *record*, not
        # merely asserted in the same joint document.
        geometry=record['data'].get('geometry',{})
        if not all(k in geometry for k in ('top_elevation_m','bottom_elevation_m')) or otop!=_num(geometry['top_elevation_m'],'تراز دفتر عضو') or obottom!=_num(geometry['bottom_elevation_m'],'تراز دفتر عضو'):
            raise OwnershipError('تراز واقعی کلاهک/ستون با Snapshot ثبت‌شده تطابق ندارد')
        overlap = min(top,otop)>max(bottom,obottom)
        volume = _num(entry['overlap_volume_m3'],'حجم مشترک')
        deduction = entry['deduction_id']
        if status=='documented_no_overlap':
            # Without authenticated horizontal outlines only disjoint Z ranges
            # conclusively demonstrate a separation; touching is non-overlap.
            if overlap or volume!=0 or deduction!='none' or entry['allocation_owner']!='not_applicable':
                raise OwnershipError('عدم تداخل بدون جدایی تراز و سند معتبر قابل اثبات نیست')
        else:
            if not overlap or volume<=0 or entry['allocation_owner']!='other_member':
                raise OwnershipError('کسر مشترک بدون همپوشانی تراز و تخصیص صریح معتبر نیست')
            did=_id(deduction,'شناسه کسر')
            if did=='none':
                raise OwnershipError('کسر مشترک به شناسه مستقل نیاز دارد')
            claims=[cut for cut in pile['deductions'] if cut['id']==did]
            if len(claims)!=1 or claims[0]['other_physical_id']!=entry['other_physical_id'] or _num(claims[0]['volume_m3'],'حجم کسر موتور')!=volume or claims[0]['owner']!='other_member':
                raise OwnershipError('حجم، هویت یا مالک کسر مشترک با موتور شمع مغایر است')
            if (pile_id,did) in matched_deductions:
                raise OwnershipError('کسر مشترک تکراری است')
            matched_deductions.add((pile_id,did))
        audit_links.append({'pile_id':pile_id,'other_kind':kind,'other_member_id':other,
                            'spatial_status':status,'documented_volume_m3':str(volume),
                            'record_revision':record['revision']})
    if seen!=required:
        raise OwnershipError('اتصالات کلاهک و ستون در Snapshot به‌صورت کامل تطبیق داده نشده‌اند')
    expected_deductions={(pile['id'],cut['id']) for pile in data['piles'] for cut in pile['deductions']}
    if matched_deductions != expected_deductions:
        raise OwnershipError('تمام کسورات شمع باید یک‌به‌یک به عضو مرتبط متصل باشند')
    for pile in data['piles']:
        if pile['interface']['ownership_status']=='documented_no_overlap' and any(k[0]==pile['id'] for k in matched_deductions):
            raise OwnershipError('وضعیت عدم تداخل با کسر ثبت‌شده متناقض است')

    # A pile starter is potentially shared with a cap or column. The ledger
    # requires explicit identity *per bar*, never mass-only or group-only aliases.
    required_bars = set()
    for a in ownership_document['allocations']:
        if a['operation']=='rebar_starters':
            required_bars.update((a['pile_id'], _canonical(piece)) for piece in a['bar_piece_ids'])
    transfer_rows = joint_document['bar_transfers']
    if not isinstance(transfer_rows, list):
        raise OwnershipError('دفتر انتقال میلگرد انتظار باید صریح باشد')
    transferred = set()
    for row in transfer_rows:
        _object(row,_BAR_KEYS,'انتقال میلگرد انتظار')
        pile_id = _id(row['pile_id'],'شناسه شمع')
        bar_id = _canonical(row['bar_piece_id'])
        key = (pile_id,bar_id)
        if key not in required_bars or key in transferred:
            raise OwnershipError('میلگرد انتظار تکراری یا فاقد هویت مستقل است')
        transferred.add(key)
        other_kind = _id(row['other_kind'],'عضو گیرنده')
        if other_kind not in _EXTERNAL_KINDS:
            raise OwnershipError('نوع عضو گیرنده میلگرد نامعتبر است')
        target=(other_kind,_id(row['other_floor_id'],'طبقه عضو'),_id(row['other_member_id'],'شناسه عضو'))
        if target not in counterpart:
            raise OwnershipError('انتقال میلگرد به عضو نامرتبط یا فاقد Snapshot انجام شده است')
        _id(row['other_bar_physical_id'],'هویت میلگرد عضو مرتبط')
        if _count_shared_piece(counterpart[target],row['other_bar_physical_id']) != 1:
            raise OwnershipError('شناسه فیزیکی میلگرد در رکورد طرف مقابل قابل احراز نیست')
        if _canonical(row['other_bar_physical_id']) != bar_id:
            raise OwnershipError('هویت فردی مشترک میلگرد شمع و عضو گیرنده برابر نیست')
        payer = row['payer_kind']
        if payer not in ('pile','other_member'):
            raise OwnershipError('مالک پرداخت میلگرد انتظار نامعلوم است')
        # Match exactly the payer decision in the original ownership record.
        a=next(a for a in ownership_document['allocations'] if a['pile_id']==pile_id and a['operation']=='rebar_starters' and bar_id in [_canonical(v) for v in a['bar_piece_ids']])
        if a['payer_kind']!=payer:
            raise OwnershipError('مالک میلگرد انتظار بین دفتر شمع و انتقال مشترک مغایر است')
        if payer == 'other_member' and _canonical(a['payer_id']) != _canonical(counterpart[target]['data']['geometry'].get('physical_id') or counterpart[target]['data']['geometry'].get('physical_cap_id') or counterpart[target]['data']['geometry'].get('physical_column_id')):
            raise OwnershipError('هویت مالک پرداخت میلگرد با عضو گیرنده تطابق ندارد')
        # A shared bar cannot also be claimed by a third concrete member.
        for record in project.get(_REG, {}).values():
            if record is counterpart[target]:
                continue
            if _count_shared_piece(record, row['other_bar_physical_id']) > 0:
                raise OwnershipError('شناسه میلگرد انتظار در عضو سوم پروژه نیز ثبت شده است')
        _id(row['source_ref'],'مرجع میلگرد مشترک')
        _hash(row['source_sha256'],'هش مدرک میلگرد مشترک')
    if transferred!=required_bars:
        raise OwnershipError('میلگردهای انتظار مشترک فاقد قرارداد یک‌به‌یک هستند')
    blockers = ['مالکیت مشترک فقط پیش‌ممیزی شد؛ قرارداد مالی و کامل‌بودن تمام سوابق تاریخی احراز نشده است',
                'یکپارچگی هش مدارک به معنای اصالت نقشه، امضا یا اختیار پرداخت نیست']
    if project.get('boq') or project.get('takeoffs'):
        blockers.append('سوابق مالی پروژه باید در گیت مستقل و بدون انتقال خاموش بررسی شوند')
    return {'policy':POLICY,'status':'JOINT_CROSSWALK_PREVIEW_ONLY',
            'commit_allowed':False,'ready_for_boq':False, 'rows':[],
            'matched_interfaces':deepcopy(audit_links),'matched_starter_pieces':len(transferred),
            'blockers':blockers}
