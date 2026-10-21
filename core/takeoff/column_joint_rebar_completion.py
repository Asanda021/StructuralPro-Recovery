"""Read-only, source-bound *registered-piece* completeness preflight for a beam-column joint.

No reinforcement design, hook development equivalency, seismic spacing design,
financial ownership, or completeness of unknown drawings is certified here.
"""
from copy import deepcopy
from decimal import Decimal, Context, localcontext

from core.takeoff.bored_pile_ownership_preflight import (
    OwnershipError, _object, _id, _canonical, _hash, read_evidence,
)
from core.takeoff.bored_pile_joint_crosswalk import _num
from core.takeoff.column_joint_bar_crosswalk import preview as routes_preview
from core.takeoff.column_joint_beam_panel import _member_prism, _box

POLICY = 'column_joint_rebar_completion_v1'
_DOC = ('policy', 'project_id', 'joint_id', 'routes_document', 'prepared_by',
        'reviewer', 'inventory', 'development_checks', 'critical_tie_stations')
_POINTER = ('path', 'sha256', 'reference')
_INVENTORY = ('role', 'group_key', 'record_piece_id', 'physical_bar_id',
              'source_ref', 'scope', 'reason', 'reviewed_by')
_DEV = ('physical_bar_id', 'diameter_mm', 'required_development_m',
        'provided_development_m', 'standard_ref', 'calculation_ref',
        'designer', 'bend_status', 'bend_radius_mm', 'bend_detail_ref')
_TIE = ('role', 'physical_bar_id', 'x_m', 'y_m', 'z_m', 'station_ref', 'approved_by')


def _rows_for_members(geometry, project):
    """Return the full set of *represented* segments in the two referenced records."""
    result = {}
    roles = {}
    for link in geometry['links']:
        role = link['role']
        if role in roles:
            raise OwnershipError('نقش اتصال تکراری است')
        box, record = _member_prism(project, link, geometry)
        roles[role] = (box, record)
        category = 'rebars' if role == 'column' else 'bars'
        groups = record['data'].get(category)
        if not isinstance(groups, dict) or not groups:
            raise OwnershipError('دفتر آرماتور عضو برای ممیزی جامع موجود نیست')
        for group_key, group in groups.items():
            _id(group_key, 'گروه میلگرد')
            if not isinstance(group, dict):
                raise OwnershipError('گروه آرماتور نامعتبر است')
            if 'segments' not in group:
                if group == {'status': 'not_applicable'}:
                    continue
                raise OwnershipError('گروه فاقد فهرست کامل قطعات فیزیکی است')
            pieces = group['segments']
            if not isinstance(pieces, list) or len(pieces) > 2048:
                raise OwnershipError('فهرست قطعات عضو نامعتبر یا نامحدود است')
            for piece in pieces:
                if not isinstance(piece, dict):
                    raise OwnershipError('دیتایل قطعه عضو نامعتبر است')
                ident = _canonical(_id(piece.get('physical_id'), 'هویت قطعه'))
                part_id = _id(piece.get('id'), 'شناسه قطعه')
                src = _id(piece.get('source_ref'), 'منشأ قطعه')
                diameter = _num(piece.get('diameter_mm'), 'قطر مستند قطعه', positive=True)
                key = (role, group_key, part_id, ident)
                if key in result:
                    raise OwnershipError('قطعه تکراری در دفتر عضو')
                result[key] = (src, diameter, piece)
    if set(roles) != {'column', 'counterpart'}:
        raise OwnershipError('هر دو عضو نسخه‌دار لازم‌اند')
    if not result:
        raise OwnershipError('هیچ قطعه ثبت‌شده‌ای برای ممیزی وجود ندارد')
    return roles, result


def _turns(points):
    axes = []
    for left, right in zip(points, points[1:]):
        changed = [k for k in ('x_m', 'y_m', 'z_m')
                   if _num(left[k], 'مختصات محور') != _num(right[k], 'مختصات محور')]
        if len(changed) != 1:
            raise OwnershipError('قطعه دارای مسیر غیرمحورمند است')
        axes.append(changed[0])
    return sum(a != b for a, b in zip(axes, axes[1:]))


