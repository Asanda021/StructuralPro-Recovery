"""Documented manual steel/deck contracts on the existing AEC ledger and BOQ.

No section database, density, profile, fastening count or price is inferred.
"""
from copy import deepcopy
from decimal import Decimal
from core.commercial.exact_values import exact,wire
from core.takeoff.roof_detail import n,canonical,checked,strict,review_digest
from core.takeoff.reviewed_components import require_text
POLICY='steel_specialist_v1'
KINDS=('steel_frame','steel_deck')
PROFILES=('columns','beams','secondary','bracing','truss','rebars')
GROUPS=('columns','beams','secondary','bracing','truss','plates','bolts','welds','coatings','operations','studs','rebars')
LABELS=dict(zip(GROUPS,('ستون فولادی','تیر فولادی','تیر فرعی و تیرچه فولادی','مهاربند','عضو خرپا با طول برش مستند','ورق اتصال و صفحه ستون','مجموعه پیچ مهره واشر','جوش','پوشش محافظ','عملیات مستقل','گل میخ','میلگرد')))
COMMON=('id','physical_key','source_ref','approved_by')
FIELDS={k:('count','length_m','unit_weight_kg_m','unit_weight_source','section_ref','steel_ref','scope_ref','cut_ref') for k in PROFILES}
FIELDS.update(plates=('count','x','y','z','length_m','width_m','thickness_m','density_kg_m3','density_source','steel_ref'),bolts=('count','unit_mass_kg','mass_source','spec_ref','payment_basis'),studs=('count','unit_mass_kg','mass_source','spec_ref','payment_basis'),welds=('count','length_m','spec_ref','method_ref'),coatings=('count','length_m','width_m','spec_ref','scope_ref'),operations=('quantity','unit','operation','basis_ref','spec_ref'))
PANEL_FIELDS=('x','y','length_m','effective_width_m','nominal_width_m','side_lap_m','end_lap_m','thickness_m','unit_weight_kg_m2','weight_source','spec_ref')

def physical_identity_guard(project):
 keys=set();seen=set()
 for key,record in project.get('reviewed_aec_systems',{}).items():
  d=record.get('data',{})
  if d.get('measurement_policy')!=POLICY:continue
  member=tuple(canonical(d.get(k)) for k in ('building_id','system_id'))
  if member in keys:raise ValueError('عضو فولادی فیزیکی در طبقه یا سیستم دیگر تکرار شده است')
  keys.add(member)
  for other,r in project.get('reviewed_aec_systems',{}).items():
   old=r.get('data',{})
   if other!=key and old.get('kind') in KINDS and old.get('measurement_policy')!=POLICY and old.get('floor_id')==d.get('floor_id') and old.get('system_id')==d.get('system_id'):raise ValueError('رکورد تاریخی نیازمند مهاجرت صریح است')
  # Use effective data after amendments, retaining original immutable records.
  from core.takeoff.manual_formula_amendments import beam_current
  effective=beam_current(project,key)['data']
  detail=effective.get('steel_detail',{})
  entries=[p for g in detail.get('groups',{}).values() for p in g.get('entries',[])]+(detail.get('deck') or {}).get('panels',[])
  for p in entries:
   pk=canonical(p.get('physical_key'));full=(canonical(d.get('building_id')),pk)
   if full in seen:raise ValueError('هویت فیزیکی فولاد یا اتصال تکراری است')
   seen.add(full)

