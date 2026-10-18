"""Documented rectangular suspended-ceiling takeoff, phase-one engineering scope.

Panels must partition the net plane exactly. Every profile, hanger, junction and
edge length has an explicit physical identity and source; none are inferred from
spacing, gross area, manufacturer ratios or waste percentages. Ancillary material
rows are informational: only the ceiling work area is payable via shared BOQ.
This is NOT a structural load, deflection, seismic or suspension design check.
"""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from core.commercial.exact_values import exact, wire
from core.takeoff.roof_detail import strict, checked, canonical, review_digest, validate_roof_source, n as _n
from core.takeoff.reviewed_components import require_text
from core.takeoff.architecture_detail import POLICY, COMMON, intersection, area

CONTRACT = 'suspended_ceiling_rectangular_v1'
GEOMETRY = ('physical_surface_id','host_id','space_id','face','plane','shape','unit',
            'length_m','width_m','count','repeat_ref','source_ref','approved_by')
BOX = ('x','y','width_m','height_m')
PANEL = BOX + ('material_ref','stock_ref','placement_ref')
RAIL = ('axis','fixed_m','start_m','end_m','profile_ref','detail_ref')
HANGER = ('x','y','rail_id','hanger_ref','anchorage_ref')
CONNECTOR = ('x','y','main_id','cross_id','connection_ref')
EDGE = ('axis','fixed_m','start_m','end_m','trim_ref')
GROUP = ('status','source_ref','approved_by','reason','items')
GROUPS = ('panels','main_rails','cross_rails','hangers','connectors','edge_trims')
LABELS = {'panels':'پانل نصب‌شده','main_rails':'پروفیل اصلی',
          'cross_rails':'پروفیل فرعی','hangers':'آویز مستند',
          'connectors':'اتصال مستند','edge_trims':'نبشی و لبه مستند'}


def is_ceiling(data):
    return isinstance(data,dict) and data.get('kind')=='suspended_ceiling' and isinstance(data.get('architecture_detail'),dict) and data['architecture_detail'].get('contract')==CONTRACT


def number(value,label,*,zero=False,integer=False):
    if isinstance(value,(bool,float)):
        raise ValueError(label+': float یا boolean سند عددی دقیق نیست')
    return _n(value,label,zero=zero,integer=integer)


def bounding(item,L,W):
    x=number(item.get('x'),'مختصات طول',zero=True)
    y=number(item.get('y'),'مختصات عرض',zero=True)
    w=number(item.get('width_m'),'طول پانل یا بازشو')
    h=number(item.get('height_m'),'عرض پانل یا بازشو')
    if x+w>L or y+h>W:raise ValueError('قطعه یا بازشو خارج از مرز هندسی سقف است')
    return (x,y,x+w,y+h)


def listed(value,label):
    if not isinstance(value,list) or len(value)>512:
        raise ValueError(label+': جدول محدود و صریح لازم است')
    return value


def identity(item,fields,used,physical):
    strict(item,COMMON+fields,'قطعه سقف کاذب')
    checked(item)
    ident=canonical(item['id']);key=canonical(item['physical_key'])
    if '|' in item['id'] or ident in used or key in physical:
        raise ValueError('شناسه یا قطعه فیزیکی سقف کاذب تکراری است')
    used.add(ident);physical.add(key)


def line(item,L,W):
    axis=item['axis']
    if axis not in ('x','y'):raise ValueError('محور پروفیل باید صریح باشد')
    fixed=number(item['fixed_m'],'مختصات عمود پروفیل',zero=True)
    start=number(item['start_m'],'شروع پروفیل',zero=True)
    end=number(item['end_m'],'انتهای پروفیل',zero=True)
    if start>=end or (fixed>W if axis=='x' else fixed>L) or (end>L if axis=='x' else end>W):
        raise ValueError('جانمایی پروفیل خارج از سقف یا بدون طول است')
    return (axis,fixed,start,end)


def line_contains(run,x,y):
    axis,fixed,start,end=run
    return (y==fixed and start<=x<=end) if axis=='x' else (x==fixed and start<=y<=end)


def meet(a,b):
    if a[0]==b[0]:return None
    horiz=a if a[0]=='x' else b
    vert=b if a[0]=='x' else a
    x,y=vert[1],horiz[1]
    return (x,y) if line_contains(horiz,x,y) and line_contains(vert,x,y) else None


