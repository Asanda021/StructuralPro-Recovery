"""Explicit paint, putty, primer and surface preparation takeoff (phase one).

No layer count, material usage, waste, substrate deduction or unit price is inferred.
Existing reviewed AEC registry, CAS, review, amendments and ledger are reused.
Paint and tile/stone may not occupy the same physical face footprint.
"""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from core.commercial.exact_values import exact, wire
from core.takeoff.roof_detail import strict, checked, canonical, review_digest, validate_roof_source, n as _n
from core.takeoff.reviewed_components import require_text
from core.takeoff.architecture_detail import POLICY, COMMON, intersection, area

CONTRACT = 'paint_surface_v1'
OPERATIONS = ('surface_preparation', 'putty', 'primer', 'finish_coat')
LABELS = {'surface_preparation': 'آماده‌سازی مستند سطح', 'putty': 'بتونه‌کاری مستند',
          'primer': 'اجرای آستر مستند', 'finish_coat': 'دست رنگ نهایی مستند'}
GEOMETRY = ('physical_surface_id', 'host_id', 'space_id', 'face', 'plane', 'shape',
            'unit', 'length_m', 'width_m', 'count', 'repeat_ref', 'source_ref', 'approved_by')
ZONE = ('x', 'y', 'width_m', 'height_m', 'opening_ids', 'scope_ref')
PASS = ('zone_id', 'pass_no', 'material_basis', 'quantity_per_m2', 'quantity_unit',
        'material_ref', 'rate_ref', 'no_material_reason')
STAGE = ('status', 'source_ref', 'approved_by', 'reason', 'passes')


def is_paint(data):
    return (isinstance(data, dict) and data.get('kind') == 'paint_finish' and
            isinstance(data.get('architecture_detail'), dict) and
            data['architecture_detail'].get('contract') == CONTRACT)


def number(value, label, *, zero=False, integer=False):
    if isinstance(value, (float, bool)):
        raise ValueError(label + ': float/boolean مجاز نیست؛ مدرک دقیق لازم است')
    return _n(value, label, zero=zero, integer=integer)


def rectangle(item, length, height):
    x, y = number(item.get('x'), 'مختصات طول', zero=True), number(item.get('y'), 'مختصات عرض', zero=True)
    w, h = number(item.get('width_m'), 'عرض ناحیه'), number(item.get('height_m'), 'ارتفاع ناحیه')
    if x + w > length or y + h > height:
        raise ValueError('ناحیه یا بازشو خارج از مرز فیزیکی است')
    return (x, y, x + w, y + h)


def _items(value, label):
    if not isinstance(value, list) or len(value) > 512:
        raise ValueError(label + ': جدول صریح و محدود لازم است')
    return value


def _identity(row, fields, ids, physical, *, require_approval=True):
    strict(row, COMMON + fields, 'جزء مستند رنگ')
    if require_approval:checked(row)
    ident = canonical(row['id']);physical_id = canonical(row['physical_key'])
    if '|' in row['id'] or ident in ids or physical_id in physical:
        raise ValueError('جزء فیزیکی یا شناسه ردیف تکراری است')
    ids.add(ident);physical.add(physical_id)


