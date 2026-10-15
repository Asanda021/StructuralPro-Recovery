"""Versioned roof detail specialization of ReviewedAEC; no design/default quantities.

Only complete, axis-aligned rectangular partitions are accepted. Measured
reinforcement and faces have independent physical identities and evidence.
"""
from copy import deepcopy
from decimal import Decimal
from itertools import combinations
from core.commercial.exact_values import number, wire, exact
from core.takeoff.reviewed_components import require_text
from core.takeoff.reviewed_structural import _validate_source

POLICY='roof_specialist_v1'
KINDS=('solid_slab','joist_block','joist_foam')
BARS=('main_x','main_y','distribution','thermal','rib','additional','opening','solid','tie')
LABELS={'concrete':'بتن درجاریز','topping':'بتن رویه','ribs':'بتن ریب درجاریز','ties':'بتن کلاف','solid_zones':'بتن ناحیه توپر','precast':'بتن پیش‌ساخته','void':'فضای بلوک یا فوم','main_x':'میلگرد اصلی جهت اول','main_y':'میلگرد اصلی جهت دوم','distribution':'میلگرد توزیعی','thermal':'میلگرد حرارتی','rib':'میلگرد ریب','additional':'میلگرد تقویتی','opening':'میلگرد بازشو','solid':'میلگرد ناحیه توپر','tie':'میلگرد کلاف','formwork':'قالب‌بندی','shoring':'شمع‌بندی','blocks':'بلوک','foam':'فوم','joists':'تیرچه'}


def n(v,label,zero=False,integer=False):
 d=number(v,label)
 if d<0 or (not zero and d==0) or (integer and d!=d.to_integral_value()):raise ValueError(label+' باید عدد معتبر مثبت باشد')
 return d


def canonical(v):
 import unicodedata
 return unicodedata.normalize('NFKC',require_text(v,'شناسه')).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).casefold()


def strict(part,allowed,label):
 if not isinstance(part,dict) or set(part)-set(allowed):raise ValueError(label+' دارای داده ناشناخته یا روش محاسباتی پشتیبانی‌نشده است')


def validate_roof_source(source,identity):
 if source.get('mode')=='drawing':raise ValueError('برداشت نقشه‌ای تخصصی سقف تا اتصال مقیاس معتبر و قرارداد ناحیه‌بندی نقشه مسدود است؛ متره دستی مستند قابل استفاده است')
 return _validate_source(source,identity)


def physical_identity_guard(project):
 seen=set()
 for record in project.get('reviewed_aec_systems',{}).values():
  d=record.get('data',{})
  if d.get('measurement_policy')!=POLICY:continue
  key=tuple(canonical(d.get(k)) for k in ('building_id','floor_id','system_id'))
  if key in seen:raise ValueError('سقف فیزیکی با نوع سیستم متفاوت یا هویت تکراری ثبت شده است')
  seen.add(key)


def checked(part):
 require_text(part.get('source_ref'),'مرجع دیتایل')
 require_text(part.get('approved_by'),'تأییدکننده دیتایل')


def applicable(group,required=False):
 if not isinstance(group,dict):raise ValueError('ساختار گروه دیتایل لازم است')
 checked(group)
 if group.get('status')=='not_applicable' and not required:
  if any(group.get(k) for k in ('series','faces','props')):raise ValueError('گروه دارای دیتایل را نمی‌توان عدم کاربرد اعلام کرد')
  require_text(group.get('reason'),'دلیل عدم کاربرد');return False
 if group.get('status')!='confirmed':raise ValueError('گروه نیازمند اطلاعات یا دیتایل است')
 return True


def box(part,limit):
 checked(part)
 start=tuple(n(part.get(k),k,True) for k in ('x','y','z'))
 size=tuple(n(part.get(k),k) for k in ('length','width','height'))
 end=tuple(a+b for a,b in zip(start,size))
 if any(b>m for b,m in zip(end,limit)):raise ValueError('ناحیه خارج از محدوده واقعی سقف است')
 return start,end