def confirmed(group,label,*,required):
    strict(group,GROUP,'گروه سقف کاذب')
    require_text(group.get('source_ref'),'مرجع گروه '+label)
    require_text(group.get('approved_by'),'تأییدکننده گروه '+label)
    items=listed(group.get('items'),label)
    if group['status']=='not_applicable':
        if required or items:raise ValueError('اجزای ضروری سقف یا عدم کاربرد ناسازگار است')
        require_text(group.get('reason'),'علت عدم کاربرد '+label)
        return False
    if group['status']!='confirmed' or not items or group['reason'] not in ('',None):
        raise ValueError('گروه سقف کاذب باید دارای جزئیات قطعی و مستند باشد')
    return True


@exact
def preview(data,engine,require_review=False):
    errors=[];rows=[];source=data.get('source',{}) if isinstance(data,dict) else {};kind=data.get('kind') if isinstance(data,dict) else None
    try:
        if not is_ceiling(data) or data.get('measurement_policy')!=POLICY:
            raise ValueError('قرارداد تخصصی سقف کاذب معتبر نیست')
        strict(data,('kind','floor_id','system_id','building_id','axis','source',
                     'measurement_policy','components','architecture_detail','roof_review'),'سقف کاذب')
        for key in ('floor_id','system_id','building_id','axis'):require_text(data[key],'هویت/موقعیت')
        validate_roof_source(source,data['system_id'])
        for key in ('plan_ref','detail_ref'):require_text(source.get(key),'مرجع نقشه و دیتایل')
        if any(v!={'status':'unreviewed'} for v in data['components'].values()):
            raise ValueError('دیتایل عمومی و تخصصی سقف کاذب نباید ترکیب شوند')
        a=data['architecture_detail'];strict(a,('contract','geometry','openings','groups'),'دیتایل سقف کاذب')
        geom=a['geometry'];strict(geom,GEOMETRY,'هندسه سقف کاذب');checked(geom)
        for k in ('physical_surface_id','host_id','space_id','repeat_ref'):require_text(geom[k],'هویت هندسی سقف')
        if (geom['shape']!='rectangle' or geom['face']!='ceiling' or geom['plane']!='horizontal' or geom['unit']!='m'):
            raise ValueError('فقط سقف کاذب افقی مستطیلی با واحد متر پذیرفته است')
        L=number(geom['length_m'],'طول سقف');W=number(geom['width_m'],'عرض سقف');count=number(geom['count'],'تعداد واحدهای یکسان',integer=True)
        ids=set();physical=set();holes={}
        for o in listed(a['openings'],'بازشوهای سقف'):
            identity(o,BOX,ids,physical)
            box=bounding(o,L,W)
            if any(intersection(box,prior)>0 for prior in holes.values()):raise ValueError('بازشوهای سقف متداخل‌اند')
            holes[o['id']]=box
        net=L*W-sum((area(v) for v in holes.values()),Decimal(0))
        if net<=0:raise ValueError('مساحت خالص سقف کاذب باید مثبت باشد')
        groups=a['groups']
        if not isinstance(groups,dict) or set(groups)!=set(GROUPS):
            raise ValueError('وضعیت همه اجزای سقف کاذب باید مستند باشد')
        status={key:confirmed(groups[key],key,required=key in ('panels','main_rails','cross_rails','hangers')) for key in GROUPS}
        panels=[];p_area=Decimal(0)
        for panel in groups['panels']['items']:
            identity(panel,PANEL,ids,physical)
            for ref in ('material_ref','stock_ref','placement_ref'):require_text(panel[ref],'مدرک پانل نصب‌شده')
            box=bounding(panel,L,W)
            if any(intersection(box,opening)>0 for opening in holes.values()):raise ValueError('پانل با بازشوی کسرشده تداخل دارد')
            if any(intersection(box,prior)>0 for prior in panels):raise ValueError('پانل دوباره شمرده شده است')
            panels.append(box);p_area+=area(box)
        if p_area!=net:raise ValueError('مساحت پانل‌های نصب‌شده با سطح خالص مستند برابر نیست؛ هندسه ناقص است')
        runs={};rails_by_type={}
        for group in ('main_rails','cross_rails'):
            rails_by_type[group]={}
            for item in groups[group]['items']:
                identity(item,RAIL,ids,physical)
                require_text(item['profile_ref'],'پروفیل واقعی');require_text(item['detail_ref'],'مدرک طول پروفیل')
                run=line(item,L,W)
                for previous in rails_by_type[group].values():
                    if run[0]==previous[0] and run[1]==previous[1] and min(run[3],previous[3])>max(run[2],previous[2]):
                        raise ValueError('پروفیل یک گروه دو بار شمرده شده است')
                rails_by_type[group][item['id']]=run
                runs[item['id']]=run
        # A rail cannot be billed under both primary and secondary identities.
        for run in rails_by_type['main_rails'].values():
            for other in rails_by_type['cross_rails'].values():
                if run[0]==other[0] and run[1]==other[1] and min(run[3],other[3])>max(run[2],other[2]):
                    raise ValueError('پروفیل اصلی و فرعی روی یک قطعه مشترک دوباره شمرده شده‌اند')
        hangers=set();supported=set()
        for item in groups['hangers']['items']:
            identity(item,HANGER,ids,physical)
            for ref in ('hanger_ref','anchorage_ref'):require_text(item[ref],'مدرک آویز')
            x=number(item['x'],'محل آویز طول',zero=True);y=number(item['y'],'محل آویز عرض',zero=True)
            if x>L or y>W or item['rail_id'] not in rails_by_type['main_rails'] or not line_contains(rails_by_type['main_rails'][item['rail_id']],x,y):
                raise ValueError('آویز به پروفیل اصلی و جانمایی واقعی متصل نیست')
            if (x,y) in hangers:raise ValueError('آویز فیزیکی تکراری است')
            hangers.add((x,y));supported.add(item['rail_id'])
        if supported!=set(rails_by_type['main_rails']):raise ValueError('پروفیل اصلی فاقد حتی یک آویز مستند است')
        expected={(x,y,main,cross) for main,ra in rails_by_type['main_rails'].items() for cross,rb in rails_by_type['cross_rails'].items() for pt in [meet(ra,rb)] if pt is not None for x,y in [pt]}
        if bool(expected)!=status['connectors']:
            raise ValueError('وجود یا عدم کاربرد اتصال‌ها با تقاطع پروفیل‌ها ناسازگار است')
        actual=set()
        for item in groups['connectors']['items']:
            identity(item,CONNECTOR,ids,physical)
            require_text(item['connection_ref'],'مدرک اتصال فیزیکی')
            key=(number(item['x'],'مختصات اتصال',zero=True),number(item['y'],'مختصات اتصال',zero=True),item['main_id'],item['cross_id'])
            if key not in expected or key in actual:raise ValueError('اتصال تکراری یا بدون تقاطع واقعی است')
            actual.add(key)
        if actual!=expected:raise ValueError('تمام تقاطع‌های پروفیل باید یک‌به‌یک ثبت شوند')
        edge_runs=[]
        for item in groups['edge_trims']['items']:
            identity(item,EDGE,ids,physical)
            require_text(item['trim_ref'],'مرجع نبشی لبه')
            edge=line(item,L,W)
            if (edge[0]=='x' and edge[1] not in (Decimal(0),W)) or (edge[0]=='y' and edge[1] not in (Decimal(0),L)):
                raise ValueError('نبشی لبه باید روی مرز مستند سقف باشد')
            if any(edge[0]==other[0] and edge[1]==other[1] and
                   min(edge[3],other[3])>max(edge[2],other[2]) for other in edge_runs):
                raise ValueError('نبشی یا لبه فیزیکی تکراری است')
            edge_runs.append(edge)
        if len({canonical(item['id']) for group in GROUPS for item in groups[group]['items']})!=sum(len(groups[g]['items']) for g in GROUPS):
            raise ValueError('شناسه اجزای سقف یکسان نیست')
        def emit(code,value,unit,role,ref,formula,params):
            rows.append(dict(source_id=f"aec:suspended_ceiling:{data['floor_id']}:{data['system_id']}:{code}",
                             line_id=code,item_code=code,quantity=wire(value*count),unit=unit,domain='building',
                             description=(LABELS.get(code,'اجرای سطح خالص سقف کاذب')+' '+data['system_id']),
                             formula='تعداد مستند × ('+formula+')',params=wire(deepcopy(params)),
                             component=code,method=POLICY,source_ref=ref,role=role))
        emit('ceiling_work',net,'m2','work',geom['source_ref'],
             'سطح سقف − مساحت بازشوها؛ برابر مجموع پانل‌های جانمایی‌شده',
             dict(physical_surface_id=geom['physical_surface_id'],net_area_m2=net,opening_ids=list(holes),panel_ids=[p['id'] for p in groups['panels']['items']]))
        for group in GROUPS:
            items=groups[group]['items']
            if not items:continue
            if group in ('main_rails','cross_rails'):
                quantity=sum((runs[p['id']][3]-runs[p['id']][2] for p in items),Decimal(0));unit='m'
            elif group=='edge_trims':
                quantity=sum((number(p['end_m'],'انتها')-number(p['start_m'],'ابتدا',zero=True) for p in items),Decimal(0));unit='m'
            else:quantity=Decimal(len(items));unit='count'
            emit(group,quantity,unit,'material',groups[group]['source_ref'],
                 'طول یا تعداد قطعات دارای هویت و جانمایی صریح؛ بدون پرت یا فاصله فرضی',
                 dict(ids=[p['id'] for p in items],physical_keys=[p['physical_key'] for p in items]))
        if require_review:
            review=data.get('roof_review',{});require_text(review.get('reviewer'),'بازبین');require_text(review.get('note'),'یادداشت بازبین')
            if review.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,ArithmeticError) as exc:
        errors.append(str(exc));rows.clear()
    return dict(kind=kind,floor_id=data.get('floor_id') if isinstance(data,dict) else None,
                system_id=data.get('system_id') if isinstance(data,dict) else None,
                source_id=source.get('source_id') if isinstance(source,dict) else None,
                ready=not errors,blockers=errors,rows=rows,preview_only=True)


