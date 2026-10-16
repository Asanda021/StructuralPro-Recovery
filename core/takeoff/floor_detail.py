"""Documented constant rectangular floor strata inside the existing AEC contract.

No quantity, density, material consumption, purchasing allowance or price is
inferred. Different elevations are physical strata, not extra surface payments.
"""
from copy import deepcopy
from decimal import Decimal
from core.commercial.exact_values import exact,wire,number
from core.takeoff.architecture_detail import POLICY,COMMON,rect,area,intersection
from core.takeoff.roof_detail import n,strict,checked,canonical,review_digest,validate_roof_source
from core.takeoff.reviewed_components import require_text
KIND='floor_finish'
GEOMETRY=('physical_region_id','space_id','shape','length_m','width_m','base_level_m','level_ref','count','repeat_ref','source_ref','approved_by')
FIELDS=('layer_key','operation','method','x','y','width_m','height_m','bottom_m','thickness_m','material_ref','payment_unit','payment_ref','opening_ids','deduction_ref','coverage_scope','scope_ref','density_kg_m3','density_ref','purchase_quantity','purchase_unit','purchase_ref')
OPENINGS=('x','y','width_m','height_m','penetration')
LABELS={'floor_fill':'پوکه و پرکننده مستند','floor_screed':'ملات زیرکف و ترازکننده','floor_concrete':'بتن کف مستند','floor_subbase':'لایه زیرسازی کف','floor_separator':'لایه جداساز کف','floor_protection':'لایه محافظ کف','floor_purchase':'خرید مستند هر ناحیه؛ اطلاعاتی'}

