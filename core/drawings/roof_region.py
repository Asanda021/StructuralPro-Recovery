"""PDF evidence adapter to the existing roof specialist, not a quantity engine.

A rectangle establishes only plan dimensions. Every material/detail remains an
explicit, byte-bound schedule evaluated by roof_detail's existing formulas.
"""
from copy import deepcopy
from decimal import Decimal, localcontext
from hashlib import sha256
from pathlib import Path
import json

from core.drawings.takeoff_bridge import validate_session_payload, verified_measurement_identities, session_to_boq_rows
from core.drawings.takeoff_session import DrawingTakeoffSession
from core.commercial.exact_values import number

KINDS=('solid_slab','joist_block','joist_foam')
POLICY='pdf_roof_region_v1'


def detail_payload(data):
    return {key:deepcopy(data.get(key)) for key in ('kind','floor_id','system_id','building_id','roof_detail')}


def _rectangle(points):
    pts=[tuple(Decimal(str(v)) for v in p) for p in points]
    if len(pts)==5 and pts[0]==pts[-1]:pts.pop()
    if len(pts)!=4 or any(len(p)!=2 or not all(v.is_finite() for v in p) for p in pts):
        raise ValueError('قرارداد سقف به چهار رأس مستطیل معتبر نیاز دارد')
    xs=sorted({p[0] for p in pts});ys=sorted({p[1] for p in pts})
    if len(xs)!=2 or len(ys)!=2 or set(pts)!={(x,y) for x in xs for y in ys}:
        raise ValueError('ناحیه سقف باید مستطیلی و هم‌راستا با صفحه باشد')
    if any(a[0]!=b[0] and a[1]!=b[1] for a,b in zip(pts,pts[1:]+pts[:1])):
        raise ValueError('ترتیب رأس‌های مستطیل نامعتبر است')
    return xs,ys


def _identity(session,item):
    xs,ys=_rectangle(item['geometry'])
    # Independent of session counters, labels, selected family, code and scale.
    value=[session['source_sha256'],item['page'],[str(v.normalize()) for v in xs+ys]]
    return sha256(json.dumps(value,separators=(',',':')).encode()).hexdigest()


def bind_source(record,item_id):
    session=deepcopy(record['session'])
    if not validate_session_payload(session)['valid']:raise ValueError('نشست نقشه نامعتبر است')
    restored=DrawingTakeoffSession.from_dict(session);item=restored.find(item_id)
    if item.kind!='area':raise ValueError('برای سقف اندازه‌گیری سطح لازم است')
    if Path(session['drawing_source']).suffix.lower()!='.pdf':raise ValueError('این قرارداد مخصوص PDF است')
    rows=session_to_boq_rows(session,session_id=record['id'],selected_item_ids=[item_id]);verified_measurement_identities(record,rows)
    raw=item.to_dict();xs,ys=_rectangle(raw['geometry'])
    import fitz
    with fitz.open(session['drawing_source']) as pdf:
        import math
        page=pdf[item.page-1];w=math.ceil(page.rect.width*150/72);h=math.ceil(page.rect.height*150/72)
        if xs[0]<0 or ys[0]<0 or xs[1]>w or ys[1]>h:
            raise ValueError('محدوده سقف از تصویر صفحه در وضوح ثبت‌شده خارج است')
    fingerprint=_identity(session,raw)
    return {'mode':'drawing','source_id':'pdf-roof:'+fingerprint,'drawing_path':session['drawing_source'],
            'sha256':session['source_sha256'],'page':item.page,
            'selected_region':[float(xs[0]),float(ys[0]),float(xs[1]-xs[0]),float(ys[1]-ys[0])],
            'roof_binding':{'policy':POLICY,'session_id':record['id'],'revision':record['revision'],
                            'item_id':item_id,'identity':fingerprint,'session':session}}


def validate_source(source):
    b=source.get('roof_binding',{})
    if b.get('policy')!=POLICY:raise ValueError('قرارداد اتصال PDF سقف معتبر نیست')
    expected=bind_source({'id':b.get('session_id'),'revision':b.get('revision'),
                          'session':b.get('session',{}),'source_sha256':b.get('session',{}).get('source_sha256')},b.get('item_id'))
    for key in ('mode','source_id','drawing_path','sha256','page','selected_region','roof_binding'):
        if source.get(key)!=expected[key]:raise ValueError('منشأ یا کالیبراسیون ناحیه با نشست معتبر تطبیق ندارد')
    return b


def dimensions(source):
    b=validate_source(source);s=b['session']
    item=next(x for x in s['items'] if x['id']==b['item_id'])
    xs,ys=_rectangle(item['geometry']);cal=s['calibrations'][str(item['page'])]
    with localcontext() as ctx:
        ctx.prec=256
        factor=Decimal(str(cal['reference_meters']))/Decimal(str(cal['reference_pixels']))
        return ((xs[1]-xs[0])*factor,(ys[1]-ys[0])*factor)


