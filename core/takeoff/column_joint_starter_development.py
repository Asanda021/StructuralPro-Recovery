"""Source-bound starter anchorage *evidence preflight*, not a design verifier.

The first-stage face-contact contract permits only straight centerlines.  This
module compares separately measured embedments and transverse clearances with
an independent immutable designer worksheet.  Hooks and curved bends fail
closed until a versioned shape/arc-length source is independently supported.
No database/BOQ mutation, ownership transfer, or structural-code acceptance.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _canonical, _hash, _id, _object, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_footing_tie import (
    _face, _member_prism, _position, preview as contact_preview,
)

POLICY = 'column_joint_starter_anchorage_evidence_v1'
CALC_POLICY = 'column_joint_starter_designer_worksheet_v1'
_POINTER = ('path', 'sha256', 'reference')
_HEADER = ('policy', 'project_id', 'joint_id', 'contact_document', 'prepared_by',
           'reviewer', 'starter_checks')
_CHECK = ('physical_bar_id', 'diameter_mm', 'provided_counterpart_m',
          'provided_column_m', 'transverse_clearance_m', 'worksheet_document')
_SHEET = ('policy', 'project_id', 'joint_id', 'physical_bar_id', 'diameter_mm',
          'required_counterpart_m', 'required_column_m', 'required_clear_cover_m',
          'design_code_ref', 'calculation_ref', 'designer', 'independent_reviewer',
          'bend_status', 'bend_detail_ref', 'bend_radius_mm', 'bend_angle_deg')


def _file_pointer(pointer, label):
    _object(pointer, _POINTER, label)
    _id(pointer['reference'], 'مرجع '+label)
    return read_evidence(_id(pointer['path'], 'مسیر '+label),
                         _hash(pointer['sha256'], 'هش '+label))


def _bar_part(record, bar):
    groups = record.get('data', {}).get('rebars')
    if not isinstance(groups, dict):
        raise OwnershipError('دفتر میلگرد واقعی عضو مالک وجود ندارد')
    group = groups.get(bar['group_key'])
    if not isinstance(group, dict) or not isinstance(group.get('segments'), list):
        raise OwnershipError('گروه میلگرد انتظار عضو مالک ثبت نشده است')
    matches = [part for part in group['segments'] if isinstance(part, dict)
               and part.get('id') == bar['record_piece_id']
               and part.get('physical_id') == bar['physical_bar_id']]
    if len(matches) != 1:
        raise OwnershipError('قطعه انتظار در دفتر مالک یکتا نیست')
    part = matches[0]
    diameter = _num(part.get('diameter_mm'), 'قطر میلگرد واقعی', positive=True)
    if _id(part.get('source_ref'), 'منبع قطعه') != bar['source_ref']:
        raise OwnershipError('منبع دیتایل قطعه و سند اتصال مغایر است')
    return diameter


def _contact_geometry(contact, project):
    roles = {}
    for link in contact['links']:
        role = link['role']
        if role in roles:
            raise OwnershipError('نقش عضو تکراری است')
        roles[role] = _member_prism(project, link, contact)
    if set(roles) != {'column', 'counterpart'}:
        raise OwnershipError('ستون و پی یا شناژ کامل نیستند')
    counterpart_kind = next(link['kind'] for link in contact['links']
                            if link['role'] == 'counterpart')
    axis, plane, _ = _face(roles['column'][0], roles['counterpart'][0],
                            kind=counterpart_kind,
                            contact_type=contact['contact_type'],
                            axis=contact['contact_axis'])
    return roles, axis, plane


def _transverse_clearance(point, first, second, axis):
    # Center-to-box-side distance in both documented prisms; *not* nominal
    # reinforcing clear cover until subtracting half of the true bar diameter.
    return min(point[i] - box[i] if side == 0 else box[i+3] - point[i]
               for box in (first, second) for i in range(3) if i != axis
               for side in (0, 1))


def preview(document, project):
    _object(document, _HEADER, 'مدرک مستقل طول مهاری میلگرد انتظار')
    if document['policy'] != POLICY:
        raise OwnershipError('نسخه پیش‌ممیزی مهاری پشتیبانی نمی‌شود')
    for key in ('project_id', 'joint_id', 'prepared_by', 'reviewer'):
        _id(document[key], key)
    if not isinstance(project, dict) or project.get('id') != document['project_id']:
        raise OwnershipError('پروژه مدرک با Snapshot واقعی مطابقت ندارد')
    author = _canonical(document['prepared_by'])
    reviewer = _canonical(document['reviewer'])
    if author == reviewer:
        raise OwnershipError('بازبین سند مهاری مستقل نیست')
    contact = _file_pointer(document['contact_document'], 'سند هندسی تماس')
    if (contact.get('project_id'), contact.get('joint_id')) != (
            document['project_id'], document['joint_id']):
        raise OwnershipError('مدرک مهاری برای اتصال دیگری ثبت شده است')
    base = contact_preview(contact, project)
    if (base.get('status') != 'COLUMN_FOUNDATION_FACE_PREVIEW_ONLY' or
            base.get('ready_for_boq') or base.get('commit_allowed') or base.get('rows')):
        raise OwnershipError('پیش‌ممیزی تماس نباید مجوز مالی صادر کند')
    if contact['starter_status'] != 'documented':
        raise OwnershipError('بدون میلگرد انتظار مستند، کنترل طول مهاری معتبر نیست')
    roles, axis, plane = _contact_geometry(contact, project)
    bases = {}
    for bar in contact['starter_bars']:
        ident = _canonical(bar['physical_bar_id'])
        if ident in bases:
            raise OwnershipError('شناسه فیزیکی انتظار در اتصال تکرار شده است')
        bases[ident] = bar
    checks = document['starter_checks']
    if not isinstance(checks, list) or len(checks) != len(bases):
        raise OwnershipError('برای تک‌تک میلگردهای انتظار، برگه مهاری مستقل لازم است')
    observed = []; seen = set()
    with localcontext(Context(prec=256, Emax=999999, Emin=-999999)):
        for check in checks:
            _object(check, _CHECK, 'بررسی هندسی میلگرد انتظار')
            ident = _canonical(_id(check['physical_bar_id'], 'هویت میلگرد'))
            if ident in seen or ident not in bases:
                raise OwnershipError('بررسی مهاری تکراری یا فاقد میلگرد واقعی است')
            seen.add(ident)
            bar = bases[ident]
            role = bar['owner_role']
            diameter = _bar_part(roles[role][1], bar)
            claimed_diameter = _num(check['diameter_mm'], 'قطر سند مهاری', positive=True)
            if claimed_diameter != diameter:
                raise OwnershipError('قطر دفتر واقعی با مدرک مهاری مغایر است')
            sheet = _file_pointer(check['worksheet_document'], 'برگه مستقل محاسبات مهاری')
            _object(sheet, _SHEET, 'برگه محاسبات طراح')
            if sheet['policy'] != CALC_POLICY:
                raise OwnershipError('قرارداد برگه محاسبات مهاری ناشناخته است')
            for key, expected in (('project_id', document['project_id']),
                                  ('joint_id', document['joint_id']),
                                  ('physical_bar_id', bar['physical_bar_id'])):
                if _id(sheet[key], key) != expected:
                    raise OwnershipError('هویت برگه طراح به این میلگرد متصل نیست')
            if _num(sheet['diameter_mm'], 'قطر برگه طراح', positive=True) != diameter:
                raise OwnershipError('قطر برگه طراح با دیتایل عضو مالک متفاوت است')
            for key in ('design_code_ref', 'calculation_ref', 'designer',
                        'independent_reviewer'):
                _id(sheet[key], key)
            designer, checker = (_canonical(sheet['designer']),
                                 _canonical(sheet['independent_reviewer']))
            if designer == checker or reviewer in (designer, checker) or author in (designer, checker):
                raise OwnershipError('استقلال تهیه‌کننده و بازبین برگه مهاری رعایت نشده است')
            # The predecessor can only attest straight centerlines. A radius,
            # bend, hook or lap requires an *additional* real shape contract.
            if (sheet['bend_status'] != 'straight' or sheet['bend_detail_ref'] != '' or
                    sheet['bend_radius_mm'] != '' or sheet['bend_angle_deg'] != ''):
                raise OwnershipError('خم یا قلاب در قرارداد مسیر مستقیم احراز نمی‌شود؛ دیتایل واقعی لازم است')
            p0 = _position(bar['start']); p1 = _position(bar['end'])
            if (p0[axis] - plane) * (p1[axis] - plane) >= 0:
                raise OwnershipError('میلگرد از سطح تماس عبور نمی‌کند')
            found_other = abs(plane - p0[axis]); found_column = abs(p1[axis] - plane)
            if (_num(check['provided_counterpart_m'], 'مهاری داخل پی یا شناژ') != found_other or
                    _num(check['provided_column_m'], 'مهاری داخل ستون') != found_column):
                raise OwnershipError('مقادیر طول مهاری اعلامی با هندسه واقعی برابر نیست')
            required_other = _num(sheet['required_counterpart_m'], 'طول لازم پی/شناژ', positive=True)
            required_column = _num(sheet['required_column_m'], 'طول لازم ستون', positive=True)
            if found_other < required_other or found_column < required_column:
                raise OwnershipError('طول مستقیم موجود از طول لازم ادعایی برگه طراح کمتر است')
            radial_offset = _transverse_clearance(p0, roles['column'][0],
                                                    roles['counterpart'][0], axis)
            actual_clear = radial_offset - diameter / Decimal(2000)
            if actual_clear < 0:
                raise OwnershipError('محور میلگرد با پوسته عضو و قطر واقعی تداخل دارد')
            if _num(check['transverse_clearance_m'], 'پوشش محاسبه‌شده') != actual_clear:
                raise OwnershipError('پوشش هندسی واقعی با ادعای سند برابر نیست')
            cover_req = _num(sheet['required_clear_cover_m'], 'پوشش لازم ادعایی', positive=True)
            if actual_clear < cover_req:
                raise OwnershipError('پوشش موجود از پوشش لازم در برگه طراح کمتر است')
            observed.append({'physical_bar_id': bar['physical_bar_id'],
                             'provided_counterpart_m': format(found_other,'f'),
                             'provided_column_m': format(found_column,'f'),
                             'transverse_clearance_m': format(actual_clear,'f'),
                             'unit': 'm', 'design_calculation_claim_checked': True,
                             'design_code_conformance_verified': False})
    return {'policy': POLICY, 'status': 'STARTER_DEVELOPMENT_EVIDENCE_PREVIEW_ONLY',
            'coverage': 'documented_straight_starters_only',
            'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
            'observations': deepcopy(observed),
            'blockers': [
                'ضوابط طول مهاری یا پوشش از مرجع آیین‌نامه مستقلاً استخراج و بازبینی نشده‌اند',
                'این موتور خم، قلاب، وصله و محصورشدگی واقعی را نمی‌پذیرد و بازبینی جداگانه لازم است',
                'SHA-256 تمامیت فایل است، نه اثبات اصالت نقشه، تأیید مهندس یا مالکیت مالی',
            ]}


def preview_file(project, path, sha256):
    return preview(read_evidence(path, sha256), project)