def remap_copy(data,replacements):
    a=data['architecture_detail'];a['geometry']['physical_surface_id']='SC-'+uuid4().hex
    for group in a['groups'].values():
        for row in group['items']:
            if row.get('rail_id'):row['rail_id']=replacements.get(row['rail_id'],row['rail_id'])
            for key in ('main_id','cross_id'):
                if key in row:row[key]=replacements.get(row[key],row[key])


@exact
def guard(project):
    """Conservatively block identical ceiling material coverage and unknown history."""
    from core.takeoff.manual_formula_amendments import beam_current
    from core.takeoff.paint_finish_detail import is_paint,_areas as paint_areas
    from core.takeoff.interior_cover_detail import is_cover,rect as cover_rect
    register=project.get('reviewed_aec_systems',{});ceilings=[];others=[];legacy=[]
    for key,record in register.items():
        d=record.get('data',{});a=d.get('architecture_detail',{});g=a.get('geometry',{})
        if is_ceiling(d):
            d=beam_current(project,key)['data'];g=d['architecture_detail']['geometry'];ceilings.append((d,g,(Decimal(0),Decimal(0),number(g['length_m'],'طول'),number(g['width_m'],'عرض'))))
        elif is_paint(d):
            d=beam_current(project,key)['data'];pg,z,_,_,_=paint_areas(d,require_approval=False)
            if pg['face']=='ceiling':others.extend((d,pg,zv[1]) for zv in z.values())
        elif is_cover(d) and g.get('face')=='ceiling':
            d=beam_current(project,key)['data'];g=d['architecture_detail']['geometry'];L,W=number(g['length_m'],'طول'),number(g['width_m'],'عرض')
            others.extend((d,g,cover_rect(v,L,W)) for v in d['architecture_detail']['surfaces'])
        elif d.get('kind')=='suspended_ceiling':legacy.append(d)
    for d,g,box in ceilings:
        for other,og,ob in ceilings+others:
            if other is d or other.get('building_id')!=d.get('building_id') or other.get('floor_id')!=d.get('floor_id'):continue
            if (other in (item[0] for item in ceilings) and
                    canonical(g['physical_surface_id'])==canonical(og.get('physical_surface_id')) and
                    (g['host_id']!=og.get('host_id') or g['face']!=og.get('face'))):
                raise ValueError('شناسه فیزیکی سقف به دو میزبان یا وجه متفاوت تخصیص یافته است')
            if g['host_id']!=og.get('host_id') or g['face']!=og.get('face'):continue
            for name in ('space_id','physical_surface_id','count','length_m','width_m','plane'):
                if name in og and og[name]!=g[name]:
                    raise ValueError('مالکیت یا هندسه مشترک سقف کاذب و پوشش دیگر ناسازگار است')
            if intersection(box,ob)>0:raise ValueError('دو پوشش سقف روی یک وجه فیزیکی تکرار شده‌اند')
        if any(v.get('floor_id')==d['floor_id'] for v in legacy):
            raise ValueError('سقف کاذب تاریخی فاقد هندسه یکتا است؛ مهاجرت خودکار ممنوع')