def _areas(data, *, require_approval=True):
    detail = data['architecture_detail']
    strict(detail, ('contract', 'geometry', 'openings', 'zones', 'stages'), 'قرارداد رنگ')
    geom = detail['geometry'];strict(geom, GEOMETRY, 'هندسه رنگ')
    if require_approval:checked(geom)
    for key in ('physical_surface_id', 'host_id', 'space_id', 'repeat_ref'):
        require_text(geom[key], 'هویت فیزیکی و دامنه سطح')
    face = geom['face']
    if (geom['shape'] != 'rectangle' or geom['unit'] != 'm' or
            face not in ('inside', 'outside', 'ceiling') or
            geom['plane'] != ('horizontal' if face == 'ceiling' else 'vertical')):
        raise ValueError('رنگ فقط روی سطح مستطیلی قائم یا سقف افقی مستند معتبر است')
    length = number(geom['length_m'], 'طول');height = number(geom['width_m'], 'امتداد دوم')
    count = number(geom['count'], 'تعداد مستقل', integer=True)
    ids, physical = set(), set();openings = {}
    for opening in _items(detail['openings'], 'بازشوها'):
        _identity(opening, ('x','y','width_m','height_m'), ids, physical, require_approval=require_approval)
        box = rectangle(opening, length, height)
        if any(intersection(box, b) > 0 for b in openings.values()):
            raise ValueError('بازشوها متداخل‌اند')
        openings[opening['id']] = box
    zones = {}
    all_boxes = []
    for zone in _items(detail['zones'], 'نواحی رنگ'):
        _identity(zone, ZONE, ids, physical, require_approval=require_approval)
        require_text(zone['scope_ref'], 'مدرک دامنه اجرای رنگ')
        box = rectangle(zone, length, height)
        if any(intersection(box, b) > 0 for b in all_boxes):
            raise ValueError('سطح رنگ روی دو ناحیه فیزیکی دوباره شمرده شده است')
        all_boxes.append(box)
        links = zone['opening_ids']
        if not isinstance(links, list) or len(links) != len(set(map(str, links))):
            raise ValueError('بازشوهای مرتبط باید فهرست یکتای صریح باشند')
        expected = {k for k,v in openings.items() if intersection(box,v) > 0}
        if set(links) != expected:
            raise ValueError('بازشوهای متقاطع باید دقیقاً یک‌بار به ناحیه رنگ متصل شوند')
        deduction = sum((intersection(box,openings[k]) for k in links), Decimal(0))
        net = area(box) - deduction
        if net <= 0:
            raise ValueError('سطح خالص رنگ باید مثبت باشد')
        zones[zone['id']] = (zone,box,net,deduction)
    if not zones:
        raise ValueError('ناحیه مستند رنگ لازم است')
    return geom, zones, count, ids, physical


