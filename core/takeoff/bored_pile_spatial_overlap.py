"""Source-bound *read-only* cylinder/box overlap audit for bored piles.

This optional phase-one audit does not modify the original joint policy, SQLite,
member revisions, payment decisions or historical documents. It handles only
provable containment or disjointness; partial circular segments fail closed.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_specialist_chat import PI, exact
from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _object, _id, _hash, _canonical, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import (
    audit_joint_contract, _digest, _num, _resolve_target,
    _require_independent_joint_reviewer,
)

POLICY = 'bored_pile_spatial_overlap_v1'
_HEADER = ('policy', 'project_id', 'floor_id', 'group_id', 'input_sha256',
           'coordinate_ref', 'vertical_datum_ref', 'prepared_by', 'reviewer', 'links')
_LINK = ('pile_id', 'pile_physical_id', 'other_kind', 'other_floor_id',
         'other_member_id', 'other_physical_id', 'other_record_sha256',
         'other_revision', 'pile_center_x_m', 'pile_center_y_m',
         'other_x_min_m', 'other_y_min_m', 'other_x_max_m', 'other_y_max_m',
         'other_top_m', 'other_bottom_m', 'geometry_reference',
         'geometry_sha256', 'deduction_id')


def _xy(entry, label):
    return _num(entry, label)


def cylinder_box_overlap(pile, *, center_x_m, center_y_m, box_x_min_m,
                         box_y_min_m, box_x_max_m, box_y_max_m,
                         box_top_m, box_bottom_m):
    """Return exact-Decimal model quantity for a provable 3-D intersection.

    PI is the documented finite 50-digit constant used by the pile engine,
    not a claim of an exact irrational mathematical pi.
    """
    with localcontext(Context(prec=256, Emin=-999999, Emax=999999)):
        diameter = _num(pile['diameter_m'], 'قطر شمع', positive=True)
        top = _num(pile['top_elevation_m'], 'تراز بالای شمع')
        bottom = _num(pile['bottom_elevation_m'], 'تراز پایین شمع')
        other_top = _num(box_top_m, 'تراز بالای عضو مرتبط')
        other_bottom = _num(box_bottom_m, 'تراز پایین عضو مرتبط')
        cx, cy = _xy(center_x_m, 'مرکز X'), _xy(center_y_m, 'مرکز Y')
        left = _xy(box_x_min_m, 'مرز چپ')
        low = _xy(box_y_min_m, 'مرز پایین')
        right = _xy(box_x_max_m, 'مرز راست')
        high = _xy(box_y_max_m, 'مرز بالا')
        if top <= bottom or other_top <= other_bottom or right <= left or high <= low:
            raise OwnershipError('جهت، تراز یا ابعاد هندسه سه‌بعدی نامعتبر است')
        z_length = min(top, other_top) - max(bottom, other_bottom)
        if z_length <= 0:
            return {'horizontal_case': 'z_disjoint', 'overlap_volume_m3': '0',
                    'overlap_height_m': '0', 'area_m2': '0'}
        radius = diameter / Decimal(2)
        radius_sq = radius * radius
        # No circular-to-rectangular approximation permitted. Whole circular
        # area is valid only when ALL of it lies inside the rectangular prism.
        if (left <= cx-radius and cx+radius <= right and
                low <= cy-radius and cy+radius <= high):
            case, area = 'cylinder_inside_box', PI * radius_sq
        else:
            nearest_x = min(max(cx, left), right)
            nearest_y = min(max(cy, low), high)
            if ((nearest_x-cx)**2+(nearest_y-cy)**2) >= radius_sq:
                case, area = 'xy_disjoint', Decimal(0)
            elif all((x-cx)**2+(y-cy)**2 <= radius_sq
                     for x in (left,right) for y in (low,high)):
                case, area = 'box_inside_cylinder', (right-left)*(high-low)
            else:
                raise OwnershipError('تقاطع جزئی دایره و مستطیل بدون انتگرال هندسی مستند مسدود است')
        return {'horizontal_case': case, 'overlap_volume_m3': exact(area*z_length),
                'overlap_height_m': exact(z_length), 'area_m2': exact(area)}


def audit_spatial_overlap(data, compiled, ownership_document, ownership_sha256,
                          joint_document, project, *, evidence_path, evidence_sha256):
    """Re-audit the actual joint register, then reconcile independently computed volumes.

    The separate spatial document's SHA proves file integrity, not authorship,
    accuracy of the geometry, completeness of signed drawings or BOQ rights.
    """
    # Re-check all existing link and starter evidence against actual register.
    linked = audit_joint_contract(data, compiled, ownership_document,
                                  ownership_sha256, joint_document, project)
    if linked['commit_allowed'] or linked['ready_for_boq'] or linked['rows']:
        raise OwnershipError('ممیزی مالکیت مشترک به‌اشتباه مجوز پرداخت صادر کرده است')
    proof = read_evidence(evidence_path, evidence_sha256)
    _object(proof, _HEADER, 'مدرک سه‌بعدی')
    if proof['policy'] != POLICY:
        raise OwnershipError('نسخه مدرک سه‌بعدی نادرست است')
    for key in ('project_id', 'floor_id', 'group_id'):
        if _id(proof[key], key) != _id(data[key], key):
            raise OwnershipError('هویت مدرک سه‌بعدی با گروه شمع متفاوت است')
    if _hash(proof['input_sha256'], 'ورودی شمع') != _hash(compiled['source_sha256'], 'ورودی موتور'):
        raise OwnershipError('مدرک سه‌بعدی به نسخه جاری ورودی شمع متصل نیست')
    for key in ('coordinate_ref','vertical_datum_ref'):
        if _id(proof[key], key) != _id(data['datum'][key], key):
            raise OwnershipError('دستگاه مختصات یا تراز مدرک سه‌بعدی یکسان نیست')
    preparer = _canonical(proof['prepared_by'])
    reviewer = _canonical(proof['reviewer'])
    if preparer == reviewer or reviewer == _canonical(joint_document['reviewer']):
        raise OwnershipError('بازبین مستقل مدرک سه‌بعدی لازم است')
    _require_independent_joint_reviewer(reviewer, data, ownership_document,
                                        joint_document)
    links = proof['links']
    if not isinstance(links, list) or len(links) > 512:
        raise OwnershipError('فهرست رابط‌های سه‌بعدی محدود و صریح لازم است')
    expected = {}
    for record in joint_document['interfaces']:
        key = (record['pile_id'],record['other_kind'],record['other_floor_id'],record['other_member_id'])
        if key in expected:
            raise OwnershipError('رابط تکراری در سند مشترک')
        expected[key] = record
    piles = {p['id']: p for p in data['piles']}
    seen = set()
    intervals = {}
    verified = []
    unbound = []
    for item in links:
        _object(item, _LINK, 'رابط سه‌بعدی')
        key=(item['pile_id'], item['other_kind'],item['other_floor_id'],item['other_member_id'])
        if key in seen or key not in expected:
            raise OwnershipError('رابط سه‌بعدی مفقود، تکراری یا بدون عضو واقعی است')
        seen.add(key)
        link = expected[key]
        pile = piles[item['pile_id']]
        if _canonical(item['pile_physical_id']) != _canonical(pile['physical_id']):
            raise OwnershipError('هویت فیزیکی شمع مغایر است')
        for field in ('other_physical_id','other_record_sha256','other_revision',
                      'other_top_m','other_bottom_m','geometry_reference',
                      'geometry_sha256','deduction_id'):
            if field == 'other_revision':
                if type(item[field]) is not int or item[field] != link[field]:
                    raise OwnershipError('نسخه مرتبط با Snapshot متفاوت است')
            elif field in ('other_top_m','other_bottom_m'):
                if _num(item[field],field)!=_num(link[field],field):
                    raise OwnershipError('تراز مرتبط با Snapshot متفاوت است')
            elif item[field] != link[field]:
                raise OwnershipError('مرجع هندسی یا هویت قرارداد مشترک متفاوت است')
        record = _resolve_target(project, link)
        if _digest(record) != item['other_record_sha256']:
            raise OwnershipError('رکورد مرتبط پس از تهیه مدرک سه‌بعدی تغییر کرده است')
        _require_independent_joint_reviewer(reviewer, record)
        from core.takeoff.bored_pile_counterpart_footprint import verify_record_bound
        bounded = verify_record_bound(
            record, project_id=data['project_id'], link=link, spatial_item=item,
            coordinate_ref=data['datum']['coordinate_ref'],
            vertical_datum_ref=data['datum']['vertical_datum_ref'])
        if not bounded:
            unbound.append(key)
        result = cylinder_box_overlap(
            pile, center_x_m=item['pile_center_x_m'],
            center_y_m=item['pile_center_y_m'],box_x_min_m=item['other_x_min_m'],
            box_y_min_m=item['other_y_min_m'],box_x_max_m=item['other_x_max_m'],
            box_y_max_m=item['other_y_max_m'],box_top_m=item['other_top_m'],
            box_bottom_m=item['other_bottom_m'])
        calculated = Decimal(result['overlap_volume_m3'])
        if calculated != _num(link['overlap_volume_m3'],'حجم دفتر مشترک'):
            raise OwnershipError('حجم هندسی محاسبه‌شده با کسر مستند دفتر مشترک برابر نیست')
        if calculated:
            if link['spatial_status'] != 'documented_deduction':
                raise OwnershipError('حجم مثبت فاقد وضعیت کسر مستند است')
            z0=max(_num(pile['bottom_elevation_m'],'پایین شمع'), _num(item['other_bottom_m'],'پایین عضو'))
            z1=min(_num(pile['top_elevation_m'],'بالای شمع'), _num(item['other_top_m'],'بالای عضو'))
            # Prevent triple physical claims even if XY might be disjoint;
            # this conservative filter can intentionally reject valid layouts.
            for prior_bottom,prior_top in intervals.get(item['pile_id'],[]):
                if min(z1,prior_top) > max(z0,prior_bottom):
                    raise OwnershipError('کسرهای کلاهک و ستون هم‌پوشانی عمودی دارند؛ تداخل سه‌طرفه حل نشده است')
            intervals.setdefault(item['pile_id'],[]).append((z0,z1))
        else:
            if link['spatial_status'] != 'documented_no_overlap':
                raise OwnershipError('عدم تداخل هندسی و وضعیت دفتر مشترک متناقض‌اند')
        verified.append({'pile_id': item['pile_id'], 'other_kind':item['other_kind'],
                         'other_member_id':item['other_member_id'], **result})
    if seen != set(expected):
        raise OwnershipError('برای تمام رابط‌های واقعی مدرک سه‌بعدی ارائه نشده است')
    return {'policy': POLICY,'status':'SPATIAL_PREVIEW_ONLY','ready_for_boq':False,
            'commit_allowed':False,'rows':[],'matched_interfaces':deepcopy(verified),
            'counterpart_geometry_record_bound':not unbound,
            'unbound_counterpart_count':len(unbound),
            'blockers':([
                'بررسی هندسی مستقل فقط برای هندسه ساده و مستند؛ اصالت هندسه و نقشه تأیید نشده است',
                'ممیزی حجم، مالکیت مالی یا تعارض همه رکوردهای تاریخی را آزاد نمی‌کند',
            ] + (['مرز افقی عضو مقابل در رکورد نسخه‌دار و سند مستقل احراز نشده است']
                 if unbound else []))}
