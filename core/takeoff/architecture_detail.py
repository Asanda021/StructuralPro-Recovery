"""Explicit rectangular masonry partitions and independently documented finish faces.

Installed units use entered layouts, never an area ratio. Mortar is the exterior
joint volume, not a guessed recipe or filling of the unit's internal cavities.
"""
from copy import deepcopy
from decimal import Decimal
from core.commercial.exact_values import exact,wire
from core.takeoff.roof_detail import n,canonical,checked,strict,review_digest,validate_roof_source
from core.takeoff.reviewed_components import require_text
POLICY='architecture_specialist_v1'
KINDS=('block_wall','brick_wall','plaster_finish','floor_finish','waterproofing','thermal_insulation','acoustic_insulation','ceramic_finish','stone_floor','stone_cladding')
COMMON=('id','physical_key','source_ref','approved_by')
LABELS={'masonry_work':'دیوارچینی کامل','masonry_units':'واحد بنایی نصب‌شده؛ اطلاعات مصالح','mortar':'ملات بند بیرونی؛ اطلاعات مصالح','base_plaster':'گچ و خاک','white_plaster':'گچ سفید','cement_render':'اندود ماسه سیمان','levelling':'زیرسازی و تسطیح','protective':'پوشش محافظ'}
LAYER_FIELDS=('material_kind','offset_m','thickness_m','unit_length_m','unit_height_m','unit_depth_m','head_joint_m','bed_joint_m','unit_spec_ref','mortar_ref','payment_unit','payment_ref')
REGION_FIELDS=('layer_id','mode','x','y','width_m','height_m','nx','ny')
SURFACE_FIELDS=('surface_id','face','layer_code','x','y','width_m','height_m','thickness_m','material_ref','payment_unit','payment_ref','density_kg_m3','density_ref','opening_ids','deduction_ref','coverage_scope','scope_ref')
OPENING_FIELDS=('x','y','width_m','height_m','penetration')

def rect(p,L,H):
 x,y=n(p.get('x'),'ابتدای طول',True),n(p.get('y'),'ابتدای ارتفاع',True)
 w,h=n(p.get('width_m'),'عرض ناحیه'),n(p.get('height_m'),'ارتفاع ناحیه')
 if x+w>L or y+h>H:raise ValueError('ناحیه خارج از دیوار است')
 return x,y,x+w,y+h

def intersection(a,b):return max(Decimal(0),min(a[2],b[2])-max(a[0],b[0]))*max(Decimal(0),min(a[3],b[3])-max(a[1],b[1]))
def area(a):return (a[2]-a[0])*(a[3]-a[1])

def group(g,required=False):
 strict(g,('status','source_ref','approved_by','reason'),'وضعیت گروه');checked(g)
 if g.get('status')=='not_applicable' and not required:require_text(g.get('reason'),'علت عدم کاربرد');return False
 if g.get('status')!='confirmed':raise ValueError('نیازمند اطلاعات یا دیتایل مستقل است')
 return True