def validate_detail(data):
    source=data['source'];b=validate_source(source)
    if data.get('kind') not in KINDS:raise ValueError('فقط سه سقف مصوب در اتصال PDF پشتیبانی می‌شوند')
    g=data.get('roof_detail',{}).get('geometry',{});length,width=dimensions(source)
    if number(g.get('length'),'طول سقف')!=length or number(g.get('width'),'عرض سقف')!=width or number(g.get('count'),'تعداد سقف')!=1:
        raise ValueError('ابعاد و تعداد سقف باید با همان یک ناحیه کالیبره‌شده تطبیق داشته باشد')
    path=Path(str(source.get('detail_path','')))
    if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=source.get('detail_sha256'):
        raise ValueError('فایل دیتایل و SHA-256 معتبر لازم است')
    def meaningful(v):
        if isinstance(v,dict):return {k:meaningful(x) for k,x in v.items() if x not in (None,'',[],{})}
        if isinstance(v,list):return [meaningful(x) for x in v]
        return v
    if meaningful(json.loads(path.read_text(encoding='utf-8-sig')))!=meaningful(detail_payload(data)):
        raise ValueError('محتوای دیتایل با ورودی جاری سقف مطابقت ندارد')
    # Holes must be independently represented in the schedule, not deducted twice.
    item=next(x for x in b['session']['items'] if x['id']==b['item_id'])
    factor=Decimal(str(b['session']['calibrations'][str(item['page'])]['meters_per_pixel']))
    outer_x,outer_y=_rectangle(item['geometry']);expected=[]
    for hole in item.get('holes',[]):
        xs,ys=_rectangle(hole)
        expected.append(((xs[0]-outer_x[0])*factor,(ys[0]-outer_y[0])*factor,
                         (xs[1]-xs[0])*factor,(ys[1]-ys[0])*factor))
    actual=[tuple(Decimal(str(p[k])) for k in ('x','y','length','width'))
            for p in data['roof_detail'].get('deductions',[]) if p.get('kind')=='opening']
    if sorted(actual)!=sorted(expected):raise ValueError('بازشوهای نقشه و کسورات دیتایل باید دقیقاً یکسان باشند')
    return b


def overlapping_pdf_roof_regions(first, second):
    """Positive AREA overlap of two PDF-bound, axis-aligned roof footprints.

    Borders touching is permitted. Same PDF bytes AND page are required; no
    automatic cross-page/floor aggregation or unreviewed polygon inference.
    A malformed stored rectangle is rejected, not silently treated as empty.
    """
    if not isinstance(first, dict) or not isinstance(second, dict):
        raise ValueError('منشأ ناحیه سقف ساختار معتبر ندارد')
    if first.get('sha256') != second.get('sha256') or first.get('page') != second.get('page'):
        return False

    def limits(source):
        rect = source.get('selected_region')
        if not isinstance(rect, (list, tuple)) or len(rect) != 4:
            raise ValueError('کادر ناحیه سقف در منشأ ذخیره‌شده نامعتبر است')
        try:
            x, y, width, height = (Decimal(str(value)) for value in rect)
        except (TypeError, ValueError, ArithmeticError) as exc:
            raise ValueError('مختصات ناحیه سقف عددی نیست') from exc
        if not all(v.is_finite() for v in (x, y, width, height)) or width <= 0 or height <= 0:
            raise ValueError('کادر ناحیه سقف باید مساحت مثبت و متناهی داشته باشد')
        return x, y, x + width, y + height

    ax0, ay0, ax1, ay1 = limits(first)
    bx0, by0, bx1, by1 = limits(second)
    return min(ax1, bx1) > max(ax0, bx0) and min(ay1, by1) > max(ay0, by0)


def project_gate(project,data,*,exclude=None):
    source=data.get('source',{})
    if not source.get('roof_binding'):return
    b=validate_source(source);current=(project.get('drawing_sessions') or {}).get(b['session_id'])
    if not current or current['revision']!=b['revision'] or json.dumps(current['session'],sort_keys=True)!=json.dumps(b['session'],sort_keys=True):
        raise RuntimeError('نسخه نشست نقشه کهنه است؛ ناحیه را بازگشایی و دوباره متصل کنید')
    session=b['session'];item=next(x for x in session['items'] if x['id']==b['item_id'])
    for key,record in (project.get('reviewed_aec_systems') or {}).items():
        if key==exclude:continue
        other_source=record.get('data',{}).get('source',{})
        other=other_source.get('roof_binding',{})
        if other.get('identity')==b['identity']:raise ValueError('همین محدوده سقف قبلاً به عضو دیگری تخصیص یافته است')
        if other and overlapping_pdf_roof_regions(source,other_source):
            raise ValueError('دو ناحیه سقف در یک صفحه PDF هم‌پوشانی مساحتی دارند؛ متره مضاعف ممنوع است')
    for row in project.get('takeoffs',[]):
        params=row.get('params') or {}
        if params.get('source_sha256')==session['source_sha256'] and params.get('page')==item['page'] and params.get('geometry'):
            if _identity(session,{'page':params['page'],'geometry':params['geometry']})==b['identity']:
                raise ValueError('ناحیه قبلاً از مسیر متره عمومی ثبت شده است؛ شمارش دوم ممنوع است')


