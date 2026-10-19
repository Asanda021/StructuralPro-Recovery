"""Phase 1: read-only, source-bound prism *envelope* overlap reconciliation.

This is not a concrete solid model: openings, holes, material attribution,
reinforcement and formwork cannot be deduced from an enclosing rectangular box.
No financial deductions or registration are produced, even when geometry matches.
"""
from __future__ import annotations

from decimal import Context, Decimal, localcontext
from itertools import combinations

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_beam_panel import _member_prism

POLICY = 'phase1_prism_envelope_collision_v1'
_HEADER = ('policy', 'project_id', 'coordinate_ref', 'vertical_datum_ref',
           'detail_ref', 'prepared_by', 'reviewer', 'geometry_scope',
           'ownership_status', 'links', 'pair_claims', 'triple_claim_m3')
_LINK = ('role', 'kind', 'floor_id', 'member_id', 'physical_id',
         'record_revision', 'record_sha256')
_PAIR = ('roles', 'envelope_intersection_m3')
_KINDS = frozenset(('column','beam','tie_beam','pile_cap','isolated_footing',
                    'strip_footing','mat_footing'))


def _volume(box):
    with localcontext(Context(prec=1024, Emax=999999, Emin=-999999)):
        value = Decimal(1)
        for i in range(3):
            side = box[i+3] - box[i]
            if side <= 0:
                return Decimal(0)
            value *= side
        return value


def _overlap(*boxes):
    low = tuple(max(box[i] for box in boxes) for i in range(3))
    high = tuple(min(box[i+3] for box in boxes) for i in range(3))
    if any(high[i] <= low[i] for i in range(3)):
        return Decimal(0)
    return _volume(low + high)


def _check_aliases(project, recorded, physicals):
    # Using an external third record with the same real identity invalidates the
    # whole cluster: a source-bound geometry hash is not an allocation decision.
    for name in ('reviewed_structural_members', 'beam_detail_register'):
        records = project.get(name, {})
        if not isinstance(records, dict):
            raise OwnershipError('دفتر اعضای سازه‌ای نامعتبر است')
        for record in records.values():
            if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
                raise OwnershipError('عضو ساختار معتبر ندارد')
            data = record['data']; g = data.get('geometry', {})
            if not isinstance(g, dict):
                continue
            candidates = (data.get('physical_id'), g.get('physical_id'),
                          g.get('physical_cap_id'), g.get('physical_column_id'))
            matched = {_canonical(x) for x in candidates if x is not None} & physicals
            if matched and not any(record is r for r in recorded):
                raise OwnershipError('هویت فیزیکی عضو در Snapshot دیگری نیز استفاده شده است')


