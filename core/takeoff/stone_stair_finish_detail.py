"""Read-only documented stair-stone tread/riser/landing takeoff in stone_floor.

No guessed step dimensions, piece counts, waste, mortar mix, stair geometry or
structural ownership. Only installed stone faces may be paid; purchase and
material breakdown are informational. Rectangular isolated faces only.
"""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from core.commercial.exact_values import exact, wire
from core.takeoff.roof_detail import strict, checked, canonical, review_digest, validate_roof_source, n as _n
from core.takeoff.reviewed_components import require_text
from core.takeoff.architecture_detail import POLICY, COMMON, intersection, area

CONTRACT = 'stone_stair_rectangular_v1'
GEOMETRY = ('physical_stair_id','host_id','unit','count','repeat_ref','source_ref','approved_by')
STEP = ('tread_face_id','riser_face_id','riser_status','riser_reason')
FACE = ('step_id','face_kind','length_m','width_m','material_ref','payment_ref',
        'layout_status','layout_ref')
OPENING = ('face_id','x','y','width_m','height_m')
STOCK = ('length_m','width_m','material_ref')
PIECE = ('face_id','stock_id','piece_type','x','y','width_m','height_m',
         'stock_x','stock_y','cut_ref')
JOINT = ('face_id','x','y','width_m','height_m')
CONSUMPTION = ('face_id','operation','basis','thickness_m','rate','rate_ref',
               'material_ref','quantity_unit')
TABLES = {'steps': STEP,'faces': FACE,'openings': OPENING,'stocks': STOCK,
          'pieces': PIECE,'joints': JOINT,'consumptions': CONSUMPTION}
LABELS = {'tread':'سنگ کف‌پله', 'riser':'سنگ پیشانی پله','landing':'سنگ پاگرد',
          'installed_pieces':'تعداد قطعات نصب‌شده؛ اطلاعاتی',
          'purchase_stocks':'قطعات خرید واقعی؛ اطلاعاتی',
          'offcut_area':'مساحت باقیمانده برش واقعی؛ اطلاعاتی',
          'bedding':'ملات نصب مستند؛ اطلاعاتی','adhesive':'چسب نصب مستند؛ اطلاعاتی',
          'grout':'بندکشی مستند؛ اطلاعاتی'}


def is_stair_stone(data):
    return isinstance(data,dict) and data.get('kind')=='stone_floor' and isinstance(data.get('architecture_detail'),dict) and data['architecture_detail'].get('contract')==CONTRACT


def n(value, label, zero=False, integer=False):
    if isinstance(value,(bool,float)):
        raise ValueError(label+': float یا boolean معتبر نیست؛ مقدار دقیق مستند لازم است')
    return _n(value,label,zero=zero,integer=integer)


def block(p,L,H):
    x=n(p.get('x'),'مبدأ X',zero=True);y=n(p.get('y'),'مبدأ Y',zero=True)
    width=n(p.get('width_m'),'عرض قطعه');height=n(p.get('height_m'),'ارتفاع قطعه')
    if x+width>L or y+height>H:raise ValueError('قطعه یا بازشو بیرون وجه سنگی است')
    return (x,y,x+width,y+height)


def identity(p,fields,used,physical):
    strict(p,COMMON+fields,'جزء مستقل سنگ پله');checked(p)
    sid=canonical(p['id']);ph=canonical(p['physical_key'])
    if '|' in p['id'] or sid in used or ph in physical:
        raise ValueError('هویت فیزیکی یا شناسه قطعه سنگ پله تکراری است')
    used.add(sid);physical.add(ph)


def emit(rows,data,code,q,unit,ident,source_ref,role,params,formula,count):
    if role=='material' and q==0:return
    rows.append(dict(source_id=f"aec:stone_floor:{data['floor_id']}:{data['system_id']}:{ident}",
                     line_id=ident,item_code=code,quantity=wire(q*count),unit=unit,
                     domain='building',description=LABELS[code]+' '+data['system_id'],
                     formula='تعداد مستقل مستند × ('+formula+')',
                     params=wire(deepcopy(params)),component=code,method=POLICY,
                     source_ref=source_ref,role=role))