@exact
def preview(data, engine, require_review=False):
    errors = [];rows = [];source = data.get('source',{});kind = data.get('kind')
    try:
        if not is_paint(data) or data.get('measurement_policy') != POLICY:
            raise ValueError('قرارداد تخصصی رنگ باید صریح باشد')
        strict(data, ('kind','floor_id','system_id','building_id','axis','source',
                      'measurement_policy','components','architecture_detail','roof_review'), 'سیستم رنگ')
        for field in ('building_id','floor_id','system_id','axis'):
            require_text(data[field], 'هویت و موقعیت')
        validate_roof_source(source, data['system_id'])
        for field in ('plan_ref','detail_ref'):
            require_text(source.get(field),'مرجع نقشه و دیتایل')
        if any(comp != {'status':'unreviewed'} for comp in data['components'].values()):
            raise ValueError('متره عمومی و تخصصی رنگ هم‌زمان مجاز نیست')
        geom, zones, count, ids, physical = _areas(data)
        stages = data['architecture_detail']['stages']
        if not isinstance(stages, dict) or set(stages) != set(OPERATIONS):
            raise ValueError('وضعیت هر چهار عملیات رنگ و آماده‌سازی باید مشخص باشد')
        for operation, group in stages.items():
            strict(group, STAGE, 'گروه رنگ');require_text(group['source_ref'],'مرجع عملیات')
            require_text(group['approved_by'],'تأییدکننده عملیات')
            passes = _items(group['passes'], 'دست‌های مستند رنگ')
            status = group['status']
            if status == 'not_applicable':
                if operation == 'finish_coat' or passes:
                    raise ValueError('رنگ نهایی ضروری و بدون دست رنگ مجاز نیست')
                require_text(group['reason'],'علت عدم کاربرد عملیات')
                continue
            if status != 'confirmed' or group['reason'] not in ('', None) or not passes:
                raise ValueError('دیتایل اجرا و تأیید هر دست رنگ لازم است')
            sequence = {zone_id:[] for zone_id in zones}
            for coat in passes:
                _identity(coat, PASS, ids, physical)
                zone_id = coat['zone_id']
                if zone_id not in zones:
                    raise ValueError('دست رنگ به ناحیه واقعی متصل نیست')
                pass_no = number(coat['pass_no'], 'شماره دست', integer=True)
                sequence[zone_id].append(pass_no)
                zone, box, net, deduction = zones[zone_id]
                params = dict(zone_id=zone_id, physical_surface_id=geom['physical_surface_id'],
                              host_id=geom['host_id'], face=geom['face'], operation=operation,
                              pass_no=pass_no, gross_area_m2=area(box),
                              deducted_area_m2=deduction, net_area_m2=net,
                              repeated_count=count, coat_reference=coat['source_ref'])
                def emit(code, quantity, unit, suffix, role, formula, meta):
                    rows.append(dict(source_id=f"aec:paint_finish:{data['floor_id']}:{data['system_id']}:{coat['id']}:{suffix}",
                                     line_id=coat['id']+':'+suffix, item_code=code,
                                     quantity=wire(quantity*count),unit=unit,domain='building',
                                     description=LABELS[operation]+' '+data['system_id'],
                                     formula='تعداد سطوح مستقل × ('+formula+')',
                                     params=wire(deepcopy(meta)),component=code,
                                     method=POLICY,source_ref=coat['source_ref'],role=role))
                emit(operation, net, 'm2', 'work', 'work',
                     'سطح مستطیلی − بازشوهای واقعی؛ یک دست مستند', params)
                basis = coat['material_basis']
                if basis == 'documented_rate':
                    rate = number(coat['quantity_per_m2'], 'مصرف واقعی هر مترمربع')
                    if coat['quantity_unit'] not in ('kg','litre'):
                        raise ValueError('واحد مصرف فقط کیلوگرم یا لیتر مستند است')
                    require_text(coat['material_ref'],'مرجع مصالح')
                    require_text(coat['rate_ref'],'مرجع نرخ مصرف')
                    if coat['no_material_reason'] not in ('', None):
                        raise ValueError('مصرف مصالح مستند با اعلام عدم مصرف متناقض است')
                    emit(operation+'_material', net*rate, coat['quantity_unit'],
                         'material', 'material', 'سطح خالص × نرخ مستند هر دست؛ اطلاعاتی، نه پرداخت مضاعف',
                         {**params,'material_ref':coat['material_ref'], 'rate_ref':coat['rate_ref'],
                          'quantity_per_m2':rate})
                elif basis == 'not_applicable':
                    if operation != 'surface_preparation' or coat['quantity_per_m2'] not in ('',None) or coat['quantity_unit'] != 'none' or coat['material_ref'] not in ('',None) or coat['rate_ref'] not in ('',None):
                        raise ValueError('عدم مصرف مصالح فقط برای آماده‌سازی بدون ماده مجاز است')
                    require_text(coat['no_material_reason'],'علت عدم مصرف مصالح')
                else:
                    raise ValueError('نرخ مصرف مجهول؛ مقدار مصالح نباید حدس زده شود')
            for zone_id, numbers in sequence.items():
                if sorted(numbers) != list(range(1,len(numbers)+1)) or not numbers:
                    raise ValueError('تعداد دست هر ناحیه باید صریح، پیوسته و بدون تکرار باشد')
        if len({canonical(row['source_id']) for row in rows}) != len(rows):
            raise ValueError('شناسه ردیف محاسبه تکراری است')
        if require_review:
            rv = data.get('roof_review',{})
            require_text(rv.get('reviewer'),'بازبین مستقل')
            require_text(rv.get('note'),'توضیح بازبینی')
            if rv.get('digest') != review_digest(data):
                raise ValueError('بازبینی جاری با داده تغییر‌یافته معتبر نیست')
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:
        errors.append(str(exc));rows.clear()
    return dict(kind=kind, floor_id=data.get('floor_id'),system_id=data.get('system_id'),
                source_id=source.get('source_id'),ready=not errors,blockers=errors,
                rows=rows,preview_only=True)