def overlap(a,b):
 ext=[max(Decimal(0),min(x,y)-max(s,t)) for s,x,t,y in zip(a[0],a[1],b[0],b[1])]
 return ext[0]*ext[1]*ext[2]


def volume(b):return (b[1][0]-b[0][0])*(b[1][1]-b[0][1])*(b[1][2]-b[0][2])


def review_digest(data):
 from core.takeoff.manual_formula_amendments import digest
 d=deepcopy(data);d.pop('roof_review',None);return digest(d)


@exact
def preview(data,engine,require_review=False):
 """Return the existing AEC preview shape; all persisted quantities use wire()."""
 errors=[];rows=[]
 kind=data['kind'];floor=data['floor_id'];sid=data['system_id'];source=data.get('source',{})
 prefix=f'aec:{kind}:{floor}:{sid}'
 try:
  if kind not in KINDS or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد سقف معتبر نیست')
  validate_roof_source(source,sid)
  for key in ('plan_ref','detail_ref'):require_text(source.get(key),'پلان و دیتایل منبع')
  require_text(data.get('building_id'),'شناسه ساختمان')
  strict(data,('kind','floor_id','system_id','source','components','measurement_policy','building_id','roof_detail','roof_review'),'سقف')
  if any(part!={'status':'unreviewed'} for part in data['components'].values()):raise ValueError('دیتایل عمومی و تخصصی سقف نباید هم‌زمان شمرده شوند')
  d=data['roof_detail'];strict(d,('geometry','regions','deductions','deductions_ref','rebars','pieces','pieces_ref','formwork','shoring','joist_layout'),'دیتایل سقف')
  g=d['geometry'];strict(g,('unit','shape','length','width','depth','count','repeat_scope','action','topping_thickness','joist_axis','joist_count','joist_spacing','joist_supply_scope','source_ref','approved_by'),'هندسه');checked(g)
  if g.get('unit')!='m' or g.get('shape')!='rectangular':raise ValueError('فقط هندسه مستطیلی با واحد صریح متر پشتیبانی می‌شود')
  L,W,H=(n(g.get(k),k) for k in ('length','width','depth'));count=n(g.get('count'),'تعداد سقف',integer=True)
  if g.get('repeat_scope')!='identical_roofs':raise ValueError('تکرار صریح سقف‌های هم‌تیپ لازم است')
  if kind=='solid_slab' and g.get('action') not in ('one_way','two_way'):raise ValueError('جهت دال باید مستند باشد')
  used=set();physical=set()
  def identity(part,physical_key=False):
   key=canonical(part.get('id'))
   if key in used:raise ValueError('شناسه جزء تکراری است')
   used.add(key)
   if physical_key:
    k=canonical(part.get('physical_key'))
    if k in physical:raise ValueError('هویت فیزیکی مشترک دوباره شمرده شده است')
    physical.add(k)
   return part['id']
  def emit(code,quantity,unit,component,ident,formula,params):
   if quantity<=0:return
   rows.append({'source_id':prefix+':'+str(ident),'line_id':str(ident),'item_code':code,'quantity':wire(quantity*count),'unit':unit,'domain':'building','description':LABELS.get(component,component)+' سقف '+sid,'formula':formula+' × تعداد سقف هم‌تیپ','params':wire(params),'component':component,'method':POLICY,'source_ref':params.get('source_ref',g['source_ref']),'role':'material' if code=='precast_concrete' or params.get('series',{}).get('supply_scope')=='factory' else 'work'})
  parts=d['regions']
  if not isinstance(parts,list) or not 0<len(parts)<=512:raise ValueError('جدول ناحیه‌ها باید شامل یک تا۵۱۲ناحیه واقعی باشد')
  regions=[]
  allowed={'concrete'} if kind=='solid_slab' else {'topping','ribs','ties','solid_zones','precast','void'}
  for p in parts:
   strict(p,('id','component','x','y','z','length','width','height','source_ref','approved_by'),'ناحیه')
   identity(p)
   if p.get('component') not in allowed:raise ValueError('نوع ناحیه با سیستم سقف تطبیق ندارد')
   regions.append((p,box(p,(L,W,H))))
  if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(regions,2)):raise ValueError('نواحی هندسی سقف هم‌پوشان‌اند')
  gross=L*W*H
  if sum((volume(b) for _,b in regions),Decimal(0))!=gross:raise ValueError('ناحیه‌بندی کامل سقف نیست؛ حجم ناشناخته مجاز نیست')
  deductions=[];require_text(d.get('deductions_ref'),'مرجع کسورات یا نبود تقاطع')
  for p in d['deductions']:
   strict(p,('id','kind','owner_source_id','x','y','z','length','width','height','source_ref','approved_by'),'کسر')
   identity(p)
   if p.get('kind') not in ('opening','beam_joint'):raise ValueError('نوع کسر معتبر نیست')
   if p['kind']=='beam_joint':require_text(p.get('owner_source_id'),'منبع مالک بتن مشترک تیر و سقف')
   deductions.append((p,box(p,(L,W,H))))
  if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(deductions,2)):raise ValueError('کسورات مشترک یا هم‌پوشان تکراری ممنوع است')
  allocations=[]
  for p,b in regions:
   if p['component']=='void':continue
   deducted=sum((overlap(b,c) for _,c in deductions),Decimal(0))
   if p['component']=='precast' and deducted:raise ValueError('بازشو در قطعه پیش‌ساخته به هندسه و دیتایل قطعه اصلاح‌شده نیاز دارد')
   code='precast_concrete' if p['component']=='precast' else 'concrete'
   emit(code,volume(b)-deducted,'m3',p['component'],p['id'],'حجم ناحیه مستطیلی منهای تقاطع مکانی مستند',{'geometry':deepcopy(p),'gross_m3':volume(b),'deducted_m3':deducted,'source_ref':p['source_ref'],'reviewed_by':p['approved_by']})
   allocations.append({'region_id':p['id'],'deducted_m3':wire(deducted)})
  if not rows:raise ValueError('سقف فاقد حجم بتن خالص است')
  rows[0]['params'].update(intersections=[{'id':p['id'],'source_ref':p['source_ref']} for p,_ in deductions],deduction_allocations=allocations,gross_roof_m3=wire(gross),roof_geometry=deepcopy(g))
  pieces=d['pieces'];require_text(d.get('pieces_ref'),'مرجع قطعات یا عدم کاربرد')
  if kind=='solid_slab':
   if pieces or d['joist_layout']:raise ValueError('دال توپر نباید قطعات پرکننده یا تیرچه داشته باشد')
  else:
   t=n(g.get('topping_thickness'),'ضخامت بتن رویه')
   if t>=H:raise ValueError('ضخامت رویه از ارتفاع سقف کمتر باشد')
   tops=[(p,b) for p,b in regions if p['component']=='topping']
   if not tops or any(b[0][2]!=H-t or b[1][2]!=H for _,b in tops):raise ValueError('رویه باید دقیقاً در تراز و ضخامت مستند باشد')
   if any(b[1][2]>H-t for p,b in regions if p['component'] not in ('topping','solid_zones')):raise ValueError('ناحیه زیرین وارد رویه شده است')
   axis=g.get('joist_axis')
   if axis not in ('x','y'):raise ValueError('جهت تیرچه مستند نیست')
   if g.get('joist_supply_scope')!='purchased_joists':raise ValueError('قرارداد فعلی نیازمند دامنه صریح تیرچه خریداری‌شده است')
   jc=n(g.get('joist_count'),'تعداد واقعی تیرچه',integer=True);spacing=n(g.get('joist_spacing'),'فاصله واقعی تیرچه')
   layout=d['joist_layout'];joists=[]
   for p in layout:
    strict(p,('id','x','y','z','length','width','height','source_ref','approved_by'),'جانمایی تیرچه');identity(p);joists.append((p,box(p,(L,W,H-t))))
   if len(joists)!=jc:raise ValueError('تعداد واقعی تیرچه با جانمایی تطبیق ندارد')
   if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(joists,2)):raise ValueError('تیرچه‌های جانمایی‌شده هم‌پوشان‌اند')
   long=0 if axis=='x' else 1;trans=1-long
   if any(b[0][long]!=0 or b[1][long]!=(L,W)[long] or b[0][2]!=0 or b[1][2]!=H-t for _,b in joists):raise ValueError('جانمایی مستند تیرچه باید تمام‌دهانه و تمام ارتفاع زیر رویه باشد')
   centers=sorted((b[0][trans]+b[1][trans])/2 for _,b in joists)
   if any(y-x!=spacing for x,y in zip(centers,centers[1:])):raise ValueError('فاصله تیرچه‌ها با جانمایی واقعی تطبیق ندارد')
   for _,j in joists:
    if sum((overlap(j,b) for p,b in regions if p['component']!='void'),Decimal(0))!=volume(j):raise ValueError('اجزای بتن تیرچه با جانمایی واقعی تطبیق ندارند')
    if not any(overlap(j,b)>0 for p,b in regions if p['component']=='precast'):raise ValueError('تیرچه خریداری‌شده نیازمند دیتایل قطعه پیش‌ساخته است')
   for p,b in regions:
    if p['component'] in ('ribs','precast') and sum((overlap(b,j) for _,j in joists),Decimal(0))!=volume(b):raise ValueError('ریب یا قطعه پیش‌ساخته بیرون جانمایی تیرچه است')
   emit('joists',jc,'عدد','joists','joist-count','تعداد واقعی ردیف‌های تیرچه',{'source_ref':g['source_ref'],'reviewed_by':g['approved_by'],'axis':axis,'spacing_m':wire(spacing)})
   voids={p['id']:(p,b) for p,b in regions if p['component']=='void'};seen=set()
   for piece in pieces:
    ident=identity(piece);require_text(piece.get('source_ref'),'منبع قطعه');require_text(piece.get('spec_ref'),'مشخصات قطعه')
    region_id=piece['region_id']
    if region_id not in voids or region_id in seen:raise ValueError('قطعه باید به یک ناحیه پرکننده مستقل مرتبط باشد')
    seen.add(region_id);_,b=voids[region_id]
    dims=[n(piece.get(k),k) for k in ('length','width','height')];nums=[n(piece.get(k),k,integer=True) for k in ('nx','ny','nz')];qty=n(piece.get('count'),'تعداد قطعه',integer=True)
    if qty!=nums[0]*nums[1]*nums[2] or any(a*c!=e-s for a,c,s,e in zip(dims,nums,b[0],b[1])):raise ValueError('تعداد و ابعاد قطعات با چیدمان واقعی تطبیق ندارد')
    emit('blocks' if kind=='joist_block' else 'foam',qty,'عدد','blocks' if kind=='joist_block' else 'foam',ident,'چیدمان مستند سه‌محوره قطعات',deepcopy(piece))
   if seen!=set(voids) or not voids:raise ValueError('همه نواحی پرکننده باید دیتایل قطعه داشته باشند')
   # An opening cannot silently remove purchased pieces/joists from their schedules.
   if any(overlap(b,c)>0 for p,b in regions if p['component'] in ('void','ribs','ties') for _,c in deductions):raise ValueError('بازشوی قطع‌کننده تیرچه یا پرکننده نیازمند دیتایل قطعه‌بندی مستقل است')
  bars=d['rebars']
  if set(bars)!=set(BARS):raise ValueError('گروه مستقل میلگرد ناقص یا ناشناخته است')
  for group in BARS:
   part=bars[group];strict(part,('status','approved_by','source_ref','reason','series'),'گروه میلگرد');required=group in (('main_x','main_y') if kind=='solid_slab' else ('rib','thermal')) or (group=='opening' and any(p['kind']=='opening' for p,_ in deductions))
   if not applicable(part,required):continue
   if not part.get('series'):raise ValueError('سری مستقل میلگرد لازم است')
   for series in part['series']:
    strict(series,('id','physical_key','diameter_mm','supply_scope','count','cut_length_m','unit_weight_kg_m','unit_weight_source','shape_ref','source_ref','cut_parts'),'سری میلگرد')
    ident=identity(series,True)
    for k in ('shape_ref','source_ref','unit_weight_source'):require_text(series.get(k),'دیتایل برش، مرجع و وزن واحد')
    if series.get('supply_scope') not in ('site','factory') or (kind=='solid_slab' and series.get('supply_scope')!='site'):raise ValueError('دامنه میلگرد کارگاهی یا داخل تیرچه کارخانه‌ای باید صریح باشد')
    n(series.get('diameter_mm'),'قطر میلگرد');qty=n(series.get('count'),'تعداد میلگرد',integer=True);cut=n(series.get('cut_length_m'),'طول برش');uw=n(series.get('unit_weight_kg_m'),'وزن واحد مستند')
    cut_parts=series.get('cut_parts');cut_ids=set();total=Decimal(0)
    if not isinstance(cut_parts,list) or not cut_parts:raise ValueError('ریز طول مستقیم، خم، قلاب و وصله صریح لازم است')
    for cp in cut_parts:
     ci=canonical(cp.get('id'))
     if ci in cut_ids:raise ValueError('جزء برش تکراری است')
     cut_ids.add(ci);require_text(cp.get('source_ref'),'مرجع جزء برش');total+=n(cp.get('length_m'),'طول جزء برش')
    if total!=cut:raise ValueError('جمع اجزای برش با طول برش یکسان نیست')
    emit('rebar',qty*cut*uw,'kg',group,ident,'تعداد × مجموع برش مستند × وزن واحد مستند',{'series':deepcopy(series),'source_ref':part['source_ref'],'reviewed_by':part['approved_by']})
  part=d['formwork'];strict(part,('status','approved_by','source_ref','reason','faces'),'قالب')
  if applicable(part):
   if not part.get('faces'):raise ValueError('وجه قالب مستند لازم است')
   for face in part['faces']:
    ident=identity(face,True);require_text(face.get('source_ref'),'مرجع وجه قالب')
    gross_face=n(face.get('length_m'),'طول وجه')*n(face.get('width_m'),'عرض وجه');ded=n(face.get('deduction_m2'),'کسر سطح مستند',True)
    if ded>=gross_face:raise ValueError('سطح خالص قالب نامعتبر است')
    emit('formwork',gross_face-ded,'m2','formwork',ident,'طول وجه × عرض وجه − کسر مستند',deepcopy(face))
  part=d['shoring'];strict(part,('status','approved_by','source_ref','reason','props'),'شمع‌بندی')
  if applicable(part):
   if not part.get('props'):raise ValueError('جدول شمع‌بندی مستند لازم است')
   for prop in part['props']:
    ident=identity(prop,True);n(prop.get('height_m'),'ارتفاع شمع');require_text(prop.get('source_ref'),'مرجع شمع');require_text(prop.get('system_ref'),'روش و مشخصات شمع‌بندی')
    emit('shoring',n(prop.get('count'),'تعداد شمع',integer=True),'عدد','shoring',ident,'تعداد مستند شمع بدون ضریب فرضی',deepcopy(prop))
  if require_review:
   r=data.get('roof_review',{})
   require_text(r.get('reviewer'),'بازبین کل سقف');require_text(r.get('note'),'یادداشت بازبینی')
   if r.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری سقف معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return {'kind':kind,'floor_id':floor,'system_id':sid,'source_id':source.get('source_id'),'ready':not errors,'blockers':errors,'rows':rows,'preview_only':True}


def takeoffs(data,version):
 from core.takeoff.engine import TakeoffEngine
 r=preview(data,TakeoffEngine())
 if not r['ready']:raise ValueError('سقف ناقص است: '+'؛ '.join(r['blockers']))
 return [{'id':v['source_id'],'source_id':v['source_id'],'member_code':data['system_id'],'system':data['floor_id'],'domain':v['domain'],'item':v['item_code'],'description':v['description'],'params':deepcopy(v['params']),'provenance':deepcopy(data['source']),'revision':version,'quantities':[{'code':v['item_code'],'title':v['description'],'unit':v['unit'],'amount':v['quantity'],'role':v['role'],'formula':v['formula'],'price_code':None,'unit_price':None}]} for v in r['rows']]