@exact
def preview(data,engine,require_review=False):
 rows=[];errors=[];kind=data.get('kind');source=data.get('source',{})
 try:
  if kind not in KINDS or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد تخصصی فولاد معتبر نیست')
  strict(data,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','steel_detail','roof_review'),'فولاد')
  for k in ('building_id','floor_id','system_id','axis'):require_text(data.get(k),'هویت، طبقه و محور')
  from core.takeoff.roof_detail import validate_roof_source
  validate_roof_source(source,data['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(p!={'status':'unreviewed'} for p in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی هم‌زمان قابل شمارش نیستند')
  detail=data['steel_detail'];strict(detail,('groups','deck'),'دیتایل فولاد')
  groups=detail['groups']
  if set(groups)!=set(GROUPS):raise ValueError('همه گروه‌ها باید مستقل بررسی شوند')
  ids=set();physical=set();plate_boxes=[]
  def ident(p,fields):
   strict(p,COMMON+fields,'جزء فولادی');checked(p)
   i=canonical(p.get('id'));pk=canonical(p.get('physical_key'))
   if i in ids or pk in physical:raise ValueError('جزء فیزیکی تکراری است')
   ids.add(i);physical.add(pk);return p['id']
  def emit(code,amount,unit,group,i,formula,p,role='work'):
   rows.append(dict(source_id=f"aec:{kind}:{data['floor_id']}:{data['system_id']}:{i}",line_id=i,item_code=code,quantity=wire(amount),unit=unit,domain='building',description=LABELS.get(group,group)+' '+data['system_id'],formula=formula,params=wire(deepcopy(p)),component=group,method=POLICY,source_ref=p['source_ref'],role=role))
  for group in GROUPS:
   g=groups[group];strict(g,('status','approved_by','source_ref','reason','entries'),'گروه فولاد');checked(g)
   required=group in (('columns','beams') if kind=='steel_frame' else ('studs','rebars'))
   if g.get('status')=='not_applicable' and not required:
    require_text(g.get('reason'),'علت عدم کاربرد')
    if g.get('entries'):raise ValueError('عدم کاربرد دارای ردیف ممنوع است')
    continue
   if g.get('status')!='confirmed' or not isinstance(g.get('entries'),list) or not 0<len(g['entries'])<=512:raise ValueError('دیتایل مستقل گروه لازم است')
   if kind=='steel_deck' and group in PROFILES and group!='rebars':raise ValueError('تیرهای تکیه‌گاه در متره مستقل فولاد ثبت شوند')
   if kind=='steel_frame' and group in ('studs','rebars'):raise ValueError('گروه سقف در اسکلت فولادی مجاز نیست')
   for p in g['entries']:
    i=ident(p,FIELDS[group]);count=n(p.get('count'),'تعداد',integer=True) if group!='operations' else None
    for field in FIELDS[group]:
     if field.endswith(('_ref','_source')) or field in ('spec_ref','steel_ref'):require_text(p.get(field),'مرجع مشخصات و اندازه‌گیری')
    if group in PROFILES:
     amount=count*n(p.get('length_m'),'طول برش')*n(p.get('unit_weight_kg_m'),'وزن واحد مستند')
     emit('rebar' if group=='rebars' else 'structural_steel',amount,'kg',group,i,'تعداد × طول برش مستند × وزن واحد گواهی‌شده',p)
    elif group=='plates':
     if count!=1:raise ValueError('هر ورق جانمایی مستقل و تعداد یک داشته باشد')
     start=tuple(n(p.get(k),k,True) for k in ('x','y','z'));dims=tuple(n(p.get(k),k) for k in ('length_m','width_m','thickness_m'));end=tuple(a+b for a,b in zip(start,dims));box=(start,end)
     from core.takeoff.roof_detail import overlap
     if any(overlap(box,b)>0 for b in plate_boxes):raise ValueError('ورق‌های هم‌پوشان یا تکراری ممنوع‌اند')
     plate_boxes.append(box);emit('structural_steel',dims[0]*dims[1]*dims[2]*n(p.get('density_kg_m3'),'چگالی مستند'),'kg',group,i,'طول × عرض × ضخامت × چگالی مستند؛ ورق افقی مستقل',p)
    elif group in ('bolts','studs'):
     mass=count*n(p.get('unit_mass_kg'),'جرم گواهی‌شده مجموعه کامل');basis=p.get('payment_basis')
     if basis not in ('count','kg'):raise ValueError('مبنای پرداخت صریح تعداد یا وزن لازم است')
     emit(group,count,'عدد',group,i,'تعداد واقعی مجموعه کامل؛ اجزای داخل مجموعه دوباره شمرده نمی‌شوند',p,'work' if basis=='count' else 'material')
     emit('bolt_mass' if group=='bolts' else 'stud_mass',mass,'kg',group,i+'-mass','تعداد × جرم مستند؛ فقط یکی از تعداد یا وزن قابل پرداخت است',p,'work' if basis=='kg' else 'material')
    elif group=='welds':emit('weld',count*n(p.get('length_m'),'طول واقعی جوش'),'m',group,i,'تعداد × طول مستند با مشخصات جوش',p)
    elif group=='coatings':emit('steel_coating',count*n(p.get('length_m'),'طول سطح')*n(p.get('width_m'),'عرض سطح'),'m2',group,i,'تعداد × طول وجه × عرض وجه؛ لایه و دامنه در مشخصات',p)
    else:
     if p.get('operation') not in ('fabrication','erection','surface_preparation') or p.get('unit') not in ('kg','m2','عدد'):raise ValueError('نوع عملیات مستقل و واحد معتبر لازم است')
     emit('steel_'+p['operation'],n(p.get('quantity'),'مقدار مستقل عملیات'),p['unit'],group,i,'مقدار مستقل عملیات طبق مبنای قراردادی؛ بدون استنتاج از مصالح',p)
  deck=detail.get('deck')
  if kind=='steel_frame':
   if deck is not None:raise ValueError('جدول عرشه در اسکلت مجاز نیست')
  else:
   strict(deck,('length_m','width_m','topping_m','flute_depth_m','flute_top_m','flute_bottom_m','pitch_m','profile_ref','approved_by','source_ref','openings','panels'),'عرشه');checked(deck);require_text(deck.get('profile_ref'),'مرجع مقطع ذوزنقه')
   if deck.get('openings')!=[]:raise ValueError('بازشو، تقاطع یا برش عرشه نیازمند قرارداد مستقل است')
   L,W,t,h,top,bottom,pitch=[n(deck.get(k),k) for k in ('length_m','width_m','topping_m','flute_depth_m','flute_top_m','flute_bottom_m','pitch_m')]
   if max(top,bottom)>pitch:raise ValueError('عرض شیار از گام بیشتر است')
   panels=deck.get('panels');used=[];area=Decimal(0)
   if not isinstance(panels,list) or not 0<len(panels)<=512:raise ValueError('جدول مستقل ورق لازم است')
   for p in panels:
    i=ident(p,PANEL_FIELDS);x=n(p.get('x'),'شروع طول',True);y=n(p.get('y'),'شروع عرض',True);length=n(p.get('length_m'),'طول ورق');width=n(p.get('effective_width_m'),'عرض مؤثر');nominal=n(p.get('nominal_width_m'),'عرض اسمی');side=n(p.get('side_lap_m'),'هم‌پوشانی عرضی',True)
    n(p.get('thickness_m'),'ضخامت ورق');require_text(p.get('weight_source'),'گواهی وزن اسمی');require_text(p.get('spec_ref'),'مشخصات ورق')
    if x!=0 or length!=L or y+width>W or nominal-width!=side or n(p.get('end_lap_m'),'هم‌پوشانی طولی',True)!=0:raise ValueError('فقط ورق تمام‌دهانه با عرض مؤثر و هم‌پوشانی عرضی صریح معتبر است')
    if width%pitch!=0:raise ValueError('عرض مؤثر باید شامل تعداد صحیح شیار مستند باشد')
    if any(min(y+width,b)-max(y,a)>0 for a,b in used):raise ValueError('ناحیه پوشش مؤثر ورق تکراری یا هم‌پوشان است')
    used.append((y,y+width));area+=length*width
    emit('deck_sheet',length*nominal*n(p.get('unit_weight_kg_m2'),'وزن بر مساحت اسمی گواهی‌شده'),'kg','ورق عرشه',i,'طول × عرض اسمی × وزن گواهی‌شده بر مساحت اسمی؛ شامل هم‌پوشانی',p)
   if area!=L*W:raise ValueError('جانمایی ورق کل سطح سقف را پوشش نمی‌دهد')
   emit('concrete',L*W*t,'m3','بتن رویه','deck-top','طول × عرض مؤثر کل × ضخامت رویه مستقل',deck)
   emit('concrete',L*(W/pitch)*(top+bottom)*h/2,'m3','بتن شیار','deck-flutes','طول × تعداد صحیح شیار × (عرض بالا + عرض پایین) × عمق / ۲',deck)
  if len({row['source_id'] for row in rows})!=len(rows):raise ValueError('شناسه ردیف تولیدشده با جزء فیزیکی تداخل دارد')
  if require_review:
   rv=data.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین');require_text(rv.get('note'),'یادداشت')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=kind,floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

def takeoffs(data,version):
 from core.takeoff.engine import TakeoffEngine
 r=preview(data,TakeoffEngine())
 if not r['ready']:raise ValueError('؛ '.join(r['blockers']))
 return [{'id':v['source_id'],'source_id':v['source_id'],'member_code':data['system_id'],'system':data['floor_id'],'domain':v['domain'],'item':v['item_code'],'description':v['description'],'params':deepcopy(v['params']),'provenance':deepcopy(data['source']),'revision':version,'quantities':[{'code':v['item_code'],'title':v['description'],'unit':v['unit'],'amount':v['quantity'],'role':v['role'],'formula':v['formula'],'price_code':None,'unit_price':None}]} for v in r['rows']]