@exact
def preview(data,engine,require_review=False):
 from core.takeoff.slope_aec_detail import is_slope,preview as slope_preview
 if is_slope(data):return slope_preview(data,engine,require_review=require_review)
 from core.takeoff.skirting_detail import is_skirting,preview as skirt_preview
 if is_skirting(data):return skirt_preview(data,engine,require_review=require_review)
 from core.takeoff.interior_cover_detail import is_cover,preview as cover_preview
 if is_cover(data):return cover_preview(data,engine,require_review=require_review)
 if data.get('kind') in ('floor_finish','waterproofing','thermal_insulation','acoustic_insulation'):
  from core.takeoff.floor_detail import preview as floor_preview
  return floor_preview(data,engine,require_review=require_review,insulation=data.get('kind')!='floor_finish')
 rows=[];errors=[];source=data.get('source',{});kind=data.get('kind')
 try:
  if kind not in KINDS or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد تخصصی معماری معتبر نیست')
  strict(data,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','architecture_detail','roof_review'),'معماری')
  for k in ('building_id','floor_id','system_id','axis'):require_text(data.get(k),'هویت و موقعیت')
  validate_roof_source(source,data['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(p!={'status':'unreviewed'} for p in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی هم‌زمان ممنوع است')
  a=data['architecture_detail'];strict(a,('geometry','openings','masonry','masonry_layers','unit_regions','finishes','surfaces','accessories'),'دیتایل معماری')
  g=a['geometry'];strict(g,('physical_wall_id','unit','length_m','height_m','wall_thickness_m','count','repeat_ref','source_ref','approved_by'),'هندسه دیوار');checked(g)
  require_text(g.get('physical_wall_id'),'شناسه فیزیکی دیوار');require_text(g.get('repeat_ref'),'دامنه تکرار')
  if g.get('unit')!='m':raise ValueError('ابعاد این قرارداد فقط متر هستند')
  L,H,T=[n(g.get(k),'ابعاد دیوار') for k in ('length_m','height_m','wall_thickness_m')];count=n(g.get('count'),'تعداد مستقل',integer=True)
  ids=set();physical=set()
  def ident(p,fields):
   strict(p,COMMON+fields,'جزء معماری');checked(p)
   i,pk=canonical(p.get('id')),canonical(p.get('physical_key'))
   if '|' in p['id'] or i in ids or pk in physical:raise ValueError('شناسه یا جزء فیزیکی تکراری یا نامعتبر است')
   ids.add(i);physical.add(pk)
  def emit(code,q,unit,i,p,formula,role='work'):
   rows.append(dict(source_id=f"aec:{kind}:{data['floor_id']}:{data['system_id']}:{i}",line_id=i,item_code=code,quantity=wire(q*count),unit=unit,domain='building',description=LABELS[code]+' '+data['system_id'],formula='تعداد صریح × ('+formula+')',params=wire(deepcopy(p)),component=code,method=POLICY,source_ref=p['source_ref'],role=role))
  for k in ('openings','masonry_layers','unit_regions','surfaces'):
   if not isinstance(a.get(k),list) or len(a[k])>512:raise ValueError('جدول مستقل و محدود لازم است')
  holes={}
  for p in a['openings']:
   ident(p,OPENING_FIELDS)
   if p.get('penetration')!='full_wall':raise ValueError('فقط بازشوی مستطیلی تمام ضخامت معتبر است')
   b=rect(p,L,H)
   if any(intersection(b,v)>0 for v in holes.values()):raise ValueError('بازشوها هم‌پوشان یا تکراری هستند')
   holes[p['id']]=b
  gross=L*H;net=gross-sum((area(b) for b in holes.values()),Decimal(0))
  if net<=0:raise ValueError('سطح خالص باید مثبت باشد')
  masonry=group(a['masonry'],kind!='plaster_finish');finishes=group(a['finishes'],kind=='plaster_finish')
  if group(a['accessories']):raise ValueError('اتصال و مسلح‌سازی دیوار هنوز قرارداد تخصصی ندارد')
  if not masonry and (a['masonry_layers'] or a['unit_regions']):raise ValueError('عدم کاربرد دیوارچینی دارای ردیف است')
  if not finishes and a['surfaces']:raise ValueError('عدم کاربرد اندود دارای ردیف است')
  bands=[];layers={};regions={}
  for p in a['masonry_layers']:
   ident(p,LAYER_FIELDS)
   if p.get('material_kind') not in (('brick',) if kind=='brick_wall' else ('cement_block','clay_block','light_block','aac')):raise ValueError('مصالح با خانواده دیوار سازگار نیست')
   for k in ('unit_spec_ref','mortar_ref','payment_ref'):require_text(p.get(k),'مرجع واحد بنایی و بند کامل')
   off=n(p.get('offset_m'),'ابتدای لایه',True);t=n(p.get('thickness_m'),'ضخامت لایه');u,v,d=[n(p.get(k),'ابعاد واقعی واحد') for k in ('unit_length_m','unit_height_m','unit_depth_m')]
   hj,bj=[n(p.get(k),'ضخامت بند مستند',True) for k in ('head_joint_m','bed_joint_m')]
   if d!=t or off+t>T or any(min(off+t,e)-max(off,s)>0 for s,e in bands):raise ValueError('ضخامت یا تداخل لایه‌های دیوار معتبر نیست')
   if p.get('payment_unit') not in ('m2','m3'):raise ValueError('مبنای پرداخت دیوار باید سطح یا حجم کامل باشد')
   bands.append((off,off+t));layers[p['id']]=(p,t,u,v,d,hj,bj);regions[p['id']]=[]
  if masonry and (not layers or sum((e-s for s,e in bands),Decimal(0))!=T):raise ValueError('تمام ضخامت دیوار باید لایه‌بندی مستند شود')
  for p in a['unit_regions']:
   ident(p,REGION_FIELDS)
   if p.get('layer_id') not in layers:raise ValueError('لایه مرجع جانمایی یافت نشد')
   layer,t,u,v,d,hj,bj=layers[p['layer_id']];b=rect(p,L,H);items=regions[p['layer_id']]
   if any(intersection(b,o)>0 for o in holes.values()) or any(intersection(b,o[0])>0 for o in items):raise ValueError('جانمایی با بازشو یا ناحیه دیگر هم‌پوشانی دارد')
   units=Decimal(0)
   if p.get('mode')=='units':
    nx,ny=[n(p.get(k),'تعداد واقعی ردیف',integer=True) for k in ('nx','ny')]
    if b[2]-b[0]!=nx*u+(nx-1)*hj or b[3]-b[1]!=ny*v+(ny-1)*bj:raise ValueError('ابعاد جانمایی با تعداد و بند مستند منطبق نیست')
    units=nx*ny
   elif p.get('mode')=='mortar':
    if p.get('nx') not in ('',None) or p.get('ny') not in ('',None) or not (b[2]-b[0]==hj or b[3]-b[1]==bj):raise ValueError('ناحیه ملات باید بند کامل با ضخامت مستند باشد')
   else:raise ValueError('نوع جانمایی معتبر نیست')
   items.append((b,units))
  for lid,(p,t,u,v,d,hj,bj) in layers.items():
   items=regions[lid]
   if sum((area(b) for b,c in items),Decimal(0))!=net:raise ValueError('قطعه‌بندی واحدها و بندها کل سطح خالص را نمی‌پوشاند')
   units=sum((c for b,c in items),Decimal(0));mortar=net*t-units*u*v*d
   if units<=0 or mortar<0:raise ValueError('تعداد یا حجم ملات معتبر نیست')
   params={**p,'gross_area_m2':gross,'net_area_m2':net,'net_volume_m3':net*t,'installed_count':units,'joint_volume_m3':mortar,'repeat_count':count}
   emit('masonry_work',net if p['payment_unit']=='m2' else net*t,p['payment_unit'],lid,params,'سطح خالص مستند' if p['payment_unit']=='m2' else 'سطح خالص × ضخامت لایه')
   emit('masonry_units',units,'عدد',lid+'-units',params,'جمع تعداد واقعی جانمایی؛ خرید و پرت تعیین نشده','material')
   if mortar:emit('mortar',mortar,'m3',lid+'-mortar',params,'حجم خالص لایه − مجموع حجم پوش خارجی واحدهای بنایی؛ بدون پرکردن حفره داخلی','material')
  surfaces={};face_ids={}
  for p in a['surfaces']:
   ident(p,SURFACE_FIELDS);side=p.get('face');code=p.get('layer_code');sid=canonical(p.get('surface_id'))
   if side not in ('inside','outside') or code not in ('base_plaster','white_plaster','cement_render','levelling','protective'):raise ValueError('وجه یا نوع لایه پشتیبانی نمی‌شود')
   if side in face_ids and face_ids[side]!=sid:raise ValueError('یک وجه نمی‌تواند چند هویت سطح داشته باشد')
   if sid in (v for k,v in face_ids.items() if k!=side):raise ValueError('دو وجه باید هویت مستقل داشته باشند')
   face_ids[side]=sid
   for k in ('material_ref','payment_ref','deduction_ref','scope_ref'):require_text(p.get(k),'مشخصات، دامنه و قرارداد کسر')
   b=rect(p,L,H);t=n(p.get('thickness_m'),'ضخامت مستقل اندود');key=(side,code);items=surfaces.setdefault(key,[])
   if any(intersection(b,q[0])>0 for q in items):raise ValueError('یک لایه پوشش دوباره شمرده شده است')
   if p.get('coverage_scope') not in ('complete','partial'):raise ValueError('دامنه پوشش باید صریح باشد')
   if any(q[2]!=p['coverage_scope'] for q in items):raise ValueError('دامنه پوشش یک لایه ناسازگار است')
   linked=p.get('opening_ids')
   if not isinstance(linked,str):raise ValueError('شناسه بازشوها با جداکننده عمودی لازم است')
   links=linked.split('|') if linked else [];actual={i for i,o in holes.items() if intersection(b,o)>0}
   if len(set(links))!=len(links) or set(links)!=actual:raise ValueError('کسورات این وجه باید دقیقاً به تمام بازشوهای متقاطع متصل شوند')
   deduction=sum((intersection(b,holes[i]) for i in links),Decimal(0));surface_net=area(b)-deduction
   if surface_net<=0:raise ValueError('پوشش خالص باید مثبت باشد')
   unit=p.get('payment_unit')
   if unit not in ('m2','m3','kg'):raise ValueError('واحد پوشش معتبر نیست')
   q=surface_net if unit=='m2' else surface_net*t
   if unit=='kg':require_text(p.get('density_ref'),'مرجع چگالی');q*=n(p.get('density_kg_m3'),'چگالی مستند')
   elif p.get('density_kg_m3') or p.get('density_ref'):raise ValueError('چگالی فقط در قرارداد پرداخت وزنی معتبر است')
   items.append((b,surface_net,p['coverage_scope']))
   params={**p,'gross_area_m2':area(b),'deducted_area_m2':deduction,'net_area_m2':surface_net,'net_volume_m3':surface_net*t,'repeat_count':count}
   emit(code,q,unit,p['id'],params,'سطح وجه مستقل − تقاطع بازشوها'+('؛ × ضخامت مستند' if unit!='m2' else '')+(' × چگالی گواهی‌شده' if unit=='kg' else ''))
  if finishes and not surfaces:raise ValueError('جدول مستقل پوشش لازم است')
  for items in surfaces.values():
   if items[0][2]=='complete' and sum((q[1] for q in items),Decimal(0))!=net:raise ValueError('پوشش کامل اعلام‌شده تمام وجه خالص را نمی‌پوشاند')
  if not rows or len({canonical(v['source_id']) for v in rows})!=len(rows):raise ValueError('ردیف خالی یا هویت تولیدشده تکراری است')
  if require_review:
   rv=data.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین');require_text(rv.get('note'),'یادداشت')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=kind,floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

def takeoffs(data,version):
 # The existing ledger row schema is shared; calculate with this contract only.
 from core.takeoff.engine import TakeoffEngine
 result=preview(data,TakeoffEngine())
 if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
 return [dict(id=v['source_id'],source_id=v['source_id'],member_code=data['system_id'],system=data['floor_id'],domain=v['domain'],item=v['item_code'],description=v['description'],params=deepcopy(v['params']),provenance=deepcopy(data['source']),revision=version,quantities=[dict(code=v['item_code'],title=v['description'],unit=v['unit'],amount=v['quantity'],role=v['role'],formula=v['formula'],price_code=None,unit_price=None)]) for v in result['rows']]

def remap_copy(data,replacements):
 from uuid import uuid4
 a=data['architecture_detail']
 from core.takeoff.slope_aec_detail import is_slope,remap_copy as slope_copy
 if is_slope(data):return slope_copy(data,replacements)
 from core.takeoff.skirting_detail import is_skirting,remap_copy as skirt_copy
 if is_skirting(data):return skirt_copy(data,replacements)
 from core.takeoff.interior_cover_detail import is_cover,remap_copy as cover_copy
 if is_cover(data):return cover_copy(data,replacements)
 if data['kind'] in ('floor_finish','waterproofing','thermal_insulation','acoustic_insulation'):
  a['geometry']['physical_region_id']='AF-'+uuid4().hex;keys={}
  for p in a['layers']:
   if p.get('layer_key'):
    keys.setdefault(p['layer_key'],'FL-'+uuid4().hex);p['layer_key']=keys[p['layer_key']]
   if isinstance(p.get('opening_ids'),str):p['opening_ids']='|'.join(replacements.get(i,i) for i in p['opening_ids'].split('|')) if p['opening_ids'] else ''
  return
 a['geometry']['physical_wall_id']='AW-'+uuid4().hex
 for p in a['unit_regions']:p['layer_id']=replacements.get(p.get('layer_id'),p.get('layer_id',''))
 faces={}
 for p in a['surfaces']:
  if p.get('surface_id'):
   faces.setdefault(p['surface_id'],'AS-'+uuid4().hex);p['surface_id']=faces[p['surface_id']]
  if isinstance(p.get('opening_ids'),str):p['opening_ids']='|'.join(replacements.get(i,i) for i in p['opening_ids'].split('|')) if p['opening_ids'] else ''

def suggestions(context):
 if context not in ('wall','room'):raise ValueError('زمینه پیشنهاد معتبر نیست')
 return [dict(kind=k,title=t,status='نیازمند انتخاب و تکمیل دیتایل') for k,t in [('block_wall','دیوارچینی بلوکی'),('brick_wall','دیوارچینی آجری'),('plaster_finish','اندود مستقل'),('paint_finish','رنگ‌آمیزی'),('ceramic_finish','کاشی و سرامیک')]]

@exact
def guard(previous,updated):
 """Check physical ownership across records, effective amendments and old contracts."""
 old=previous.get('reviewed_aec_systems',{});register=updated.get('reviewed_aec_systems',{})
 from core.takeoff.skirting_detail import is_skirting,guard as skirt_guard
 from core.takeoff.interior_cover_detail import is_cover,guard as cover_guard
 for key,r in old.items():
  new=register.get(key)
  if new and r['data'].get('architecture_detail',{}).get('contract')!=new['data'].get('architecture_detail',{}).get('contract'):raise ValueError('تغییر قرارداد تاریخی پوشش نیازمند مهاجرت صریح است')
 for key,r in old.items():
  new=register.get(key)
  if new and r['data'].get('kind') in KINDS and r['data'].get('measurement_policy')!=new['data'].get('measurement_policy') and POLICY in (r['data'].get('measurement_policy'),new['data'].get('measurement_policy')):raise ValueError('تغییر قرارداد تاریخی معماری نیازمند مهاجرت صریح است')
 walls={};parts=set();coats={};face_names={}
 from core.takeoff.manual_formula_amendments import beam_current
 for key,r in register.items():
  if r.get('data',{}).get('measurement_policy')!=POLICY:continue
  if is_cover(r['data']) or is_skirting(r['data']):continue
  if r['data']['kind'] in ('floor_finish','waterproofing','thermal_insulation','acoustic_insulation'):continue
  d=beam_current(updated,key)['data'];a=d.get('architecture_detail',{});g=a.get('geometry',{});building=canonical(d.get('building_id'));wall=(building,canonical(g.get('physical_wall_id')))
  for other,p in register.items():
   v=p.get('data',{})
   if other!=key and v.get('kind') in KINDS and v.get('measurement_policy')!=POLICY and v.get('floor_id')==d.get('floor_id') and v.get('system_id')==d.get('system_id'):raise ValueError('هویت تاریخی معماری نیازمند مهاجرت صریح است')
  identity=tuple(str(d.get(k,'')) for k in ('floor_id','axis'))+tuple(str(g.get(k,'')) for k in ('length_m','height_m','wall_thickness_m','count','repeat_ref'))
  owns=a.get('masonry',{}).get('status')=='confirmed'
  if wall in walls:
   prior,owner=walls[wall]
   if prior!=identity or (owner and owns):raise ValueError('هویت فیزیکی یا دیوارچینی تکراری یا دامنه متناقض است')
   walls[wall]=(identity,owner or owns)
  else:walls[wall]=(identity,owns)
  for name in ('masonry_layers','unit_regions','openings','surfaces'):
   for p in a.get(name,[]):
    pk=p.get('physical_key')
    if pk:
     part=(building,canonical(pk))
     if part in parts:raise ValueError('جزء فیزیکی معماری در چند رکورد تکرار شده است')
     parts.add(part)
  for p in a.get('surfaces',[]):
   if not all(p.get(k) not in ('',None) for k in ('x','y','width_m','height_m','face','layer_code','surface_id')):continue
   b=rect(p,n(g.get('length_m'),'طول'),n(g.get('height_m'),'ارتفاع'));scope=wall+(p['face'],p['layer_code'])
   if any(intersection(b,o)>0 for o in coats.get(scope,[])):raise ValueError('یک عملیات پوشش روی یک وجه در چند رکورد دوباره شمرده شده است')
   coats.setdefault(scope,[]).append(b)
   face=wall+(p['face'],);surface=canonical(p['surface_id'])
   if face in face_names and face_names[face]!=surface:raise ValueError('هویت سطح یک وجه ناسازگار است')
   face_names[face]=surface
 from core.takeoff.floor_detail import guard as floor_guard
 floor_guard(updated)
 from core.takeoff.slope_aec_detail import guard as slope_guard
 slope_guard(updated)
 cover_guard(updated)
 skirt_guard(updated)


def validate_amendment(previous,proposal,before_rows,after_rows):
 """An arithmetic delta cannot subtract unlike units or replace a physical wall."""
 from core.takeoff.slope_aec_detail import is_slope,validate_amendment as validate_slope
 if is_slope(previous):validate_slope(previous,proposal)
 from core.takeoff.skirting_detail import is_skirting
 from core.takeoff.interior_cover_detail import is_cover
 if previous['architecture_detail'].get('contract')!=proposal['architecture_detail'].get('contract'):raise ValueError('تغییر قرارداد تخصصی در اصلاحیه ممنوع است')
 if is_cover(previous):
  for key in ('physical_surface_id','host_id','face','plane'):
   if previous['architecture_detail']['geometry'][key]!=proposal['architecture_detail']['geometry'][key]:raise ValueError('تغییر هویت سطح یا وجه در اصلاحیه ممنوع است')
 identity='physical_space_id' if is_skirting(previous) else 'physical_surface_id' if is_cover(previous) else 'physical_region_id' if previous['kind'] in ('floor_finish','waterproofing','thermal_insulation','acoustic_insulation') else 'physical_wall_id'
 if canonical(previous['architecture_detail']['geometry'][identity])!=canonical(proposal['architecture_detail']['geometry'][identity]):raise ValueError('تغییر هویت فیزیکی دیوار در اصلاحیه ممنوع است')
 def dimensions(rows):return {r['source_id']:(r['item'],r['quantities'][0]['unit'],r['quantities'][0]['role']) for r in rows}
 before,after=dimensions(before_rows),dimensions(after_rows)
 if any(before[k]!=after[k] for k in before.keys() & after.keys()):raise ValueError('اختلاف اصلاحیه باید هم‌واحد و برای همان عملیات باشد؛ تغییر مبنا نیازمند ردیف مستقل است')