def preview(document, project):
    """Revalidate the former geometry/routes and crosswalk *every* listed member bar.

    Positive here means recorded pieces are accounted for, not that undocumented
    reinforcement does not exist and not that hooks satisfy any design code.
    """
    _object(document, _DOC, 'سند تکمیل آرماتور اتصال')
    if document['policy'] != POLICY:
        raise OwnershipError('نسخه سند تکمیل آرماتور اتصال نامعتبر است')
    for field in ('project_id', 'joint_id', 'prepared_by', 'reviewer'):
        _id(document[field], field)
    if (not isinstance(project, dict) or project.get('id') != document['project_id'] or
            _canonical(document['prepared_by']) == _canonical(document['reviewer'])):
        raise OwnershipError('هویت پروژه یا استقلال بازبین نامعتبر است')
    pointer = document['routes_document']
    _object(pointer, _POINTER, 'ارجاع مسیرهای واقعی میلگرد')
    _id(pointer['reference'], 'مرجع مسیر میلگرد')
    route_doc = read_evidence(_id(pointer['path'], 'مسیر فایل'),
                              _hash(pointer['sha256'], 'هش سند مسیر'))
    if (route_doc.get('project_id') != document['project_id'] or
            route_doc.get('joint_id') != document['joint_id']):
        raise OwnershipError('سند تکمیل به اتصال دیگری اشاره می‌کند')
    audited_routes = routes_preview(route_doc, project)
    if (audited_routes['status'] != 'BAR_ROUTE_PREVIEW_ONLY' or
            audited_routes['rows'] or audited_routes['ready_for_boq'] or audited_routes['commit_allowed']):
        raise OwnershipError('مسیر میلگرد به‌اشتباه آزادسازی مالی صادر کرده است')
    gp = route_doc['geometry_document']
    geometry = read_evidence(gp['path'], gp['sha256'])
    panel = _box(geometry['panel_zone'], 'چشمه اتصال')
    roles, registry = _rows_for_members(geometry, project)
    inventory = document['inventory']
    if not isinstance(inventory, list) or not 1 <= len(inventory) <= 2048:
        raise OwnershipError('صورت قطعات آرماتور باید کامل و محدود باشد')
    assigned = {}
    for row in inventory:
        _object(row, _INVENTORY, 'ردیف موجودی آرماتور')
        for key in ('role', 'group_key', 'record_piece_id', 'physical_bar_id',
                    'source_ref', 'reviewed_by'):
            _id(row[key], key)
        key = (row['role'], row['group_key'], row['record_piece_id'],
               _canonical(row['physical_bar_id']))
        if key in assigned or key not in registry:
            raise OwnershipError('صورت قطعات دارای ردیف اضافی، تکراری یا ناشناخته است')
        if row['source_ref'] != registry[key][0]:
            raise OwnershipError('مرجع قطعه با دفتر عضو متفاوت است')
        if _canonical(row['reviewed_by']) == _canonical(document['prepared_by']):
            raise OwnershipError('ممیزی قطعه از تهیه‌کننده مستقل نیست')
        scope = row['scope']
        if scope not in ('route', 'critical_tie', 'excluded_documented'):
            raise OwnershipError('نوع عضویت در اتصال صریح نیست')
        if scope == 'excluded_documented':
            _id(row['reason'], 'دلیل مستقل حذف از اتصال')
        elif row['reason']:
            raise OwnershipError('قطعه داخل اتصال نباید دلیل استثنا داشته باشد')
        assigned[key] = row
    if set(assigned) != set(registry):
        raise OwnershipError('فهرست آرماتور عضو ناقص است؛ قطعه ثبت‌شده حذف شده است')
    route_ids = {_canonical(r['physical_bar_id']) for r in route_doc['bar_routes']}
    scheduled_routes = {_canonical(r['physical_bar_id']) for r in inventory if r['scope'] == 'route'}
    if route_ids != scheduled_routes or not scheduled_routes:
        raise OwnershipError('تمام میلگردهای برچسب‌خورده اتصال باید مسیر یکتای مستند داشته باشند')
    tie_ids = {_canonical(r['physical_bar_id']) for r in inventory if r['scope'] == 'critical_tie'}
    if not tie_ids:
        raise OwnershipError('خاموت بحرانی فاقد صورت قطعه فیزیکی مستند است')
    # Duplicate physical IDs across schedules must never become separate members.
    all_physical = [_canonical(r['physical_bar_id']) for r in inventory]
    if len(set(all_physical)) != len(all_physical):
        raise OwnershipError('شناسه فیزیکی میلگرد در صورت قطعات تکراری است')
    for target in set(all_physical):
        count = 0
        for book in ('reviewed_structural_members', 'beam_detail_register'):
            for record in project.get(book, {}).values():
                for group in (record.get('data', {}).get('rebars', {}),
                              record.get('data', {}).get('bars', {})):
                    if not isinstance(group, dict):
                        raise OwnershipError('دفتر عضو دیگری دارای ساختار نامعتبر است')
                    for detail in group.values():
                        if not isinstance(detail, dict):
                            raise OwnershipError('دیتایل گروه عضو نامعتبر است')
                        for piece in detail.get('segments', []):
                            if (isinstance(piece, dict) and piece.get('physical_id') is not None
                                    and _canonical(piece['physical_id']) == target):
                                count += 1
        if count != 1:
            raise OwnershipError('قطعه‌ای در عضو سوم تکرار شده یا در دفتر وجود ندارد')
    checks = document['development_checks']
    if not isinstance(checks, list) or len(checks) != len(route_ids):
        raise OwnershipError('برای تک‌تک میلگردهای عبوری، بررسی طول مهاری مستند لازم است')
    route_lookup = {_canonical(r['physical_bar_id']): r for r in route_doc['bar_routes']}
    checked = set()
    with localcontext(Context(prec=256, Emax=999999, Emin=-999999)):
        for check in checks:
            _object(check, _DEV, 'مدرک طول مهاری میلگرد')
            bar = _canonical(check['physical_bar_id'])
            if bar in checked or bar not in route_ids:
                raise OwnershipError('مدرک مهاری مفقود یا تکراری است')
            checked.add(bar)
            inv = next(r for r in inventory if _canonical(r['physical_bar_id']) == bar)
            key = (inv['role'], inv['group_key'], inv['record_piece_id'], bar)
            if _num(check['diameter_mm'], 'قطر') != registry[key][1]:
                raise OwnershipError('قطر دیتایل طراحی با قطر قطعه مالک تفاوت دارد')
            required = _num(check['required_development_m'], 'طول لازم', positive=True)
            provided = _num(check['provided_development_m'], 'طول موجود', positive=True)
            _id(check['standard_ref'], 'نسخه مرجع طراحی')
            _id(check['calculation_ref'], 'برگه محاسبات طراح')
            _id(check['designer'], 'طراح دیتایل')
            if (_canonical(check['designer']) == _canonical(document['reviewer']) or
                    _canonical(check['designer']) == _canonical(document['prepared_by'])):
                raise OwnershipError('طراح دیتایل مستقل نیست')
            if provided < required or provided > _num(route_lookup[bar]['centerline_length_m'], 'طول محور'):
                raise OwnershipError('طول موجود با طول لازم مستند یا طول واقعی قطعه ناسازگار است')
            turns = _turns(route_lookup[bar]['points'])
            if turns:
                if check['bend_status'] != 'documented':
                    raise OwnershipError('خم مسیر بدون مدرک جزئیات مجاز نیست')
                _num(check['bend_radius_mm'], 'شعاع خم', positive=True)
                _id(check['bend_detail_ref'], 'منبع جزئیات خم')
            elif (check['bend_status'] != 'straight' or check['bend_radius_mm'] != '' or
                  check['bend_detail_ref'] != ''):
                raise OwnershipError('قطعه مستقیم نباید خم ادعایی داشته باشد')
    stations = document['critical_tie_stations']
    if not isinstance(stations, list) or len(stations) != len(tie_ids):
        raise OwnershipError('خاموت‌های بحرانی باید موقعیت‌های مستقل و کامل داشته باشند')
    found = set()
    for station in stations:
        _object(station, _TIE, 'جانمایی خاموت بحرانی')
        role = _id(station['role'], 'مالک خاموت')
        ident = _canonical(station['physical_bar_id'])
        if role not in roles or ident in found or ident not in tie_ids:
            raise OwnershipError('خاموت بحرانی دارای نقش یا هویت تکراری است')
        if not any(_canonical(i['physical_bar_id']) == ident and i['role'] == role
                   and i['scope'] == 'critical_tie' for i in inventory):
            raise OwnershipError('خاموت در عضو مالک واقعی ثبت نشده است')
        found.add(ident)
        for key in ('station_ref', 'approved_by'):
            _id(station[key], key)
        if _canonical(station['approved_by']) == _canonical(document['reviewer']):
            raise OwnershipError('بازبین و تأییدکننده جانمایی خاموت یکی است')
        position = tuple(_num(station[k], k) for k in ('x_m', 'y_m', 'z_m'))
        box = roles[role][0]
        if any(position[i] < panel[i] or position[i] > panel[i+3] or
               position[i] < box[i] or position[i] > box[i+3] for i in range(3)):
            raise OwnershipError('نقطه مرجع خاموت خارج از چشمه یا منشور عضو است')
    return {'policy': POLICY, 'status': 'COLUMN_REBAR_COMPLETENESS_PREVIEW_ONLY',
            'coverage': 'all_enumerated_segments_of_two_versioned_members',
            'geometry_record_bound': True,
            'registered_piece_count': len(inventory),
            'routed_piece_count': len(route_ids),
            'critical_tie_count': len(tie_ids),
            'ready_for_boq': False, 'commit_allowed': False, 'rows': [],
            'blockers': [
                'کامل‌بودن فقط نسبت به قطعات فیزیکی ثبت‌شده در دو عضو اثبات شده؛ نقشه مستقل ممکن است قطعات دیگری داشته باشد',
                'برابری طول‌های مهاری با مدارک ادعایی، صحت محاسبات آیین‌نامه‌ای و اجرای خم‌ها را تأیید نمی‌کند',
                'نقطه مرجع خاموت، شکل بسته و فاصله‌گذاری تمام خاموت‌ها را اثبات نمی‌کند',
                'مالکیت مالی مشترک و اصالت نقشه هنوز حل نشده است',
            ]}


def preview_file(project, path, sha256):
    return preview(read_evidence(path, sha256), project)