@exact
def preview(data,engine,require_review=False):
    errors=[];rows=[];source=data.get('source',{}) if isinstance(data,dict) else {}
    try:
        if not is_stair_stone(data) or data.get('measurement_policy')!=POLICY:
            raise ValueError('زیرقرارداد تخصصی سنگ پله لازم است')
        strict(data,('kind','floor_id','system_id','building_id','axis','source',
                     'measurement_policy','components','architecture_detail','roof_review'),'سنگ پله')
        for key in ('floor_id','system_id','building_id','axis'):require_text(data[key],'هویت پروژه')
        validate_roof_source(source,data['system_id'])
        for key in ('plan_ref','detail_ref'):require_text(source.get(key),'مدرک نقشه یا دیتایل')
        if any(v!={'status':'unreviewed'} for v in data['components'].values()):
            raise ValueError('محاسبه عمومی و تخصصی سنگ پله قابل جمع نیستند')
        a=data['architecture_detail'];strict(a,('contract','geometry')+tuple(TABLES),'دیتایل سنگ پله')
        g=a['geometry'];strict(g,GEOMETRY,'هندسه میزبان پله');checked(g)
        for key in ('physical_stair_id','host_id','repeat_ref'):require_text(g[key],'شناسه فیزیکی و تکرار')
        if g['unit']!='m':raise ValueError('همه ابعاد سنگ پله باید متر باشند')
        count=n(g['count'],'تعداد پله‌های فیزیکی مستقل و همسان',integer=True)
        if count != 1:raise ValueError('تکرار چند پله نیازمند هویت فیزیکی مستقل برای هر نمونه است')
        ids=set();physical=set()
        for name,fields in TABLES.items():
            value=a[name]
            if not isinstance(value,list) or len(value)>512:
                raise ValueError(name+': جدول صریح و محدود لازم است')
            for item in value:identity(item,fields,ids,physical)
        if not a['steps'] or not a['faces']:
            raise ValueError('کف‌پله و دیتایل نصب سنگ باید صریح باشند')
        steps={p['id']:p for p in a['steps']}
        faces={p['id']:p for p in a['faces']}
        for sid,step in steps.items():
            tid=step['tread_face_id'];rid=step['riser_face_id'];status=step['riser_status']
            if tid not in faces or faces[tid]['step_id']!=sid or faces[tid]['face_kind']!='tread':
                raise ValueError('کف‌پله باید دقیقاً به وجه مستند متعلق به همان پله وصل باشد')
            if status=='covered':
                if rid not in faces or faces[rid]['step_id']!=sid or faces[rid]['face_kind']!='riser' or step['riser_reason'] not in ('',None):
                    raise ValueError('پیشانی پوشش‌دار نیازمند وجه مستقل و بدون تناقض است')
            elif status=='not_applicable':
                if rid!='none':raise ValueError('پیشانی بدون سنگ نباید وجه پوشش داشته باشد')
                require_text(step['riser_reason'],'علت عدم کاربرد سنگ پیشانی')
            else:raise ValueError('وضعیت سنگ پیشانی مجهول است')
        related=set()
        for p in a['steps']:
            related.add(p['tread_face_id'])
            if p['riser_status']=='covered':related.add(p['riser_face_id'])
        net={};holes={};units={};bounds={}
        for fid,face in faces.items():
            face_kind=face['face_kind'];sid=face['step_id']
            if face_kind=='landing':
                if sid!='none':raise ValueError('پاگرد به شناسه پله ساختگی منتسب نشود')
            elif face_kind not in ('tread','riser') or fid not in related:
                raise ValueError('وجه سنگی فاقد پیوند یکتا با کف‌پله یا پیشانی است')
            for key in ('material_ref','payment_ref','layout_ref'):require_text(face[key],'مدرک سنگ اجرا')
            if face['layout_status']!='documented':
                raise ValueError('سنگ پله فقط با جانمایی واقعی قطعات معتبر است')
            L=n(face['length_m'],'طول وجه سنگی');W=n(face['width_m'],'عرض وجه سنگی')
            bounds[fid]=(L,W);holes[fid]=[]
            for h in a['openings']:
                if h['face_id']!=fid:continue
                b=block(h,L,W)
                if any(intersection(b,old)>0 for old in holes[fid]):raise ValueError('بازشوهای یک وجه هم‌پوشانی دارند')
                holes[fid].append(b)
            q=L*W-sum((area(h) for h in holes[fid]),Decimal(0))
            if q<=0:raise ValueError('مساحت خالص وجه سنگی باید مثبت باشد')
            net[fid]=q;units[fid]=face_kind
        if related != {fid for fid,f in faces.items() if f['face_kind'] in ('tread','riser')}:
            raise ValueError('وجه کف‌پله/پیشانی بدون شناسنامه یکتا موجود است')
        for h in a['openings']:
            if h['face_id'] not in faces:raise ValueError('بازشو با وجه ناشناخته مرتبط است')
        stocks={};stock_boxes={}
        for p in a['stocks']:
            stocks[p['id']]=(p,n(p['length_m'],'طول سنگ خرید'),n(p['width_m'],'عرض سنگ خرید'))
            require_text(p['material_ref'],'مرجع مصالح خرید واقعی')
            stock_boxes[p['id']]=[]
        face_boxes={fid:[] for fid in faces};material_sums={fid:[] for fid in faces}
        for name in ('pieces','joints'):
            for p in a[name]:
                fid=p['face_id']
                if fid not in faces:raise ValueError('قطعه یا بند روی وجه ناموجود است')
                L,W=bounds[fid];b=block(p,L,W)
                if any(intersection(b,h)>0 for h in holes[fid]) or any(intersection(b,v)>0 for v in face_boxes[fid]):
                    raise ValueError('قطعه سنگ یا بند با بازشو یا قطعه دیگر هم‌پوشانی دارد')
                face_boxes[fid].append(b)
                if name=='joints':continue
                if p['stock_id'] not in stocks or p['piece_type'] not in ('full','cut'):
                    raise ValueError('قطعه خرید و وضعیت برش مستند لازم است')
                stock,sl,sw=stocks[p['stock_id']]
                if stock['material_ref']!=faces[fid]['material_ref']:
                    raise ValueError('سنگ نصب‌شده با مصالح خرید یکی نیست')
                require_text(p['cut_ref'],'مرجع برش قطعه سنگ')
                cut=block(dict(x=p['stock_x'],y=p['stock_y'],width_m=p['width_m'],height_m=p['height_m']),sl,sw)
                if any(intersection(cut,v)>0 for v in stock_boxes[p['stock_id']]):
                    raise ValueError('یک قطعه خرید چند بار برش خورده است')
                if (p['piece_type']=='full')!=(cut==(Decimal(0),Decimal(0),sl,sw)):
                    raise ValueError('نوع برش با ابعاد واقعی سنگ خرید سازگار نیست')
                stock_boxes[p['stock_id']].append(cut);material_sums[fid].append(b)
        for fid,face in faces.items():
            if not material_sums[fid] or sum((area(b) for b in face_boxes[fid]),Decimal(0))!=net[fid]:
                raise ValueError('سنگ‌ها و بندها سطح خالص هر وجه را دقیقاً نمی‌پوشانند')
            emit(rows,data,face['face_kind'],net[fid],'m2',fid,face['source_ref'],
                 'work',dict(face_id=fid,physical_stair_id=g['physical_stair_id'],
                             host_id=g['host_id'],net_area_m2=net[fid]),
                 'سطح واقعی وجه − بازشوها؛ خرید و قطعات اطلاعاتی‌اند',count)
            pieces=[p for p in a['pieces'] if p['face_id']==fid]
            emit(rows,data,'installed_pieces',Decimal(len(pieces)),'عدد',fid+'-pieces',face['source_ref'],
                 'material',dict(face_id=fid,piece_ids=[p['id'] for p in pieces]),
                 'شمارش واقعی قطعات جانمایی‌شده؛ بدون حدس',count)
        for sid,(stock,L,W) in stocks.items():
            cuts=stock_boxes[sid]
            if not cuts:raise ValueError('سنگ خرید بدون قطعه نصب‌شده پذیرفته نیست')
            emit(rows,data,'purchase_stocks',Decimal(1),'عدد',sid+'-stock',stock['source_ref'],
                 'material',dict(stock_id=sid),'یک قطعه واقعی خرید',count)
            emit(rows,data,'offcut_area',L*W-sum((area(v) for v in cuts),Decimal(0)),
                 'm2',sid+'-offcut',stock['source_ref'],'material',dict(stock_id=sid),
                 'مساحت قطعه خرید منهای قطعات برش‌خورده واقعاً جانمایی‌شده',count)
        used=set()
        for p in a['consumptions']:
            fid=p['face_id'];operation=p['operation']
            if fid not in faces or operation not in ('bedding','adhesive','grout') or (fid,operation) in used:
                raise ValueError('مصالح نصب تکراری یا فاقد وجه معتبر است')
            used.add((fid,operation))
            require_text(p['material_ref'],'مرجع مصالح نصب');require_text(p['rate_ref'],'مرجع مصرف')
            q=net[fid]
            if operation=='grout':
                q=sum((area(block(j,*bounds[fid])) for j in a['joints'] if j['face_id']==fid),Decimal(0))
                if q<=0:raise ValueError('بندکشی بدون ناحیه بند مستند ممنوع است')
            if p['basis']=='constant_thickness' and p['quantity_unit']=='m3' and p['rate'] in ('',None):
                q*=n(p['thickness_m'],'ضخامت ملات')
            elif p['basis']=='area_rate' and p['quantity_unit']=='kg' and p['thickness_m'] in ('',None):
                q*=n(p['rate'],'مصرف ماده')
            else:raise ValueError('مبنای مصرف و واحد مصالح نامعتبر است')
            emit(rows,data,operation,q,p['quantity_unit'],p['id'],p['source_ref'],
                 'material',dict(face_id=fid,material_ref=p['material_ref'],rate_ref=p['rate_ref']),
                 'سطح خالص مستند × ضخامت یا نرخ مصرف دقیق',count)
        if require_review:
            rv=data.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین مستقل')
            require_text(rv.get('note'),'یادداشت بازبین')
            if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
            reviewer=canonical(rv['reviewer'])
            approvers=[source.get('approved_by'),g['approved_by']]
            approvers.extend(p.get('approved_by') for name in TABLES for p in a[name])
            if any(reviewer==canonical(a) for a in approvers if a):
                raise ValueError('بازبین سنگ پله نمی‌تواند تأییدکننده دیتایل خودش باشد')
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,ArithmeticError) as exc:
        errors.append(str(exc));rows.clear()
    return dict(kind='stone_floor',floor_id=data.get('floor_id'),system_id=data.get('system_id'),
                source_id=source.get('source_id'),ready=not errors,blockers=errors,
                rows=rows,preview_only=True)