def remap_copy(data,replacements):
    a=data['architecture_detail'];g=a['geometry'];g['physical_surface_id']='PS-'+uuid4().hex;g['host_id']='PH-'+uuid4().hex
    for table in ('openings','zones'):
        for p in a[table]:
            p['physical_key']='P-'+uuid4().hex
            if table == 'zones':p['opening_ids']=[replacements.get(i,i) for i in p['opening_ids']]
    for stage in a['stages'].values():
        for coat in stage['passes']:
            coat['zone_id']=replacements.get(coat['zone_id'],coat['zone_id'])


@exact
def guard(project):
    """Require shared host/face geometry not to overlap paint or tile/stone.

    Existing unscoped/legacy paint cannot be silently assigned to a new host.
    An unknown geometry never permits a guessed spatial clearance.
    """
    from core.takeoff.manual_formula_amendments import beam_current
    from core.takeoff.interior_cover_detail import is_cover,rect as cover_rect
    register=project.get('reviewed_aec_systems',{})
    paint=[];covers=[];legacy=[]
    for key,record in register.items():
        d=record.get('data',{})
        if d.get('kind') not in ('paint_finish','ceramic_finish','stone_cladding','stone_floor'):
            continue
        if is_paint(d):
            effective=beam_current(project,key)['data']
            geom,zones,count,_,_=_areas(effective,require_approval=False)
            for zone,b,net,ded in zones.values():
                paint.append((effective,geom,b))
        elif is_cover(d):
            effective=beam_current(project,key)['data'];a=effective['architecture_detail'];g=a['geometry']
            if g['face'] not in ('inside','outside','ceiling'):
                continue
            L,W=number(g['length_m'],'طول پوشش'),number(g['width_m'],'عرض پوشش')
            for zone in a['surfaces']:
                covers.append((effective,g,cover_rect(zone,L,W)))
        elif d.get('kind') in ('paint_finish','ceramic_finish','stone_cladding'):
            legacy.append(d)
    for d,g,b in paint:
        for other,og,ob in paint+covers:
            if other is d:
                continue
            if (canonical(d['building_id']) != canonical(other['building_id']) or
                    d['floor_id'] != other['floor_id']):
                continue
            if canonical(g['physical_surface_id']) == canonical(og['physical_surface_id']) and (canonical(g['host_id']) != canonical(og['host_id']) or g['face'] != og['face']):
                raise ValueError('هویت فیزیکی سطح به دو میزبان یا وجه تخصیص یافته است')
            if canonical(g['host_id']) != canonical(og['host_id']) or g['face'] != og['face']:
                continue
            if (d['axis'] != other['axis'] or g['space_id'] != og['space_id'] or
                    g['plane'] != og['plane'] or
                    number(g['length_m'],'طول سطح') != number(og['length_m'],'طول پوشش') or
                    number(g['width_m'],'امتداد دوم') != number(og['width_m'],'امتداد دوم پوشش') or
                    number(g['count'],'تکرار سطح',integer=True) != number(og['count'],'تکرار پوشش',integer=True)):
                raise ValueError('مرجع مکانی، هندسه یا تعداد سطح مشترک رنگ و سنگ/کاشی ناسازگار است')
            if intersection(b,ob)>0:
                raise ValueError('رنگ و کاشی/سنگ یا دو قرارداد رنگ روی ناحیه مشترک دوباره شمرده شده‌اند')
        for unknown in legacy:
            if unknown.get('floor_id') == d['floor_id'] and unknown.get('building_id') in (None,d['building_id']):
                raise ValueError('مالکیت پوشش تاریخی بدون جانمایی معتبر قابل احراز نیست')
