"""Adapter of the unchanged Chat planar engine to the existing architecture ledger.

The integration accepts a shared horizontal base and local rectangular host.
Bounding-volume conflicts are deliberately conservative; no hidden tolerances.
"""
from copy import deepcopy
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4
from core.commercial.exact_values import exact,number
from core.takeoff.roof_detail import n,strict,checked,canonical,review_digest,validate_roof_source
from core.takeoff.reviewed_components import require_text
from core.takeoff.slope_planar_zones import calculate_planar_slope_zones,POLICY as ENGINE_POLICY
from core.takeoff.floor_detail import GEOMETRY as FLOOR_GEOMETRY

CONTRACT='planar_slope_aec_v1'
POLICY='architecture_specialist_v1'
GEOMETRY=FLOOR_GEOMETRY+('bottom_m','coordinate_frame_ref','material_ref','source_path','source_sha256','layer_key','payment_ref','interface_ref')
TABLES={'zones':('datum_ref','x_m','y_m','length_m','width_m','base_elevation_m','thickness_00_m','thickness_10_m','thickness_01_m'),'openings':('zone_id','x_m','y_m','length_m','width_m','penetration')}
TITLES={'zones':'نواحی شیب‌بندی و ترازهای مستند','openings':'بازشوهای تمام‌ضخامت هر ناحیه'}
LABELS={'slope_fill':'حجم خالص اجرای شیب‌بندی مستند'}
FIELD_LABELS={'coordinate_frame_ref':'مرجع دستگاه مختصات مشترک','source_path':'مسیر مدرک هندسه','source_sha256':'هش مدرک هندسه','interface_ref':'مدرک تطبیق میزبان و لایه‌های مجاور','datum_ref':'مرجع تراز زیرکار','x_m':'ابتدای طول (متر)','y_m':'ابتدای عرض (متر)','base_elevation_m':'تراز زیرکار (متر)','thickness_00_m':'ضخامت گوشه مبنا (متر)','thickness_10_m':'ضخامت گوشه راست (متر)','thickness_01_m':'ضخامت گوشه بالا (متر)','zone_id':'شناسه ناحیه مالک بازشو','gross_volume_m3':'حجم ناخالص (متر مکعب)','deducted_volume_m3':'حجم کسرشده (متر مکعب)','region_id':'شناسه ناحیه','coordinate_unit':'واحد مختصات','elevation_unit':'واحد تراز'}
VALUES={'full_depth':'نافذ تمام ضخامت'}
CHOICES={'penetration':('full_depth',)}

def is_slope(d):return d.get('architecture_detail',{}).get('contract')==CONTRACT

def no_float(value):
 if isinstance(value,float):raise ValueError('float در قرارداد دقیق شیب‌بندی مجاز نیست')
 if isinstance(value,dict):
  for v in value.values():no_float(v)
 elif isinstance(value,list):
  for v in value:no_float(v)

def document(g):
 path=Path(require_text(g.get('source_path'),'مسیر مدرک هندسه'));h=sha256()
 with path.open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 if h.hexdigest()!=g.get('source_sha256'):raise ValueError('هش مدرک هندسه با فایل واقعی تطبیق ندارد')

def engine_input(d):
 a=d['architecture_detail'];g=a['geometry'];zones=[];ids=set();physical=set();sources={canonical(g.get('source_ref'))}
 for name,fields in TABLES.items():
  if not isinstance(a.get(name),list) or len(a[name])>128:raise ValueError('جدول مستقل و محدود شیب‌بندی لازم است')
  for p in a[name]:
   strict(p,('id','physical_key','source_ref','approved_by')+fields,'جزء شیب‌بندی');checked(p)
   for key,seen in [('id',ids),('physical_key',physical),('source_ref',sources)]:
    v=canonical(p.get(key))
    if v in seen or key=='id' and '|' in p[key]:raise ValueError('شناسه فیزیکی یا منبع جزء تکراری است')
    seen.add(v)
 for z in a['zones']:
  p={k:v for k,v in z.items() if k!='id'};p['region_id']=z['id'];p['openings']=[]
  if number(z['base_elevation_m'],'تراز',negative=True)!=number(g['base_level_m'],'تراز مشترک',negative=True)+n(g['bottom_m'],'ابتدای شیب‌بندی',True):raise ValueError('این اتصال فقط زیرکار افقی مشترک مستند را می‌پذیرد')
  x,y,L,W=[n(z[k],k,k in ('x_m','y_m')) for k in ('x_m','y_m','length_m','width_m')]
  if x+L>n(g['length_m'],'طول میزبان') or y+W>n(g['width_m'],'عرض میزبان'):raise ValueError('ناحیه خارج از میزبان مستند است')
  for h in a['openings']:
   if h['zone_id']==z['id']:p['openings'].append({k:v for k,v in h.items() if k not in ('zone_id','approved_by')})
  zones.append(p)
 if any(h['zone_id'] not in {z['id'] for z in a['zones']} for h in a['openings']):raise ValueError('ناحیه مالک بازشو موجود نیست')
 return dict(policy=ENGINE_POLICY,surface_id=g['physical_region_id'],coordinate_frame_ref=g['coordinate_frame_ref'],source_ref=g['source_ref'],source_sha256=g['source_sha256'],approved_by=g['approved_by'],material_ref=g['material_ref'],coordinate_unit=g['unit'],elevation_unit=g['unit'],zones=zones)