def remap_copy(data,replacements):
    a=data['architecture_detail'];a['geometry']['physical_stair_id']='SS-'+uuid4().hex
    a['geometry']['host_id']='SH-'+uuid4().hex
    # Ordinary copy adapter remaps item IDs/references. No approval is carried.
    for p in a['steps']:
        p['tread_face_id']=replacements.get(p['tread_face_id'],p['tread_face_id'])
        if p['riser_face_id']!='none':p['riser_face_id']=replacements.get(p['riser_face_id'],p['riser_face_id'])
    for table in ('faces','openings','pieces','joints','consumptions'):
        for p in a[table]:
            for key in ('step_id','face_id','stock_id'):
                if key in p and p[key]!='none':p[key]=replacements.get(p[key],p[key])


@exact
def guard(project):
    """Reject repeated stair-stone assets or pieces and ambiguous old claims."""
    from core.takeoff.manual_formula_amendments import beam_current
    from core.takeoff.interior_cover_detail import is_cover
    register=project.get('reviewed_aec_systems',{});stair_owners={};pieces=set();old_hosts=set()
    for key,record in register.items():
        d=record.get('data',{});g=d.get('architecture_detail',{}).get('geometry',{})
        if is_cover(d) and not is_stair_stone(d):
            if g.get('host_id'):old_hosts.add((canonical(d.get('building_id')),str(d.get('floor_id')),canonical(g['host_id'])))
    for key,record in register.items():
        d=record.get('data',{})
        if not is_stair_stone(d):continue
        d=beam_current(project,key)['data'];a=d['architecture_detail'];g=a['geometry']
        owner=(canonical(d['building_id']),str(d['floor_id']))
        host=(owner[0],owner[1],canonical(g['host_id']))
        if host in old_hosts:raise ValueError('مالکیت سنگ کف و پله روی میزبان قدیمی نامعلوم است')
        ident=(owner[0],owner[1],canonical(g['physical_stair_id']))
        if ident in stair_owners:raise ValueError('یک پله فیزیکی دوبار سنگ‌کاری شده است')
        stair_owners[ident]=key
        for name in TABLES:
            for p in a.get(name,[]):
                ph=(owner[0],canonical(p.get('physical_key')))
                if ph in pieces:raise ValueError('سنگ یا قطعه فیزیکی در چند رکورد تکرار شده است')
                pieces.add(ph)