def reject_reserved_regions(project,record,rows):
    identities={r.get('data',{}).get('source',{}).get('roof_binding',{}).get('identity')
                for r in (project.get('reviewed_aec_systems') or {}).values()}
    for row in rows:
        if row.get('kind')!='area':continue
        try:ident=_identity(record['session'],row)
        except ValueError:continue
        if ident in identities:raise ValueError('ناحیه به سقف تخصصی تخصیص یافته است؛ پرداخت سطح عمومی دوباره مجاز نیست')


def add_rectangular_opening(session,item_id,points,reference):
    """Edit the same area identity atomically; supported contained rectangles only."""
    from core.drawings.graphical_takeoff import Point, polygon_area
    from core.takeoff.reviewed_components import require_text
    reference=require_text(reference,'مرجع بازشو')
    item=session.find(item_id)
    if item.kind!='area':raise ValueError('بازشو فقط روی متره سطحی اعمال می‌شود')
    outer_x,outer_y=_rectangle(item.geometry);xs,ys=_rectangle(points)
    if not (outer_x[0]<=xs[0]<xs[1]<=outer_x[1] and outer_y[0]<=ys[0]<ys[1]<=outer_y[1]):
        raise ValueError('بازشو خارج از سطح مالک است')
    for hole in item.holes:
        hx,hy=_rectangle(hole)
        if min(xs[1],hx[1])>max(xs[0],hx[0]) and min(ys[1],hy[1])>max(ys[0],hy[0]):
            raise ValueError('بازشوی تکراری یا هم‌پوشان مجاز نیست')
    holes=tuple(item.holes)+(tuple(tuple(float(v) for v in p) for p in points),)
    net=polygon_area([Point(*p) for p in item.geometry])-sum(polygon_area([Point(*p) for p in h]) for h in holes)
    factor=session._factor_for(item.page);quantity=net*factor*factor
    if net<=0 or not Decimal(str(quantity)).is_finite() or quantity<=0:raise ValueError('مساحت خالص معتبر نیست')
    return session.edit(item_id,holes=holes,quantity=quantity,
                        formula=f'{net} px² × {factor}² | مرجع بازشو: {reference}')


def guard_project_change(previous,updated):
    """Reuse the existing ProjectStore invariant hook, including direct writes."""
    old_records=(previous or {}).get('reviewed_aec_systems',{})
    new_records=updated.get('reviewed_aec_systems',{})
    if not isinstance(old_records,dict) or not isinstance(new_records,dict):
        raise ValueError('ساختار دفتر سیستم‌های بازبینی‌شده نامعتبر است')
    seen=set()
    for key,record in new_records.items():
        old=old_records.get(key,{});data=record.get('data',{})
        old_source=old.get('data',{}).get('source',{});source=data.get('source',{})
        if old_source.get('roof_binding') and not source.get('roof_binding'):
            raise ValueError('حذف منشأ نقشه‌ای سقف یا تبدیل خاموش به متره دستی ممنوع است')
        binding=source.get('roof_binding')
        if not binding:continue
        ident=binding.get('identity')
        if ident in seen:raise ValueError('ناحیه سقف در دو رکورد تکرار شده است')
        seen.add(ident)
        if record!=old:
            project_gate(updated,data,exclude=key)
            if record.get('status')=='committed':validate_detail(data)
    for ident,am in (updated.get('beam_amendments') or {}).items():
        if am==((previous or {}).get('beam_amendments') or {}).get(ident):continue
        proposal=am.get('proposal') or {};base=new_records.get(am.get('beam_key'),{}).get('data',{})
        if base.get('source',{}).get('roof_binding'):
            if not proposal.get('source',{}).get('roof_binding'):raise ValueError('منشأ نقشه در اصلاحیه سقف باید حفظ شود')
            if not same_source_identity(base['source'],proposal['source']):raise ValueError('منشأ PDF در اصلاحیه باید ثابت بماند')
            evidence=am.get('evidence') or {}
            if proposal['source'].get('detail_sha256')!=evidence.get('evidence_sha256') or proposal['source'].get('detail_path')!=evidence.get('evidence_path'):raise ValueError('مدرک دیتایل با مدرک اصلاحیه یکسان نیست')
            project_gate(updated,proposal,exclude=am.get('beam_key'))


def same_source_identity(a,b):
    if not isinstance(a,dict) or not isinstance(b,dict):return a==b
    def identity(v):return {k:x for k,x in v.items() if k not in ('detail_path','detail_sha256')}
    return json.dumps(identity(a),sort_keys=True)==json.dumps(identity(b),sort_keys=True)