@exact
def preview(data,engine,require_review=False):
 rows=[];errors=[];source=data.get('source',{})
 try:
  no_float(data)
  if data.get('kind')!='floor_finish' or data.get('measurement_policy')!=POLICY or not is_slope(data):raise ValueError('قرارداد تخصصی شیب‌بندی معتبر نیست')
  strict(data,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','architecture_detail','roof_review'),'شیب‌بندی')
  for k in ('building_id','floor_id','system_id','axis'):require_text(data.get(k),'هویت و موقعیت')
  validate_roof_source(source,data['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(p!={'status':'unreviewed'} for p in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی هم‌زمان ممنوع است')
  a=data['architecture_detail'];strict(a,('contract','geometry','zones','openings'),'دیتایل شیب‌بندی');g=a['geometry'];strict(g,GEOMETRY+('unit',),'هندسه میزبان')
  for k in GEOMETRY:require_text(g.get(k),FIELD_LABELS.get(k,k))
  checked(g)
  if g['unit']!='m' or g['shape']!='rectangle':raise ValueError('میزبان این قرارداد فقط مستطیلی و بر حسب متر است')
  count=n(g['count'],'تعداد مستقل',integer=True);document(g);out=calculate_planar_slope_zones(engine_input(data));out['source_sha256_verified']=True
  for z in out['zones']:
   params={**deepcopy(g),**deepcopy(z),'source_sha256_verified':True,**{'thickness_'+key[1:]+'_m':value for key,value in z['corner_thickness_m'].items()}}
   rows.append(dict(source_id=f"aec:floor_finish:{data['floor_id']}:{data['system_id']}:{z['region_id']}",line_id=z['region_id'],item_code='slope_fill',quantity=format(Decimal(z['net_volume_m3'])*count,'f'),unit='m3',domain='building',description=LABELS['slope_fill']+' '+data['system_id'],formula='تعداد مستند × (انتگرال ضخامت صفحه روی مستطیل − جمع حجم بازشوها با ضخامت مرکز هر بازشو)',params=params,component='slope_fill',method=CONTRACT,source_ref=z['source_ref'],role='work'))
  if require_review or 'roof_review' in data:
   rv=data.get('roof_review',{});reviewer=canonical(rv.get('reviewer'));require_text(rv.get('note'),'یادداشت بازبینی')
   if reviewer in {canonical(p['approved_by']) for p in [g]+a['zones']+a['openings']}:raise ValueError('بازبین شیب‌بندی باید مستقل از تأییدکنندگان دیتایل باشد')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OSError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=data.get('kind'),floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

def remap_copy(d,replacements):
 a=d['architecture_detail'];a['geometry']['physical_region_id']='SL-'+uuid4().hex;a['geometry']['layer_key']='SLAYER-'+uuid4().hex
 for h in a['openings']:h['zone_id']=replacements.get(h['zone_id'],h['zone_id'])

def validate_amendment(before,after):
 for k in ('layer_key','coordinate_frame_ref','space_id'):
  if before['architecture_detail']['geometry'].get(k)!=after['architecture_detail']['geometry'].get(k):raise ValueError('تغییر هویت لایه، فضا یا دستگاه مختصات در اصلاحیه ممنوع است')

@exact
def guard(project):
 from core.takeoff.manual_formula_amendments import beam_current
 from core.takeoff.architecture_detail import rect,intersection
 register=project.get('reviewed_aec_systems',{});records=[beam_current(project,k)['data'] for k,r in register.items() if r.get('data',{}).get('measurement_policy')==POLICY]
 slopes=[d for d in records if is_slope(d)]
 if not slopes:return
 physical={};scopes={};boxes={};hosts={};frames={}
 for d in records:
  a=d.get('architecture_detail',{});g=a.get('geometry',{});b=canonical(d['building_id'])
  for table in ('zones','openings','layers','surfaces','stocks','pieces','runs','corners','joints'):
   for p in a.get(table,[]):
    if p.get('physical_key'):
     pk=(b,canonical(p['physical_key']))
     if pk in physical and (is_slope(d) or physical[pk]):raise ValueError('هویت جزء شیب‌بندی در رکورد دیگری تکراری است')
     physical[pk]=is_slope(d)
  if not g.get('physical_region_id'):continue
  scope=(b,canonical(g['physical_region_id']));hosts.setdefault(scope,[]).append((d,a,g))
  if not is_slope(d):
   for p in a.get('layers',[]):
    if all(p.get(k) not in ('',None) for k in ('x','y','width_m','height_m','bottom_m','thickness_m')):
     bb=rect(p,n(g['length_m'],'طول'),n(g['width_m'],'عرض'));bottom=number(g['base_level_m'],'تراز',negative=True)+n(p['bottom_m'],'ابتدا',True);boxes.setdefault(scope,[]).append((bb,bottom,bottom+n(p['thickness_m'],'ضخامت')))
 for d in slopes:
  a=d['architecture_detail'];g=a['geometry'];scope=(canonical(d['building_id']),canonical(g.get('physical_region_id')))
  if 'roof_review' in d:
   r=preview(d,None)
   if not r['ready']:raise ValueError('؛ '.join(r['blockers']))
  frame=canonical(g.get('coordinate_frame_ref'))
  if scope in frames and frames[scope]!=frame:raise ValueError('دستگاه مختصات شیب‌بندی‌های یک میزبان ناسازگار است')
  frames[scope]=frame
  for z in a.get('zones',[]):
   fields=('x_m','y_m','length_m','width_m','base_elevation_m','thickness_00_m','thickness_10_m','thickness_01_m')
   if not all(z.get(k) not in ('',None) for k in fields):continue
   x,y,L,W=[n(z[k],k,k in ('x_m','y_m')) for k in fields[:4]];bb=(x,y,x+L,y+W);bottom=number(z['base_elevation_m'],'تراز',negative=True);t=[n(z[k],k,True) for k in fields[5:]];top=bottom+max(*t,t[1]+t[2]-t[0])
   if any(intersection(bb,old)>0 and min(top,end)>max(bottom,start) for old,start,end in boxes.get(scope,[])):raise ValueError('حجم شیب‌بندی با کف، عایق یا شیب‌بندی قبلی تداخل دارد؛ رفع ابهام هندسی لازم است')
   boxes.setdefault(scope,[]).append((bb,bottom,top))
   lk=scope+(canonical(g.get('layer_key')),)
   if lk in scopes and scopes[lk]!=d['system_id']:raise ValueError('لایه شیب‌بندی در چند برداشت تکراری است')
   scopes[lk]=d['system_id']
   holes=[(n(h['x_m'],'طول',True),n(h['y_m'],'عرض',True),n(h['x_m'],'طول',True)+n(h['length_m'],'طول'),n(h['y_m'],'عرض',True)+n(h['width_m'],'عرض')) for h in a.get('openings',[]) if h.get('zone_id')==z['id']]
   for other,old,og in hosts.get(scope,[]):
    if is_slope(other):continue
    for h in old.get('openings',[]):
     hb=rect(h,n(og['length_m'],'طول'),n(og['width_m'],'عرض'));clip=(max(bb[0],hb[0]),max(bb[1],hb[1]),min(bb[2],hb[2]),min(bb[3],hb[3]));required=intersection(bb,hb)
     if required>0 and sum((intersection(clip,v) for v in holes),Decimal(0))!=required:raise ValueError('بازشوی میزبان ثبت‌شده از شیب‌بندی مرتبط کسر نشده است')
