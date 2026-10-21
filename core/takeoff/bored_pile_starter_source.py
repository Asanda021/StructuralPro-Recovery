"""Read-only, byte-verified source schedule for individual bored-pile starter bars.

This contract does NOT authenticate an engineer's signature or grant a BOQ
permission. The pile engine currently carries starter series/counts, not bar
identities. This independent, SHA-256-checked source schedule binds each bar
identity to the exact compiled pile input and source series.
"""
from __future__ import annotations

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object,
)

SCHEMA = 'bored_pile_starter_source_v1'
_HEADER = ('schema', 'project_id', 'floor_id', 'group_id', 'input_sha256',
           'coordinate_ref', 'vertical_datum_ref', 'prepared_by', 'reviewer', 'series')
_SERIES = ('pile_id', 'series_physical_id', 'bar_piece_ids',
           'schedule_ref', 'schedule_sha256')


def audit_source(data, compiled, document):
    """Return exact, canonical pile/series/bar IDs, without mutating records."""
    _object(document, _HEADER, 'مدرک منشأ میلگردهای انتظار شمع')
    if document['schema'] != SCHEMA:
        raise OwnershipError('نسخه مدرک منشأ میلگرد انتظار معتبر نیست')
    for key in ('project_id', 'floor_id', 'group_id'):
        if _id(document[key], key) != _id(data[key], key):
            raise OwnershipError('هویت مدرک منشأ با ورودی واقعی شمع مغایر است')
    if _hash(document['input_sha256'], 'هش ورودی شمع') != _hash(compiled['source_sha256'], 'هش موتور'):
        raise OwnershipError('مدرک منشأ میلگرد انتظار به ورودی موتور جاری تعلق ندارد')
    for key in ('coordinate_ref', 'vertical_datum_ref'):
        if _id(document[key], key) != _id(data['datum'][key], key):
            raise OwnershipError('مبنای هندسی منشأ میلگرد انتظار ناسازگار است')
    author = _canonical(document['prepared_by'])
    reviewer = _canonical(document['reviewer'])
    if author == reviewer:
        raise OwnershipError('بازبین مدرک منشأ باید مستقل از تهیه‌کننده باشد')
    if not isinstance(document['series'], list) or len(document['series']) > 512:
        raise OwnershipError('فهرست سری‌های منشأ میلگرد انتظار معتبر نیست')

    # These series are present in the *actual* pile input, not in an ownership
    # allocation or a receiving-member assertion.
    required = {}
    for pile in data['piles']:
        pid = _canonical(pile['id'])
        group = pile['rebars']['starters']
        if group['status'] == 'not_applicable':
            if group.get('series') not in (None, []):
                raise OwnershipError('میلگرد انتظار غیرقابل‌کاربرد دارای سری است')
            continue
        if group['status'] != 'confirmed' or not isinstance(group.get('series'), list):
            raise OwnershipError('سری میلگرد انتظار از ورودی واقعی شمع قابل تأیید نیست')
        for bar in group['series']:
            sid = _canonical(bar['physical_id'])
            key = (pid, sid)
            if key in required:
                raise OwnershipError('سری فیزیکی انتظار در ورودی شمع تکراری است')
            count = bar['count']
            if isinstance(count, (float, bool)) or not isinstance(count, (str, int)):
                raise OwnershipError('تعداد میلگرد انتظار باید عدد صحیح و مستند باشد')
            try:
                value = int(count)
            except (ValueError, OverflowError) as exc:
                raise OwnershipError('تعداد میلگرد انتظار نامعتبر است') from exc
            if value < 1 or str(value) != str(count) or value > 4096:
                raise OwnershipError('تعداد صحیح و محدود میلگرد انتظار لازم است')
            required[key] = value

    actual = {}
    source_bars = set()
    series_to_schedule = {}
    for row in document['series']:
        _object(row, _SERIES, 'سری مستقل منشأ میلگرد انتظار')
        pid, sid = (_canonical(_id(row['pile_id'], 'شناسه شمع')),
                    _canonical(_id(row['series_physical_id'], 'سری فیزیکی')))
        key = (pid, sid)
        if key not in required or key in actual:
            raise OwnershipError('سری میلگرد منشأ ناشناخته یا تکراری است')
        _id(row['schedule_ref'], 'مرجع مدرک برش میلگرد')
        schedule_hash = _hash(row['schedule_sha256'], 'هش فهرست منشأ میلگرد')
        ids = row['bar_piece_ids']
        if not isinstance(ids, list) or len(ids) != required[key]:
            raise OwnershipError('تعداد شناسه‌های فردی با ورودی موتور شمع برابر نیست')
        canonical = []
        for ident in ids:
            cid = _canonical(_id(ident, 'شناسه فردی میلگرد شمع'))
            if '|' in cid or (pid, cid) in source_bars:
                raise OwnershipError('شناسه فردی میلگرد شمع مبهم یا تکراری است')
            source_bars.add((pid, cid))
            canonical.append(cid)
        actual[key] = tuple(canonical)
        series_to_schedule[key] = schedule_hash
    if actual.keys() != required.keys():
        raise OwnershipError('تمام سری‌های واقعی میلگرد انتظار باید منشأ فردی مستقل داشته باشند')
    # The same physical ID must not be assigned to two piles in this project.
    if len({bar_id for _, bar_id in source_bars}) != len(source_bars):
        raise OwnershipError('یک میلگرد فیزیکی به دو شمع مختلف اختصاص یافته است')
    return {'schema': SCHEMA, 'source_bar_keys': frozenset(source_bars),
            'series_bars': actual, 'series_schedule_sha256': series_to_schedule,
            'status': 'SOURCE_IDENTITY_PREVIEW_ONLY', 'commit_allowed': False,
            'ready_for_boq': False, 'rows': []}
