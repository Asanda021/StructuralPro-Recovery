"""Exact predicates for the existing drawing session, not a takeoff engine.

Decimal coordinate literals are rational numbers; no epsilon is used for topology.
128 vertices/ring, 32 holes and 512 total vertices bound quadratic work. External
boundary-contact holes and disconnected interiors are intentionally unsupported.
"""
from decimal import Decimal, localcontext, Inexact
from fractions import Fraction as F
from math import isfinite

MAX_VERTICES=128
MAX_HOLES=32


def coordinate(value):
    if isinstance(value,bool):raise ValueError('مختصات منطقی معتبر نیست')
    try:d=Decimal(str(value))
    except Exception as e:raise ValueError('مختصات عددی معتبر نیست') from e
    if not d.is_finite() or len(d.as_tuple().digits)>32 or (d and (d.adjusted()>12 or d.adjusted() < -100)):
        raise ValueError('مختصات خارج از قرارداد دقت یا دامنه معتبر است')
    return F(d)


def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def on(a,b,p):return cross(a,b,p)==0 and all(min(a[i],b[i])<=p[i]<=max(a[i],b[i]) for i in (0,1))
def edges(r):return zip(r,r[1:]+r[:1])
def signed(r):return sum(a[0]*b[1]-b[0]*a[1] for a,b in edges(r))/2


def segments(a,b,c,d):
    x,y,u,v=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
    return (x*y<0 and u*v<0) or any((z==0 and on(p,q,t)) for z,p,q,t in ((x,a,b,c),(y,a,b,d),(u,c,d,a),(v,c,d,b)))


def ring(points):
    if not isinstance(points,(list,tuple)):raise ValueError('رأس‌ها باید آرایه صریح باشند')
    try:r=tuple((coordinate(p[0]),coordinate(p[1])) for p in points if len(p)==2)
    except Exception as e:raise ValueError('ساختار رأس‌های چندضلعی معتبر نیست') from e
    if len(r)!=len(points):raise ValueError('هر رأس به دو مختصات نیاز دارد')
    if len(r)>1 and r[0]==r[-1]:r=r[:-1]
    if not 3<=len(r)<=MAX_VERTICES or len(set(r))!=len(r):raise ValueError('تعداد یا تکرار رأس‌های چندضلعی نامعتبر است')
    n=len(r)
    for i,(a,b) in enumerate(edges(r)):
        for j,(c,d) in enumerate(edges(r)):
            if j<=i or j==i+1 or (i==0 and j==n-1):continue
            if segments(a,b,c,d):raise ValueError('چندضلعی خودمتقاطع یا دارای تماس نامعتبر است')
    for i,p in enumerate(r):
        a,b=r[i-1],r[(i+1)%n]
        if cross(a,p,b)==0 and not on(a,b,p):raise ValueError('ضلع برگشتی یا فروریخته معتبر نیست')
    r=tuple(p for i,p in enumerate(r) if cross(r[i-1],p,r[(i+1)%n])!=0)
    if len(r)<3 or signed(r)==0:raise ValueError('مساحت چندضلعی صفر است')
    return r if signed(r)>0 else r[::-1]


def canonical_ring(points):
    r=ring(points);i=min(range(len(r)),key=lambda k:r[k]);r=r[i:]+r[:i]
    return tuple((str(x),str(y)) for x,y in r)


def location(r,p):
    winding=0
    for a,b in edges(r):
        if on(a,b,p):return 0
        if a[1]<=p[1]<b[1] and cross(a,b,p)>0:winding+=1
        if b[1]<=p[1]<a[1] and cross(a,b,p)<0:winding-=1
    return 1 if winding else -1


def triangles(r):
    remaining=list(r);out=[]
    while len(remaining)>3:
        for i,b in enumerate(remaining):
            a,c=remaining[i-1],remaining[(i+1)%len(remaining)]
            if cross(a,b,c)<=0:continue
            if any(all(cross(u,v,p)>=0 for u,v in ((a,b),(b,c),(c,a))) for p in remaining if p not in (a,b,c)):continue
            out.append((a,b,c));remaining.pop(i);break
        else:raise ValueError('مثلث‌بندی دقیق هندسه ممکن نیست')
    return out+[tuple(remaining)]


def clipped_area(subject,clip):
    out=list(subject)
    for a,b in edges(clip):
        inp=out;out=[]
        if not inp:break
        for p,q in edges(inp):
            cp,cq=cross(a,b,p),cross(a,b,q)
            if cp>=0:out.append(p)
            if (cp<0 and cq>0) or (cp>0 and cq<0):
                t=cp/(cp-cq);out.append((p[0]+t*(q[0]-p[0]),p[1]+t*(q[1]-p[1])))
    return abs(signed(out)) if len(out)>=3 else F(0)