@exact
def preview(data,engine,require_review=False):
 rows=[];errors=[];source=data.get('source',{})
 try:
  if data.get('kind')!=KIND or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد تخصصی کف معتبر نیست')
  strict(data,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','architecture_detail','roof_review'),'کف‌سازی')
  for k in ('building_id','floor_id','system_id','axis'):require_text(data.get(k),'هویت و موقعیت')
  validate_roof_source(source,data['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(p!={'status':'unreviewed'} for p in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی هم‌زمان ممنوع است')
  a=data['architecture_detail'];strict(a,('geometry','openings','layers'),'دیتایل کف');g=a['geometry'];strict(g,GEOMETRY+('unit',),'هندسه کف');checked(g)
  for k in ('physical_region_id','space_id','level_ref','repeat_ref'):require_text(g.get(k),'هویت ناحیه و مرجع تراز و تکرار')
  if g.get('unit')!='m' or g.get('shape')!='rectangle':raise ValueError('فقط ناحیه مستطیلی با ابعاد متر معتبر است')
  L,W=n(g.get('length_m'),'طول کف'),n(g.get('width_m'),'عرض کف');base=number(g.get('base_level_m'),'تراز مبنا',negative=True);count=n(g.get('count'),'تعداد مستقل',integer=True)
  ids=set();physical=set()
  def ident(p,fields):
   strict(p,COMMON+fields,'جزء کف');checked(p);i,pk=canonical(p.get('id')),canonical(p.get('physical_key'))
   if '|' in p['id'] or i in ids or pk in physical:raise ValueError('شناسه یا جزء فیزیکی کف تکراری است')
   ids.add(i);physical.add(pk)
  for name in ('openings','layers'):
   if not isinstance(a.get(name),list) or len(a[name])>512:raise ValueError('جدول مستقل محدود لازم است')
  if not a['layers']:raise ValueError('لایه مستقل کف نیازمند دیتایل است')
  holes={}
  for p in a['openings']:
   ident(p,OPENINGS)
   if p.get('penetration')!='all_layers':raise ValueError('فقط کسر مستطیلی تمام لایه‌های کف پشتیبانی می‌شود')
   b=rect(p,L,W)
   if any(intersection(b,v)>0 for v in holes.values()):raise ValueError('بازشوهای کف هم‌پوشان یا تکراری هستند')
   holes[p['id']]=b
  gross=L*W;net=gross-sum((area(b) for b in holes.values()),Decimal(0))
  if net<=0:raise ValueError('سطح خالص کف باید مثبت باشد')
  volumes=[];groups={}
  def emit(p,code,q,unit,suffix='',role='work'):
   i=p['id']+suffix;rows.append(dict(source_id=f"aec:{KIND}:{data['floor_id']}:{data['system_id']}:{i}",line_id=i,item_code=code,quantity=wire(q*count),unit=unit,domain='building',description=LABELS[code]+' '+data['system_id'],formula='تعداد صریح × '+('مقدار خرید واردشده و مستند هر ناحیه؛ بدون ضریب پرت خودکار' if role=='material' else 'سطح خالص مستقل'+(' × ضخامت ثابت مستند' if unit!='m2' else '')+(' × چگالی گواهی‌شده' if unit=='kg' else '')),params=wire(deepcopy(p)),component=code,method=POLICY,source_ref=p['source_ref'],role=role))
  for p in a['layers']:
   ident(p,FIELDS)
   for k in ('layer_key','material_ref','payment_ref','deduction_ref','scope_ref'):require_text(p.get(k),'هویت لایه و مرجع ماده، پرداخت و کسر')
   if p.get('operation') not in LABELS or p['operation']=='floor_purchase' or p.get('method')!='constant_rectangular':raise ValueError('نوع لایه یا روش ضخامت متغیر نیازمند قرارداد معتبر است')
   b=rect(p,L,W);bottom=n(p.get('bottom_m'),'ابتدای لایه از تراز مبنا',True);t=n(p.get('thickness_m'),'ضخامت ثابت لایه');top=bottom+t
   if any(intersection(b,box)>0 and min(top,end)-max(bottom,start)>0 for box,start,end in volumes):raise ValueError('لایه‌های کف از نظر حجم هم‌پوشانی دارند')
   volumes.append((b,bottom,top))
   if p.get('coverage_scope') not in ('complete','partial'):raise ValueError('محدوده لایه باید صریح باشد')
   links=p.get('opening_ids')
   if not isinstance(links,str):raise ValueError('شناسه بازشوهای مرتبط لازم است')
   linked=links.split('|') if links else [];actual={i for i,h in holes.items() if intersection(b,h)>0}
   if len(linked)!=len(set(linked)) or set(linked)!=actual:raise ValueError('لینک کسورات باید دقیقاً با بازشوهای متقاطع همین لایه برابر باشد')
   deduction=sum((intersection(b,holes[i]) for i in linked),Decimal(0));qarea=area(b)-deduction
   if qarea<=0:raise ValueError('سطح خالص لایه باید مثبت باشد')
   key=canonical(p['layer_key']);definition=tuple(str(p.get(k)) for k in ('operation','method','bottom_m','thickness_m','material_ref','payment_unit','payment_ref','density_kg_m3','density_ref','coverage_scope','scope_ref'))
   if key in groups and groups[key][0]!=definition:raise ValueError('تعریف قطعات یک لایه فیزیکی ناسازگار است')
   if key not in groups:groups[key]=[definition,Decimal(0),p['coverage_scope']]
   groups[key][1]+=qarea
   unit=p.get('payment_unit')
   if unit not in ('m2','m3','kg'):raise ValueError('واحد پرداخت کف معتبر نیست')
   q=qarea if unit=='m2' else qarea*t
   if unit=='kg':require_text(p.get('density_ref'),'مرجع چگالی');q*=n(p.get('density_kg_m3'),'چگالی مستند')
   elif p.get('density_kg_m3') or p.get('density_ref'):raise ValueError('چگالی فقط در مبنای وزنی پذیرفته است')
   params={**p,'gross_area_m2':area(b),'deducted_area_m2':deduction,'net_area_m2':qarea,'net_volume_m3':qarea*t,'bottom_level_m':base+bottom,'top_level_m':base+top,'repeat_count':count}
   emit(params,p['operation'],q,unit)
   purchase=tuple(p.get(k) for k in ('purchase_quantity','purchase_unit','purchase_ref'))
   if any(v not in ('',None) for v in purchase):
    if p.get('purchase_unit') not in ('m2','m3','kg'):raise ValueError('واحد خرید مستند معتبر نیست')
    require_text(p.get('purchase_ref'),'مدرک خرید مستقل هر ناحیه');emit(params,'floor_purchase',n(p.get('purchase_quantity'),'مقدار خرید مستند هر ناحیه'),p['purchase_unit'],'-purchase','material')
  if any(v[2]=='complete' and v[1]!=net for v in groups.values()):raise ValueError('لایه کامل اعلام‌شده تمام سطح خالص کف را نمی‌پوشاند')
  if len({canonical(v['source_id']) for v in rows})!=len(rows):raise ValueError('شناسه ردیف تولیدشده تکراری است')
  if require_review:
   rv=data.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین');require_text(rv.get('note'),'یادداشت')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=data.get('kind'),floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

@exact
def guard(project):
 from core.takeoff.manual_formula_amendments import beam_current
 register=project.get('reviewed_aec_systems',{});regions={};parts=set();boxes={};old_wall_ids=set();layer_defs={}
 for key,r in register.items():
  d=r.get('data',{})
  if d.get('measurement_policy')!=POLICY:continue
  d=beam_current(project,key)['data']
  a=d.get('architecture_detail',{});g=a.get('geometry',{})
  if g.get('physical_wall_id'):old_wall_ids.add((canonical(d.get('building_id')),canonical(g['physical_wall_id'])))
  for table in ('openings','masonry_layers','unit_regions','surfaces','layers'):
   for p in a.get(table,[]):
    if p.get('physical_key'):
     k=(canonical(d.get('building_id')),canonical(p['physical_key']))
     if k in parts:raise ValueError('جزء فیزیکی معماری در چند ناحیه تکراری است')
     parts.add(k)
 for key,r in register.items():
  if r.get('data',{}).get('measurement_policy')!=POLICY or r['data'].get('kind')!=KIND:continue
  d=beam_current(project,key)['data'];a=d['architecture_detail'];g=a['geometry'];region=(canonical(d.get('building_id')),canonical(g.get('physical_region_id')))
  if region in old_wall_ids:raise ValueError('هویت ناحیه کف با دیوار تداخل دارد')
  for other,v in register.items():
   old=v.get('data',{})
   if other!=key and old.get('kind')==KIND and old.get('measurement_policy')!=POLICY and old.get('floor_id')==d.get('floor_id') and old.get('system_id')==d.get('system_id'):raise ValueError('هویت تاریخی کف نیازمند مهاجرت صریح است')
  identity=tuple(str(d.get(k,'')) for k in ('floor_id','axis'))+tuple(str(g.get(k,'')) for k in ('space_id','length_m','width_m','base_level_m','count','repeat_ref'))
  if region in regions and regions[region]!=identity:raise ValueError('دامنه یا تراز ناحیه فیزیکی کف ناسازگار است')
  regions[region]=identity
  for p in a.get('layers',[]):
   if not all(p.get(k) not in ('',None) for k in ('x','y','width_m','height_m','bottom_m','thickness_m')):continue
   b=rect(p,n(g.get('length_m'),'طول'),n(g.get('width_m'),'عرض'));s=number(g.get('base_level_m'),'تراز',negative=True)+n(p['bottom_m'],'ابتدای لایه',True);e=s+n(p['thickness_m'],'ضخامت')
   if p.get('layer_key'):
    lk=region+(canonical(p['layer_key']),);definition=(s,e)+tuple(str(p.get(k,'')) for k in ('operation','material_ref','payment_unit','payment_ref','density_kg_m3','density_ref'))
    if lk in layer_defs and layer_defs[lk]!=definition:raise ValueError('یک لایه فیزیکی در چند رکورد تعریف ناسازگار دارد')
    layer_defs[lk]=definition
   if any(intersection(b,bb)>0 and min(e,ee)-max(s,ss)>0 for bb,ss,ee in boxes.get(region,[])):raise ValueError('یک حجم کف در چند رکورد دوباره شمرده شده است')
   boxes.setdefault(region,[]).append((b,s,e))