def preview(document, project):
    """Audit 2 or 3 source-pinned, versioned prisms. No database writes."""
    _object(document, _HEADER, 'ممیزی هندسه مشترک اعضا')
    if document['policy'] != POLICY:
        raise OwnershipError('نسخه قرارداد هم‌پوشانی منشوری ناشناخته است')
    if not isinstance(project, dict) or _id(document['project_id'], 'پروژه') != _id(project.get('id'), 'پروژه'):
        raise OwnershipError('شناسه پروژه با سند هم‌پوشانی مغایر است')
    for name in ('coordinate_ref','vertical_datum_ref','detail_ref','prepared_by','reviewer'):
        _id(document[name], name)
    if _canonical(document['prepared_by']) == _canonical(document['reviewer']):
        raise OwnershipError('بازبین مستقل هندسه لازم است')
    if document['geometry_scope'] != 'bounding_envelopes_only' or document['ownership_status'] != 'unresolved':
        raise OwnershipError('این ممیزی اجازه ادعای حجم بتن خالص یا مالکیت مالی را ندارد')
    links = document['links']
    if not isinstance(links, list) or len(links) not in (2, 3):
        raise OwnershipError('دو یا سه عضو واقعی با مدارک مستقل لازم است')
    roles = {}; physicals = set(); records = []
    for link in links:
        _object(link, _LINK, 'عضو مرتبط')
        role = _id(link['role'], 'نقش عضو')
        kind = _id(link['kind'], 'خانواده عضو')
        if role in roles or role not in ('column', 'counterpart', 'third') or kind not in _KINDS:
            raise OwnershipError('نقش تکراری یا خانواده خارج از محدوده منشور مستند است')
        for field in ('floor_id','member_id','physical_id'):
            _id(link[field], field)
        physical = _canonical(link['physical_id'])
        if physical in physicals:
            raise OwnershipError('شناسه فیزیکی دو عضو یکسان است')
        physicals.add(physical)
        box, record = _member_prism(project, link, document)
        if record.get('status') not in ('draft','committed'):
            raise OwnershipError('وضعیت عضو تأییدنشده است')
        reviewer = record['data'].get('source', {}).get('approved_by')
        if reviewer and _canonical(reviewer) == _canonical(document['reviewer']):
            raise OwnershipError('بازبین سند نباید تأییدکننده منبع عضو باشد')
        roles[role] = box
        records.append(record)
    if 'column' not in roles or 'counterpart' not in roles or (len(roles) == 3) != ('third' in roles):
        raise OwnershipError('دو نقش اصلی و نقش سوم اختیاری باید کامل باشند')
    _check_aliases(project, records, physicals)
    expected = {tuple(sorted(pair)):_overlap(roles[pair[0]],roles[pair[1]])
                for pair in combinations(roles, 2)}
    claims = document['pair_claims']
    if not isinstance(claims, list) or len(claims) != len(expected):
        raise OwnershipError('همه تقاطع‌های دوتایی باید صریح و یکتا مستند شوند')
    claimed = {}
    for entry in claims:
        _object(entry, _PAIR, 'ادعای تقاطع دو عضو')
        pair = entry['roles']
        if not isinstance(pair, list) or len(pair) != 2 or any(type(x) is not str for x in pair):
            raise OwnershipError('دو نقش صریح برای تقاطع لازم است')
        key = tuple(sorted(pair))
        if pair[0] == pair[1] or key not in expected or key in claimed:
            raise OwnershipError('تقاطع مفقود، تکراری یا متعلق به عضو دیگر است')
        amount = _num(entry['envelope_intersection_m3'], 'حجم پاکت مشترک')
        if amount < 0 or amount != expected[key]:
            raise OwnershipError('حجم ادعایی با هندسه منشورهای نسخه‌دار متفاوت است')
        claimed[key] = amount
    if set(claimed) != set(expected):
        raise OwnershipError('تمام تقاطع‌های ممکن مستند نشده‌اند')
    triple = _overlap(*roles.values()) if len(roles) == 3 else Decimal(0)
    triple_claim = _num(document['triple_claim_m3'], 'هم‌پوشانی سه‌طرفه')
    if triple_claim < 0 or triple_claim != triple:
        raise OwnershipError('هم‌پوشانی سه‌طرفه جداگانه با هندسه مطابقت ندارد')
    # Inclusion-exclusion prevents double counting *geometric envelope* volume,
    # not concrete. Do not interpret this as a material/net/BOQ quantity.
    with localcontext(Context(prec=1024, Emax=999999, Emin=-999999)):
        union_envelopes = sum((_volume(b) for b in roles.values()), Decimal(0)) - sum(claimed.values(), Decimal(0)) + triple
    return {'policy': POLICY, 'status': 'ENVELOPE_COLLISION_PREVIEW_ONLY',
            'envelope_scope': 'bounding_envelopes_only',
            'member_count': len(roles),
            'pair_intersections': [{'roles': list(key), 'envelope_intersection_m3': format(value,'f')}
                                   for key, value in sorted(expected.items())],
            'triple_intersection_m3': format(triple, 'f'),
            'union_envelope_m3': format(union_envelopes, 'f'),
            'material_deduction_m3': None,
            'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
            'blockers': ['این حجم‌ها تقاطع پاکت هندسی‌اند؛ وجود بتن توپر، بازشوها و کسورات واقعی اثبات نشده است',
                         'مالکیت بتن، قالب، میلگرد و حجم قابل پرداخت مستقل از هندسه باید تأیید شود',
                         'SHA-256 اصالت نقشه یا اختیار بازبین مهندس را اثبات نمی‌کند']}


def preview_file(project, path, sha256):
    """No cached evidence: recheck actual file bytes on each invocation."""
    return preview(read_evidence(path, _hash(sha256, 'SHA-256 مدرک هندسه')), project)