def intersection(a,b):
    if any(max(p[i] for p in a)<=min(p[i] for p in b) or max(p[i] for p in b)<=min(p[i] for p in a) for i in (0,1)):return F(0)
    return sum((clipped_area(x,y) for x in triangles(a) for y in triangles(b)),F(0))


def contact_components(a,b):
    """Number of disconnected boundary contacts between disjoint interiors."""
    if any(max(p[i] for p in a)<min(p[i] for p in b) or max(p[i] for p in b)<min(p[i] for p in a) for i in (0,1)):return 0
    pieces=[]
    for u,v in edges(a):
        for x,y in edges(b):
            if not segments(u,v,x,y):continue
            points=sorted(set(p for p in (u,v,x,y) if on(u,v,p) and on(x,y,p)))
            if not points:raise ValueError('تقاطع مرزی بازشو معتبر نیست')
            pieces.append((points[0],points[-1]))
    parents=list(range(len(pieces)))
    def find(i):
        while parents[i]!=i:i=parents[i]
        return i
    for i,(u,v) in enumerate(pieces):
        for j,(x,y) in enumerate(pieces[:i]):
            if segments(u,v,x,y):parents[find(i)]=find(j)
    return len({find(i) for i in range(len(pieces))})


def region(outer,holes=()):
    outer=ring(outer)
    if len(holes)>MAX_HOLES or len(outer)+sum(len(h) for h in holes)>512:raise ValueError('هندسه از بودجه معتبر رأس یا بازشو بیشتر است')
    hs=[];parents=[]
    def find(i):
        while parents[i]!=i:i=parents[i]
        return i
    for h in holes:
        h=ring(h)
        if any(location(outer,p)!=1 for p in h) or any(segments(a,b,c,d) for a,b in edges(outer) for c,d in edges(h)):
            raise ValueError('بازشو باید کاملاً داخل مالک باشد؛ تماس با مرز خارجی پشتیبانی نمی‌شود')
        index=len(hs);parents.append(index)
        for j,old in enumerate(hs):
            if intersection(h,old)>0:raise ValueError('بازشوی تکراری یا هم‌پوشان مجاز نیست')
            contacts=contact_components(h,old)
            if contacts>1:raise ValueError('تماس جداگانه بازشوها می‌تواند جزیره بسازد؛ هندسه چندقسمتی پشتیبانی نمی‌شود')
            if contacts:
                if find(index)==find(j):raise ValueError('حلقه تماس بازشوها خارج از توپولوژی ساده پشتیبانی‌شده است')
                parents[find(index)]=find(j)
        hs.append(h)
    gross=abs(signed(outer));deduct=sum((abs(signed(h)) for h in hs),F(0))
    if gross<=deduct:raise ValueError('مساحت خالص مثبت نیست')
    return outer,hs,gross,deduct


def regions_overlap(a,ah,b,bh):
    a,ah,_,_=region(a,ah);b,bh,_,_=region(b,bh)
    if (len(ah)+1)*(len(bh)+1)>256:raise ValueError('تقاطع از بودجه معتبر بازشو بیشتر است؛ بازبینی لازم است')
    if sum((len(x)-2)*(len(y)-2) for x in [a]+ah for y in [b]+bh)>20000:raise ValueError('تقاطع از بودجه ۲۰۰۰۰ جفت مثلث بیشتر است؛ تقسیم‌بندی مستند لازم است')
    area=intersection(a,b)-sum((intersection(h,b) for h in ah),F(0))-sum((intersection(a,h) for h in bh),F(0))+sum((intersection(x,y) for x in ah for y in bh),F(0))
    return area>0


def decimal_text(value):
    with localcontext() as ctx:
        ctx.prec=256;ctx.traps[Inexact]=True
        try:return str(Decimal(value.numerator)/Decimal(value.denominator))
        except Exception as e:raise ValueError('مقدار دقیق خارج از قرارداد Decimal است') from e


def evidence(outer,holes,factor,refs=(),**identity):
    _,_,gross,deduct=region(outer,holes);scale=factor if isinstance(factor,F) else coordinate(factor)
    if scale<=0:raise ValueError('مقیاس معتبر نیست')
    if any(not isinstance(v,str) for v in identity.values()):raise ValueError('هویت طبقه، عضو و مالک باید متن صریح باشد')
    if len(refs)!=len(holes) or any(not isinstance(r,str) or not r.strip() for r in refs):raise ValueError('مرجع مستقل هر بازشو الزامی است')
    net=(gross-deduct)*scale*scale;text=decimal_text(net)
    display=float(text)
    if not isfinite(display) or display<=0:raise ValueError('مساحت غیرصفر خارج از دامنه نمایش معتبر است')
    return {'policy':'exact_simple_polygon_v1','gross_m2':decimal_text(gross*scale*scale),'deducted_m2':decimal_text(deduct*scale*scale),'net_m2':text,'opening_refs':list(refs),'coordinate_unit':'reference_pixel','meters_per_pixel':str(factor),**identity}
