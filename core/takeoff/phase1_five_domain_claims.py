"""Fail-closed read-only component identity crosswalk across five Phase-1 domains.

This audits ONLY rows represented by the currently stored reviewed AEC record.
It is not a new takeoff formula, payable quantity, designer approval or a
complete physical inventory for specialist modules / historical ledgers.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from decimal import Decimal

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _digest, _num
from core.takeoff.engine import TakeoffEngine
from core.takeoff.reviewed_aec import (
    ELECTRICAL_SYSTEMS, MECHANICAL_SYSTEMS, CIVIL_SYSTEMS, SPECS,
    preview_system, _id as aec_key,
)

POLICY = 'phase1_five_domain_physical_claims_v1'
DOMAINS = {
    'steel_composite': frozenset(('steel_frame', 'composite_frame', 'steel_deck')),
    'timber_special_roofs': frozenset(('timber_frame', 'kromit_roof', 'composite_roof',
                                     'sandwich_roof', 'timber_roof', 'precast_roof')),
    'architecture_finishes': frozenset(('stone_cladding', 'facade_cladding',
                                        'gypsum_partition', 'door_window',
                                        'upvc_aluminium_windows', 'thermal_insulation',
                                        'acoustic_insulation', 'cement_render')),
    'mep': MECHANICAL_SYSTEMS | ELECTRICAL_SYSTEMS,
    'site_renovation': CIVIL_SYSTEMS | frozenset(('demolition', 'concrete_repair',
                                                 'seismic_retrofit', 'historic_restoration')),
}
_HEADER = ('policy','project_id','prepared_by','reviewer','coverage','claims')
_CLAIM = ('scope','kind','floor_id','system_id','component','line_id',
          'physical_component_id','record_revision','record_sha256',
          'quantity','unit','source_ref','measurement_ref','evidence_ref')


def _physical_inventory(project):
    """Detect explicit identities in all generic stored AEC component rows.

    Specialist records whose pieces do not use this representation are NOT
    presumed absent from physical inventory; this is a limited crosswalk.
    """
    records = project.get('reviewed_aec_systems', {})
    if not isinstance(records, dict):
        raise OwnershipError('دفتر سیستم‌های AEC موجود نیست')
    found = {}
    unindexed = []
    for key, record in records.items():
        if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
            raise OwnershipError('رکورد سیستم دارای ساختار نامعتبر است')
        data = record['data']
        components = data.get('components')
        if not isinstance(components, dict):
            raise OwnershipError('رکورد سیستم فاقد فهرست مصالح معتبر است')
        for name, group in components.items():
            if not isinstance(group, dict):
                raise OwnershipError('گروه مصالح فاقد ساختار معتبر است')
            items = group.get('items', [])
            if not isinstance(items, list):
                raise OwnershipError('لیست قطعات سیستم نامعتبر است')
            if group.get('status') == 'confirmed' and not items:
                unindexed.append((key, name))
            for item in items:
                if not isinstance(item, dict):
                    raise OwnershipError('ریزقلم سیستم نامعتبر است')
                pid = item.get('physical_component_id')
                if pid is None:
                    unindexed.append((key, name))
                    continue
                normalized = _canonical(_id(pid, 'هویت فیزیکی قطعه'))
                coordinate = (key, name, item.get('line_id'))
                if normalized in found:
                    raise OwnershipError('شناسه فیزیکی قطعه در دو ریزقلم AEC تکرار شده است')
                found[normalized] = coordinate
    return records, found, unindexed


def audit(project, evidence):
    """Validate selected stored component claims across all five domain classes.

    Do not treat missing claims as zero or proof of a complete material schedule.
    All AEC preview computations are delegated to the *existing* engine.
    """
    _object(evidence, _HEADER, 'سند ممیزی پنج حوزه فاز یک')
    if evidence['policy'] != POLICY:
        raise OwnershipError('نسخه ممیزی پنج حوزه معتبر نیست')
    if not isinstance(project, dict) or _id(project.get('id'), 'پروژه') != _id(evidence['project_id'], 'پروژه'):
        raise OwnershipError('شناسه پروژه با سند ادعا برابر نیست')
    for key in ('prepared_by', 'reviewer'):
        _id(evidence[key], key)
    if _canonical(evidence['prepared_by']) == _canonical(evidence['reviewer']):
        raise OwnershipError('ممیزی باید بازبین مستقل داشته باشد')
    if evidence['coverage'] != 'selected_registered_items_only':
        raise OwnershipError('ادعای کامل بودن همه خانواده‌ها یا همه قطعات ممنوع است')
    claims = evidence['claims']
    if not isinstance(claims, list) or not 1 <= len(claims) <= 512:
        raise OwnershipError('فهرست محدود و صریح قطعات لازم است')
    records, identities, unindexed = _physical_inventory(project)
    seen = set(); covered = set(); observations = []
    checked_records = {}
    for claim in claims:
        _object(claim, _CLAIM, 'ادعای قطعه فیزیکی')
        for key in ('scope','kind','floor_id','system_id','component','line_id',
                    'physical_component_id','unit','source_ref','measurement_ref','evidence_ref'):
            _id(claim[key], key)
        scope = claim['scope']; kind = claim['kind']
        if scope not in DOMAINS or kind not in DOMAINS[scope] or kind not in SPECS:
            raise OwnershipError('حوزه و خانواده قطعه فیزیکی ناسازگارند')
        if claim['component'] not in SPECS[kind].components:
            raise OwnershipError('جزء انتخاب‌شده در خانواده تعریف نشده است')
        record_key = aec_key(kind, claim['floor_id'], claim['system_id'])
        record = records.get(record_key)
        if not isinstance(record, dict) or not isinstance(record.get('data'), dict):
            raise OwnershipError('رکورد نسخه‌دار واقعی خانواده پیدا نشد')
        if (type(claim['record_revision']) is not int or claim['record_revision'] <= 0 or
                claim['record_revision'] != record.get('revision') or
                _hash(claim['record_sha256'], 'هش Snapshot') != _digest(record)):
            raise OwnershipError('نسخه یا محتوای رکورد پس از ایجاد ادعای قطعه تغییر کرده است')
        if record.get('status') not in ('draft','committed'):
            raise OwnershipError('وضعیت رکورد معتبر نیست')
        data = record['data']
        if (data.get('kind'), data.get('floor_id'), data.get('system_id')) != (
                kind, claim['floor_id'], claim['system_id']):
            raise OwnershipError('کلید رکورد و هویت داخل آن یکسان نیستند')
        if record_key not in checked_records:
            result = preview_system(data, TakeoffEngine())
            if not result['ready'] or result['blockers']:
                raise OwnershipError('متره فعلی جزء انتخاب‌شده تأیید جزئی و قابل محاسبه ندارد')
            checked_records[record_key] = result
        part = data['components'][claim['component']]
        if not isinstance(part, dict) or part.get('status') != 'confirmed':
            raise OwnershipError('گروه جزء در سیستم ثبت‌شده تأیید نشده است')
        items = part.get('items')
        if not isinstance(items, list):
            raise OwnershipError('قطعات ثبت‌شده گروه نامعتبرند')
        candidates = [x for x in items if isinstance(x, dict) and x.get('line_id') == claim['line_id']]
        if len(candidates) != 1:
            raise OwnershipError('ریزقلم قطعه در سیستم یکتا نیست')
        item = candidates[0]
        physical = _canonical(claim['physical_component_id'])
        if (item.get('physical_component_id') != claim['physical_component_id'] or
                identities.get(physical) != (record_key, claim['component'], claim['line_id'])):
            raise OwnershipError('ادعای هویت فیزیکی به ریزقلم ذخیره‌شده متصل نیست')
        if item.get('mode') != 'measured':
            raise OwnershipError('این نسخه فقط ریزمقادیر اندازه‌گیری‌شده و دارای مدرک را بررسی می‌کند')
        if (item.get('source_ref') != claim['source_ref'] or
                item.get('measurement_ref') != claim['measurement_ref']):
            raise OwnershipError('منبع یا جدول اندازه‌گیری با ریزقلم نسخه‌دار برابر نیست')
        matching = [r for r in checked_records[record_key]['rows']
                    if r.get('component') == claim['component'] and r.get('line_id') == claim['line_id']]
        if len(matching) != 1:
            raise OwnershipError('ریزقلم در پیش‌نمایش واقعی سیستم یکتا نیست')
        row = matching[0]
        if row['unit'] != claim['unit'] or _num(claim['quantity'], 'مقدار ادعایی', positive=True) != Decimal(str(row['quantity'])):
            raise OwnershipError('مقدار یا واحد با موتور متره AEC برابر نیست')
        key = (record_key, claim['component'], claim['line_id'])
        if key in seen:
            raise OwnershipError('یک قطعه بیش از یک بار در سند پنج حوزه ادعا شده است')
        seen.add(key);covered.add(scope)
        observations.append({'scope':scope, 'kind':kind, 'component':claim['component'],
                             'physical_component_id':claim['physical_component_id'],
                             'unit':claim['unit'], 'measured_quantity':claim['quantity']})
    blockers = ['این سند فقط ریزاقلام منتخب را کنترل می‌کند؛ تمام خانواده‌ها، نقشه‌ها و اقلام بدون شناسه پوشش ندارند',
                'مدارک می‌توانند هویت ساختاری صحیح و مقدار یکسان داشته باشند بدون آنکه اصالت نقشه یا اجازه پرداخت احراز شود']
    if unindexed:
        blockers.append(f'{len(unindexed)} ریزقلم فاقد شناسه فیزیکی در دفترهای بررسی‌شده وجود دارد؛ عدم تکرار سراسری اثبات نشده است')
    if project.get('takeoffs') or project.get('boq'):
        blockers.append('تطبیق ردیف‌های تاریخی دفتر مالی مستقل از این ممیزی لازم است')
    if set(covered) != set(DOMAINS):
        blockers.append('بخشی از پنج حوزه هنوز سند و قطعه فیزیکی ممیزی‌شده ندارد')
    return {'policy':POLICY,'status':'FIVE_DOMAINS_CLAIM_PREVIEW_ONLY',
            'covered_scopes':sorted(covered),'selected_claim_count':len(observations),
            'observations':deepcopy(observations), 'blockers':blockers,
            'ready_for_boq':False,'commit_allowed':False,'rows':[]}


def audit_file(project, path, sha256):
    """Check physical JSON bytes with SHA-256 before opening any claims."""
    return audit(project, read_evidence(path, _hash(sha256, 'هش سند ممیزی')))
