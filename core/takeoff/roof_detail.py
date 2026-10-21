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
WAFFLE_KINDS=('waffle_one_way','waffle_two_way')
HOLLOW_KIND='hollow_core_detail'
VOID_KINDS=('uboot','cobiax')
KINDS=('solid_slab','joist_block','joist_foam')+WAFFLE_KINDS+(HOLLOW_KIND,)+VOID_KINDS
BARS=('main_x','main_y','distribution','thermal','rib','additional','opening','solid','tie')
LABELS={'opening_void':'فضای بازشوی مستند؛ غیرقابل پرداخت','joints':'بتن درز هالوکور','cast_in_place':'بتن درجاریز مستقل','hollow_core_panels':'قطعه نهایی هالوکور','precast_panel_mass':'جرم کل قطعه شامل فولاد کارخانه‌ای','prestressing_steel':'فولاد پیش‌تنیدگی کارخانه‌ای','ribs_x':'بتن ریب جهت طول','ribs_y':'بتن ریب جهت عرض','junctions':'بتن تقاطع مستقل ریب‌ها','void_formers':'حفره‌ساز خریداری‌شده مستقل','void_cells':'بتن خالص سلول دارای حفره‌ساز','waffle_molds':'قالب وافل؛ تعداد قطعه مستقل','concrete':'بتن درجاریز','topping':'بتن رویه','ribs':'بتن ریب درجاریز','ties':'بتن کلاف','solid_zones':'بتن ناحیه توپر','precast':'بتن پیش‌ساخته','void':'فضای بلوک یا فوم','main_x':'میلگرد اصلی جهت اول','main_y':'میلگرد اصلی جهت دوم','distribution':'میلگرد توزیعی','thermal':'میلگرد حرارتی','rib':'میلگرد ریب','additional':'میلگرد تقویتی','opening':'میلگرد بازشو','solid':'میلگرد ناحیه توپر','tie':'میلگرد کلاف','formwork':'قالب‌بندی','shoring':'شمع‌بندی','blocks':'بلوک','foam':'فوم','joists':'تیرچه'}


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
 if source.get('mode')=='drawing' and source.get('roof_binding'):
  from core.drawings.roof_region import validate_source
  validate_source(source);return source['source_id']
 if source.get('mode')=='drawing':raise ValueError('برداشت نقشه‌ای تخصصی سقف تا اتصال مقیاس معتبر و قرارداد ناحیه‌بندی نقشه مسدود است؛ متره دستی مستند قابل استفاده است')
 return _validate_source(source,identity)


def physical_identity_guard(project):
 if not isinstance(project.get('reviewed_aec_systems',{}),dict):
  raise ValueError('ساختار دفتر سیستم‌های بازبینی‌شده نامعتبر است')
 seen=set()
 for record in project.get('reviewed_aec_systems',{}).values():
  d=record.get('data',{})
  if d.get('measurement_policy')!=POLICY:continue
  key=tuple(canonical(d.get(k)) for k in ('building_id','floor_id','system_id'))
  if key in seen:raise ValueError('سقف فیزیکی با نوع سیستم متفاوت یا هویت تکراری ثبت شده است')
  seen.add(key)
  if d.get('kind') in VOID_KINDS:
   for previous in project.get('reviewed_aec_systems',{}).values():
    old=previous.get('data',{})
    if old.get('kind') in VOID_KINDS and old.get('measurement_policy')!=POLICY and all(canonical(old.get(k))==canonical(d.get(k)) for k in ('floor_id','system_id')):
     raise ValueError('سقف حفره‌دار تاریخی هم‌هویت وجود دارد؛ مهاجرت مستند پیش از شمارش مجدد الزامی است')
  if d.get('kind')==HOLLOW_KIND:
   for previous in project.get('reviewed_aec_systems',{}).values():
    old=previous.get('data',{})
    if old.get('kind')=='hollow_core' and all(canonical(old.get(k))==canonical(d.get(k)) for k in ('floor_id','system_id')):raise ValueError('هالوکور تاریخی هم‌هویت وجود دارد؛ تبدیل یا شمارش مجدد بدون گردش مهاجرت معتبر ممنوع است')

 _planar_physical_guard(project)


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
 if isinstance(a,PlanarPrism) or isinstance(b,PlanarPrism):
  from core.drawings.planar_geometry import intersection,decimal_text
  from fractions import Fraction
  height=max(Decimal(0),min(a[1][2],b[1][2])-max(a[0][2],b[0][2]))
  return number(decimal_text(intersection(_prism_footprint(a),_prism_footprint(b))*Fraction(height)),'حجم تقاطع دقیق')
 ext=[max(Decimal(0),min(x,y)-max(s,t)) for s,x,t,y in zip(a[0],a[1],b[0],b[1])]
 return ext[0]*ext[1]*ext[2]


def volume(b):
 if isinstance(b,PlanarPrism):
  from core.drawings.planar_geometry import signed,decimal_text
  from fractions import Fraction
  return number(decimal_text(abs(signed(b.footprint))*Fraction(b[1][2]-b[0][2])),'حجم منشور دقیق')
 return (b[1][0]-b[0][0])*(b[1][1]-b[0][1])*(b[1][2]-b[0][2])


def review_digest(data):
 from core.takeoff.manual_formula_amendments import digest
 d=deepcopy(data);d.pop('roof_review',None);return digest(d)


def validate_waffle(d,kind,regions,deductions,limit,identity,emit):
 """Validate measured rib envelopes against a disjoint solid/void partition.

 Cross-direction envelopes may intersect. Their intersection belongs solely to
 junction regions. Same-direction overlap is never valid. No grid is inferred.
 """
 L,W,H=limit;g=d['geometry'];t=n(g.get('topping_thickness'),'ضخامت رویه وافل')
 if t>=H:raise ValueError('ضخامت رویه وافل باید کمتر از ارتفاع باشد')
 if d.get('joist_layout') or any(g.get(k) not in (None,'') for k in ('joist_axis','joist_count','joist_spacing','joist_supply_scope')):raise ValueError('دیتایل تیرچه در وافل مجاز نیست')
 if g.get('action')!=('one_way' if kind=='waffle_one_way' else 'two_way'):raise ValueError('رفتار وافل با خانواده انتخابی تطبیق ندارد')
 axis=g.get('rib_axis')
 if axis not in ('x','y'):raise ValueError('جهت اصلی ریب باید مستند باشد')
 tops=[b for p,b in regions if p['component']=='topping']
 if not tops or any(b[0][2]!=H-t or b[1][2]!=H for b in tops):raise ValueError('رویه وافل باید در تراز و ضخامت مستند باشد')
 if any(b[1][2]>H-t for p,b in regions if p['component'] not in ('topping','solid_zones')):raise ValueError('ناحیه زیرین وافل وارد رویه شده است')
 layout=d.get('rib_layout')
 if not isinstance(layout,list) or not 0<len(layout)<=128:raise ValueError('جانمایی مستقل یک تا۱۲۸ریب لازم است')
 ribs={'x':[],'y':[]}
 for p in layout:
  strict(p,('id','axis','x','y','z','length','width','height','source_ref','approved_by'),'جانمایی ریب')
  identity(p);a=p.get('axis')
  if a not in ribs or (kind=='waffle_one_way' and a!=axis):raise ValueError('جهت ریب با قرارداد وافل تطبیق ندارد')
  b=box(p,(L,W,H-t))
  if b[0][2]!=0 or b[1][2]!=H-t:raise ValueError('ریب باید تمام ارتفاع زیر رویه باشد؛ ریب پله‌ای پشتیبانی نمی‌شود')
  ribs[a].append(b)
 if not ribs[axis] or (kind=='waffle_two_way' and (not ribs['x'] or not ribs['y'])):raise ValueError('جانمایی هر جهت ریب الزامی است')
 if any(overlap(a,b)>0 for group in ribs.values() for a,b in combinations(group,2)):raise ValueError('ریب‌های هم‌جهت مشترک یا تکراری‌اند')
 crossings=[(a,b) for a in ribs['x'] for b in ribs['y'] if overlap(a,b)>0]
 if kind=='waffle_two_way' and not crossings:raise ValueError('وافل دوطرفه فاقد تقاطع مستند است')
 rib_volume=Decimal(0)
 for p,b in regions:
  c=p['component'];vx=sum((overlap(b,r) for r in ribs['x']),Decimal(0));vy=sum((overlap(b,r) for r in ribs['y']),Decimal(0));v=volume(b)
  if c=='ribs_x' and (vx!=v or vy):raise ValueError('ناحیه ریب طولی شامل تقاطع یا خارج از جانمایی است')
  if c=='ribs_y' and (vy!=v or vx):raise ValueError('ناحیه ریب عرضی شامل تقاطع یا خارج از جانمایی است')
  if c=='junctions' and (vx!=v or vy!=v):raise ValueError('ناحیه تقاطع باید دقیقاً تحت پوشش هر دو جهت باشد')
  if c not in ('ribs_x','ribs_y','junctions') and (vx or vy):raise ValueError('جانمایی ریب با ناحیه توپر، رویه یا قالب تداخل دارد؛ قطعه‌بندی مستند لازم است')
  if c in ('ribs_x','ribs_y','junctions'):rib_volume+=v
 expected=sum((volume(b) for group in ribs.values() for b in group),Decimal(0))-sum((overlap(a,b) for a,b in crossings),Decimal(0))
 if rib_volume!=expected:raise ValueError('ناحیه‌بندی ریب و تقاطع کامل نیست')
 voids={p['id']:b for p,b in regions if p['component']=='void'};seen=set()
 if not voids:raise ValueError('وافل فاقد ناحیه قالب مستند است')
 for piece in d['pieces']:
  strict(piece,('id','physical_key','region_id','count','length','width','height','nx','ny','nz','shape','source_ref','spec_ref','approved_by'),'قالب وافل')
  ident=identity(piece,True);checked(piece);require_text(piece.get('spec_ref'),'مشخصات قالب')
  if piece.get('shape')!='rectangular_prism':raise ValueError('فقط قالب منشوری مستطیلی با دیتایل واقعی پشتیبانی می‌شود؛ قالب شیب‌دار مسدود است')
  rid=piece.get('region_id')
  if rid not in voids or rid in seen:raise ValueError('ناحیه قالب تکراری یا فاقد جانمایی است')
  seen.add(rid);b=voids[rid]
  if b[0][2]!=0 or b[1][2]!=H-t:raise ValueError('قالب وافل باید از زیر سقف تا زیر رویه باشد؛ حفره معلق پذیرفته نیست')
  dims=[n(piece.get(k),k) for k in ('length','width','height')];nums=[n(piece.get(k),k,integer=True) for k in ('nx','ny','nz')];qty=n(piece.get('count'),'تعداد قالب',integer=True)
  if nums[2]!=1 or qty!=nums[0]*nums[1]*nums[2] or any(a*c!=e-s for a,c,s,e in zip(dims,nums,b[0],b[1])):raise ValueError('تعداد، ابعاد یا چیدمان قالب وافل با ناحیه حفره یکسان نیست')
  emit('waffle_molds',qty,'عدد','waffle_molds',ident,'تعداد قالب در جانمایی مستند؛ مستقل از سطح تماس قالب',deepcopy(piece))
 if seen!=set(voids):raise ValueError('همه نواحی حفره نیازمند دیتایل قالب هستند')
 if any(overlap(b,c)>0 for p,b in regions if p['component']!='solid_zones' for _,c in deductions):raise ValueError('بازشو یا تقاطع وافل فقط در ناحیه توپر مستقل پذیرفته می‌شود؛ قطع ریب یا قالب نیازمند قرارداد قطعه‌بندی است')


def validate_hollow_core(d,regions,deductions,limit,identity,emit):
 """Final rectangular panels with certified hollow volumes; never infer density.

 Envelope partitions separate factory panels from site concrete. An internal
 hollow's shape is not approximated: its certified volume is a measured input.
 """
 L,W,H=limit;g=d['geometry'];t=n(g.get('topping_thickness'),'ضخامت رویه هالوکور',True)
 if t>=H:raise ValueError('رویه باید کمتر از ارتفاع کل هالوکور باشد')
 if g.get('panel_axis') not in ('x','y'):raise ValueError('جهت نصب قطعات باید مستند باشد')
 if d.get('pieces') or d.get('joist_layout') or d.get('rib_layout') or any(g.get(k) not in (None,'') for k in ('action','joist_axis','joist_count','joist_spacing','joist_supply_scope','rib_axis')):raise ValueError('دیتایل دال، تیرچه یا وافل در هالوکور مجاز نیست')
 tops=[b for p,b in regions if p['component']=='topping']
 if bool(tops)!=bool(t) or any(b[0][2]!=H-t or b[1][2]!=H for b in tops):raise ValueError('تراز، ضخامت یا عدم کاربرد رویه باید دقیقاً با نواحی تطبیق داشته باشد')
 if any(b[1][2]>H-t for p,b in regions if p['component'] not in ('topping','solid_zones','cast_in_place')):raise ValueError('قطعه یا درز وارد ناحیه رویه شده است')
 precast={p['id']:(p,b) for p,b in regions if p['component']=='precast'};panels=d.get('panels');seen=set()
 if not precast or not isinstance(panels,list) or not 0<len(panels)<=256:raise ValueError('جدول مستقل یک تا۲۵۶قطعه هالوکور لازم است')
 for panel in panels:
  strict(panel,('id','physical_key','region_id','count','length','width','height','shape','spec_ref','fabrication_ref','source_ref','approved_by','void_volume_m3','void_source_ref','net_volume_m3','volume_source_ref','unit_mass_kg','mass_source_ref','mass_scope'),'قطعه هالوکور')
  ident=identity(panel,True);checked(panel)
  for key in ('spec_ref','fabrication_ref','void_source_ref'):require_text(panel.get(key),'گواهی مقطع، قطعه نهایی و حفره')
  if panel.get('shape')!='factory_finished_rectangle' or n(panel.get('count'),'تعداد قطعه مستقل',integer=True)!=1:raise ValueError('هر ردیف باید یک قطعه نهایی مستطیلی با دیتایل کارخانه باشد؛ تعداد یا قطعه‌بندی فرضی مسدود است')
  rid=panel.get('region_id')
  if rid not in precast or rid in seen:raise ValueError('قطعه باید به ناحیه پیش‌ساخته مستقل و غیرتکراری متصل باشد')
  seen.add(rid);region,b=precast[rid]
  if b[0][2]!=0 or b[1][2]!=H-t or any(n(panel.get(k),k)!=end-start for k,start,end in zip(('length','width','height'),b[0],b[1])):raise ValueError('ابعاد قطعه نهایی با پوش و تراز واقعی قطعه تطبیق ندارد')
  gross=volume(b);void=n(panel.get('void_volume_m3'),'حجم حفره مستند')
  if void>=gross:raise ValueError('حجم حفره از حجم پوش قطعه کمتر باشد')
  net=gross-void;has_volume=panel.get('net_volume_m3') not in (None,'');has_mass=panel.get('unit_mass_kg') not in (None,'')
  if not has_volume and not has_mass:raise ValueError('حجم خالص یا جرم گواهی‌شده قطعه لازم است')
  if has_volume:
   require_text(panel.get('volume_source_ref'),'منبع حجم خالص')
   if n(panel['net_volume_m3'],'حجم خالص قطعه')!=net:raise ValueError('حجم خالص، حفره و پوش قطعه با هم تطبیق ندارند')
  elif panel.get('volume_source_ref'):raise ValueError('مرجع حجم بدون مقدار صریح مجاز نیست')
  if has_mass:
   mass=n(panel['unit_mass_kg'],'جرم کل قطعه');require_text(panel.get('mass_source_ref'),'منبع جرم قطعه')
   if panel.get('mass_scope')!='whole_panel_including_factory_steel':raise ValueError('جرم باید صریحاً جرم کل قطعه شامل فولاد کارخانه‌ای باشد')
  elif panel.get('mass_source_ref') or panel.get('mass_scope'):raise ValueError('مرجع یا دامنه جرم بدون مقدار صریح مجاز نیست')
  if any(overlap(b,c)>0 for _,c in deductions):raise ValueError('بازشوی قطع‌کننده قطعه پیش‌ساخته بدون قرارداد هندسی معتبر مسدود است')
  params={'panel':deepcopy(panel),'geometry':deepcopy(region),'gross_m3':gross,'deducted_m3':void,'net_panel_m3':net,'source_ref':panel['source_ref'],'reviewed_by':panel['approved_by']}
  emit('precast_concrete',net,'m3','precast',rid,'حجم پوش قطعه منهای حجم حفره گواهی‌شده؛ اطلاعات غیرقابل پرداخت مستقل',params)
  emit('hollow_core_panels',Decimal(1),'عدد','hollow_core_panels',ident,'تعداد واقعی قطعات نهایی؛ بدون جمع مالی مجدد اجزای کارخانه‌ای',{'panel':deepcopy(panel),'source_ref':panel['source_ref']})
  if has_mass:
   mass_id=ident+':mass';identity({'id':mass_id})
   emit('precast_panel_mass',mass,'kg','precast_panel_mass',mass_id,'جرم کل گواهی‌شده؛ شامل فولاد کارخانه‌ای و غیرقابل پرداخت مستقل',{'panel':deepcopy(panel),'source_ref':panel['mass_source_ref']})
 if seen!=set(precast):raise ValueError('همه نواحی پیش‌ساخته نیازمند جدول قطعه هستند')
 for p,b in deductions:
  if b[0][2]!=0 or b[1][2]!=H or any(overlap(b,c)>0 for region,c in regions if region['component'] not in ('solid_zones','cast_in_place','topping')):raise ValueError('کسور هالوکور فقط تمام‌ارتفاع در ناحیه درجاریز مستقل با دیتایل معتبر پذیرفته می‌شود')



def validate_void_formers(d,kind,regions,deductions,limit,identity,emit):
 """Certified U-Boot rectangular voids or Cobiax spherical voids in disjoint cells.

 The cell is a FULL CONCRETE ENVELOPE, not an empty box. Certified former void
 volume is subtracted once per cell. One independently identified former per
 cell avoids guessing spacing, overlap, group placement and cut pieces.
 """
 L,W,H=limit;g=d['geometry']
 top=n(g.get('topping_thickness'),'ضخامت بالایی سقف')
 bottom=n(g.get('bottom_thickness'),'ضخامت پایینی سقف')
 if top+bottom>=H:raise ValueError('ضخامت بالایی و پایینی فضای میانی معتبر باقی نمی‌گذارند')
 if deductions:raise ValueError('بازشو یا قطع حفره‌ساز نیازمند قرارداد هندسی و قطعه‌بندی مستقل است')
 if d.get('pieces') or d.get('panels') or d.get('joist_layout') or d.get('rib_layout'):
  raise ValueError('قطعات تیرچه/وافل/هالوکور در یوبوت و کوبیاکس مجاز نیستند')
 if any(g.get(k) not in (None,'') for k in ('action','rib_axis','panel_axis','joist_axis','joist_count','joist_spacing','joist_supply_scope')):
  raise ValueError('پارامتر دال/تیرچه/وافل به یوبوت یا کوبیاکس تعلق ندارد')
 tops=[b for p,b in regions if p['component']=='topping']
 if not tops or any(b[0][2]!=H-top or b[1][2]!=H for b in tops) or sum((volume(b) for b in tops),Decimal(0))!=L*W*top:
  raise ValueError('بتن رویه باید کل لایه بالایی مستند را بدون هم‌پوشانی پوشش دهد')
 bottoms=[b for p,b in regions if p['component']=='solid_zones' and b[0][2]==0 and b[1][2]==bottom]
 if not bottoms or sum((volume(b) for b in bottoms),Decimal(0))!=L*W*bottom:
  raise ValueError('بتن زیره باید تمام سطح و ضخامت مستند زیرین را پوشش دهد')
 core_top=H-top
 for p,b in regions:
  c=p['component']
  if c=='topping':continue
  if b[0][2]<bottom and not (c=='solid_zones' and b[0][2]==0 and b[1][2]==bottom):
   raise ValueError('پوش بتن زیرین نباید با سلول حفره‌دار یا ریب مخلوط شود')
  if c=='void' and (b[0][2]!=bottom or b[1][2]!=core_top):
   raise ValueError('سلول حفره‌دار باید از روی زیره تا زیر رویه ارتفاع کامل داشته باشد')
  if b[1][2]>core_top and c!='solid_zones':
   raise ValueError('ناحیه میانی وارد رویه بالایی شده است')
 void_cells={p['id']:(p,b) for p,b in regions if p['component']=='void'}
 formers=d.get('void_formers')
 if not void_cells or not isinstance(formers,list) or len(formers)!=len(void_cells) or len(formers)>512:
  raise ValueError('هر سلول حفره‌دار دقیقاً به یک قطعه واقعی و مستند نیاز دارد')
 seen=set()
 for former in formers:
  strict(former,('id','physical_key','region_id','shape','count','x','y','z','length','width','height','diameter_m','certified_void_volume_m3','volume_source_ref','spec_ref','source_ref','approved_by'),'حفره‌ساز مستقل')
  ident=identity(former,True);checked(former)
  require_text(former.get('spec_ref'),'گواهی قطعه حفره‌ساز')
  require_text(former.get('volume_source_ref'),'گواهی حجم واقعی حفره')
  rid=former.get('region_id')
  if rid not in void_cells or rid in seen:raise ValueError('شناسه سلول حفره‌ساز تکراری یا نامعتبر است')
  seen.add(rid);region,cell=void_cells[rid]
  if n(former.get('count'),'تعداد قطعه در سلول',integer=True)!=1:
   raise ValueError('قطعه‌بندی فعلی فقط یک حفره‌ساز دارای جانمایی مستقل در هر سلول می‌پذیرد')
  bbox=box(former,limit)
  if any(a<s or b>e for (a,b),(s,e) in zip(zip(bbox[0],bbox[1]),zip(cell[0],cell[1]))):
   raise ValueError('پوش فیزیکی حفره‌ساز خارج از سلول یا لایه میانی است')
  certified=n(former.get('certified_void_volume_m3'),'حجم واقعی گواهی‌شده حفره')
  if kind=='uboot':
   if former.get('shape')!='rectangular_prism' or former.get('diameter_m') not in ('',None):
    raise ValueError('یوبوت فعلاً فقط حفره منشوری مستطیلی گواهی‌شده را می‌پذیرد')
   if certified!=volume(bbox):
    raise ValueError('حجم یوبوت منشوری با ابعاد مستند حفره برابر نیست')
  else:
   if former.get('shape')!='certified_sphere':
    raise ValueError('کوبیاکس نیازمند حفره کروی با حجم مستقل گواهی‌شده است')
   diameter=n(former.get('diameter_m'),'قطر گواهی‌شده حفره کروی')
   if any(b-a!=diameter for a,b in zip(bbox[0],bbox[1])):
    raise ValueError('ابعاد پوش کوبیاکس باید با قطر کروی گواهی‌شده برابر باشد')
   if certified>=volume(bbox):
    raise ValueError('حجم کروی گواهی‌شده باید از حجم پوش مکعبی کمتر باشد')
  if certified>=volume(cell):
   raise ValueError('حجم حفره باید از حجم سلول واقعی کوچک‌تر باشد')
  params={'geometry':deepcopy(region),'void_former':deepcopy(former),'gross_m3':volume(cell),'deducted_m3':certified,'source_ref':former['volume_source_ref'],'reviewed_by':former['approved_by']}
  emit('concrete',volume(cell)-certified,'m3','void_cells',rid,'حجم سلول واقعی منهای یک حفره گواهی‌شده با جانمایی مستقل',params)
  emit('void_formers',Decimal(1),'عدد','void_formers',ident,'تعداد حفره‌ساز خریداری‌شده با هویت مستقل، بدون کسر مالی مضاعف بتن',{'void_former':deepcopy(former),'source_ref':former['source_ref']})
 if seen!=set(void_cells):
  raise ValueError('جدول حفره‌سازها با ناحیه‌بندی سقف کامل نیست')


@exact
def preview(data,engine,require_review=False):
 """Return the existing AEC preview shape; all persisted quantities use wire()."""
 errors=[];rows=[]
 kind=data['kind'];floor=data['floor_id'];sid=data['system_id'];source=data.get('source',{})
 prefix=f'aec:{kind}:{floor}:{sid}'
 try:
  if kind not in KINDS or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد سقف معتبر نیست')
  validate_roof_source(source,sid)
  if source.get('roof_binding'):
   from core.drawings.roof_region import validate_detail
   validate_detail(data)
  for key in ('plan_ref','detail_ref'):require_text(source.get(key),'پلان و دیتایل منبع')
  require_text(data.get('building_id'),'شناسه ساختمان')
  strict(data,('kind','floor_id','system_id','source','components','measurement_policy','building_id','roof_detail','roof_review'),'سقف')
  if any(part!={'status':'unreviewed'} for part in data['components'].values()):raise ValueError('دیتایل عمومی و تخصصی سقف نباید هم‌زمان شمرده شوند')
  d=data['roof_detail'];strict(d,('geometry','regions','deductions','deductions_ref','rebars','pieces','pieces_ref','formwork','shoring','joist_layout','rib_layout','panels','void_formers','geometry_change'),'دیتایل سقف')
  g=d['geometry'];strict(g,('unit','shape','length','width','depth','count','repeat_scope','action','topping_thickness','joist_axis','joist_count','joist_spacing','joist_supply_scope','rib_axis','panel_axis','bottom_thickness','source_ref','approved_by','planar'),'هندسه');checked(g)
  planar=g.get('shape')=='documented_planar'
  if d.get('geometry_change') and (not planar or source.get('roof_binding',{}).get('policy')!='pdf_roof_planar_v2'):raise ValueError('اصلاح هندسه نیازمند اتصال صریح پلان PDF است')
  if g.get('unit')!='m' or g.get('shape') not in ('rectangular','documented_planar'):raise ValueError('هندسه دارای قرارداد معتبر و واحد متر نیست')
  if not planar and g.get('planar'):raise ValueError('حذف صریح قرارداد پلان محلی مجاز نیست')
  if planar and (kind not in ('solid_slab','joist_block','joist_foam') or g.get('planar',{}).get('policy')!='roof_planar_partition_v1'):raise ValueError('قرارداد پلان فقط برای سه سقف مصوب است')
  L,W,H=(n(g.get(k),k) for k in ('length','width','depth'));count=n(g.get('count'),'تعداد سقف',integer=True)
  if planar:
   from core.drawings.planar_geometry import ring,signed,decimal_text
   strict(g['planar'],('policy','outer','thickness_zones'),'قرارداد پلان محلی')
   owner=ring(g['planar']['outer'])
   if min(p[0] for p in owner)!=0 or min(p[1] for p in owner)!=0 or max(p[0] for p in owner)!=L or max(p[1] for p in owner)!=W:raise ValueError('پوش محلی جزء با رأس‌های واقعی سقف یکسان نیست')
   plan_area=number(decimal_text(abs(signed(owner))),'مساحت واقعی سقف')
   zones=[];zone_ids=set()
   for zone in g['planar'].get('thickness_zones',[]):
    if kind!='solid_slab':raise ValueError('ضخامت متغیر در این قرارداد فقط برای دال با ناحیه‌بندی مستقل است')
    strict(zone,('id','footprint','depth','source_ref','approved_by'),'ناحیه ضخامت');checked(zone)
    key=canonical(zone.get('id'))
    if key in zone_ids:raise ValueError('ناحیه ضخامت تکراری است')
    zone_ids.add(key);footprint=ring(zone['footprint']);depth=n(zone['depth'],'ضخامت مستند ناحیه')
    from core.drawings.planar_geometry import intersection
    if depth>H or intersection(owner,footprint)!=abs(signed(footprint)):raise ValueError('ناحیه ضخامت خارج از سقف است')
    zones.append(PlanarPrism(footprint,Decimal(0),depth))
   if zones and (any(overlap(a,b)>0 for a,b in combinations(zones,2)) or sum((number(decimal_text(abs(signed(z.footprint))),'سطح ناحیه') for z in zones),Decimal(0))!=plan_area or max(z.z1 for z in zones)!=H):raise ValueError('ناحیه‌بندی ضخامت کامل، مستقل و مطابق پوش ارتفاع نیست')
  make_box=(lambda p,limit:planar_box(p,limit,owner)) if planar else box
  make_region_box=(lambda p,limit:planar_box(p,limit,owner,zones)) if planar else box
  if g.get('repeat_scope')!='identical_roofs':raise ValueError('تکرار صریح سقف‌های هم‌تیپ لازم است')
  if kind=='solid_slab' and g.get('action') not in ('one_way','two_way'):raise ValueError('جهت دال باید مستند باشد')
  if kind not in WAFFLE_KINDS and (d.get('rib_layout') or g.get('rib_axis') not in (None,'')):raise ValueError('دیتایل ریب وافل در خانواده دیگر مجاز نیست')
  if kind!=HOLLOW_KIND and (d.get('panels') or g.get('panel_axis') not in (None,'')):raise ValueError('جدول قطعات هالوکور در خانواده دیگر مجاز نیست')
  if kind not in VOID_KINDS and d.get('void_formers'):raise ValueError('جدول حفره‌ساز در نوع دیگر سقف مجاز نیست')
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
   rows.append({'source_id':prefix+':'+str(ident),'line_id':str(ident),'item_code':code,'quantity':wire(quantity*count),'unit':unit,'domain':'building','description':LABELS.get(component,component)+' سقف '+sid,'formula':formula+' × تعداد سقف هم‌تیپ','params':wire(params),'component':component,'method':POLICY,'source_ref':params.get('source_ref',g['source_ref']),'role':'material' if code in ('precast_concrete','waffle_molds','precast_panel_mass') or params.get('series',{}).get('supply_scope')=='factory' else 'work'})
  parts=d['regions']
  if not isinstance(parts,list) or not 0<len(parts)<=512:raise ValueError('جدول ناحیه‌ها باید شامل یک تا۵۱۲ناحیه واقعی باشد')
  regions=[]
  allowed={'concrete'} if kind=='solid_slab' else {'topping','ribs','ties','solid_zones','precast','void'}
  if planar:allowed=allowed|{'opening_void'}
  if kind in WAFFLE_KINDS:allowed={'topping','ribs_x','ribs_y','junctions','solid_zones','void'}
  if kind==HOLLOW_KIND:allowed={'topping','precast','joints','cast_in_place','solid_zones'}
  if kind in VOID_KINDS:allowed={'topping','solid_zones','ribs_x','ribs_y','junctions','void'}
  for p in parts:
   strict(p,('id','component','x','y','z','length','width','height','source_ref','approved_by')+(('footprint',) if planar else ()),'ناحیه')
   identity(p)
   if p.get('component') not in allowed:raise ValueError('نوع ناحیه با سیستم سقف تطبیق ندارد')
   regions.append((p,make_region_box(p,(L,W,H))))
  if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(regions,2)):raise ValueError('نواحی هندسی سقف هم‌پوشان‌اند')
  gross=(sum((volume(z) for z in zones),Decimal(0)) if zones else plan_area*H) if planar else L*W*H
  if sum((volume(b) for _,b in regions),Decimal(0))!=gross:raise ValueError('ناحیه‌بندی کامل سقف نیست؛ حجم ناشناخته مجاز نیست')
  deductions=[];require_text(d.get('deductions_ref'),'مرجع کسورات یا نبود تقاطع')
  for p in d['deductions']:
   strict(p,('id','kind','owner_source_id','x','y','z','length','width','height','source_ref','approved_by')+(('footprint',) if planar else ()),'کسر')
   identity(p)
   if p.get('kind') not in ('opening','beam_joint'):raise ValueError('نوع کسر معتبر نیست')
   if p['kind']=='beam_joint':require_text(p.get('owner_source_id'),'منبع مالک بتن مشترک تیر و سقف')
   deductions.append((p,make_box(p,(L,W,H))))
  if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(deductions,2)):raise ValueError('کسورات مشترک یا هم‌پوشان تکراری ممنوع است')
  if planar:
   for p,b in regions:
    if p['component']=='opening_void' and (b[0][2]!=0 or b[1][2]!=H or not any(q['kind']=='opening' and overlap(b,c)==volume(b)==volume(c) for q,c in deductions)):
     raise ValueError('فضای بازشو باید دقیقاً به کسر تمام‌عمق مستند متصل باشد')
  if kind==HOLLOW_KIND:validate_hollow_core(d,regions,deductions,(L,W,H),identity,emit)
  if kind in VOID_KINDS:validate_void_formers(d,kind,regions,deductions,(L,W,H),identity,emit)
  allocations=[]
  for p,b in regions:
   if p['component'] in ('void','opening_void') or (kind==HOLLOW_KIND and p['component']=='precast'):continue
   deducted=sum((overlap(b,c) for _,c in deductions),Decimal(0))
   if p['component']=='precast' and deducted:raise ValueError('بازشو در قطعه پیش‌ساخته به هندسه و دیتایل قطعه اصلاح‌شده نیاز دارد')
   code='precast_concrete' if p['component']=='precast' else 'concrete'
   emit(code,volume(b)-deducted,'m3',p['component'],p['id'],('مساحت دقیق چندضلعی جزء × ضخامت صریح − تقاطع حجمی مستند' if planar else 'حجم ناحیه مستطیلی منهای تقاطع مکانی مستند'),{'geometry':deepcopy(p),'gross_m3':volume(b),'deducted_m3':deducted,'source_ref':p['source_ref'],'reviewed_by':p['approved_by']})
   allocations.append({'region_id':p['id'],'deducted_m3':wire(deducted)})
  if not rows:raise ValueError('سقف فاقد حجم بتن خالص است')
  rows[0]['params'].update(intersections=[{'id':p['id'],'source_ref':p['source_ref']} for p,_ in deductions],deduction_allocations=allocations,gross_roof_m3=wire(gross),roof_geometry=deepcopy(g))
  pieces=d['pieces'];require_text(d.get('pieces_ref'),'مرجع قطعات یا عدم کاربرد')
  if kind=='solid_slab':
   if pieces or d['joist_layout']:raise ValueError('دال توپر نباید قطعات پرکننده یا تیرچه داشته باشد')
  elif kind==HOLLOW_KIND:
   pass # Panel schedules were validated and emitted before region quantities.
  elif kind in WAFFLE_KINDS:
   validate_waffle(d,kind,regions,deductions,(L,W,H),identity,emit)
  elif kind in VOID_KINDS:
   if pieces or d.get('joist_layout'):raise ValueError('حفره‌سازهای یوبوت و کوبیاکس فقط در جدول مستقل مستند مجازند')
  else:
   t=n(g.get('topping_thickness'),'ضخامت بتن رویه')
   if t>=H:raise ValueError('ضخامت رویه از ارتفاع سقف کمتر باشد')
   tops=[(p,b) for p,b in regions if p['component']=='topping']
   if not tops or any(b[0][2]!=H-t or b[1][2]!=H for _,b in tops):raise ValueError('رویه باید دقیقاً در تراز و ضخامت مستند باشد')
   if any(b[1][2]>H-t for p,b in regions if p['component'] not in ('topping','solid_zones','opening_void')):raise ValueError('ناحیه زیرین وارد رویه شده است')
   axis=g.get('joist_axis')
   if axis not in ('x','y'):raise ValueError('جهت تیرچه مستند نیست')
   if g.get('joist_supply_scope')!='purchased_joists':raise ValueError('قرارداد فعلی نیازمند دامنه صریح تیرچه خریداری‌شده است')
   jc=n(g.get('joist_count'),'تعداد واقعی تیرچه',integer=True);spacing=n(g.get('joist_spacing'),'فاصله واقعی تیرچه')
   layout=d['joist_layout'];joists=[]
   for p in layout:
    strict(p,('id','x','y','z','length','width','height','source_ref','approved_by')+(('physical_key','run_id','span_ref') if planar else ()),'جانمایی تیرچه');identity(p,planar);joists.append((p,make_box(p,(L,W,H-t))))
   if len(joists)!=jc:raise ValueError('تعداد واقعی تیرچه با جانمایی تطبیق ندارد')
   if any(overlap(a,b)>0 for (_,a),(_,b) in combinations(joists,2)):raise ValueError('تیرچه‌های جانمایی‌شده هم‌پوشان‌اند')
   long=0 if axis=='x' else 1;trans=1-long
   if any((not planar and (b[0][long]!=0 or b[1][long]!=(L,W)[long])) or b[0][2]!=0 or b[1][2]!=H-t for _,b in joists):raise ValueError('جانمایی مستند تیرچه با دهانه و ارتفاع تطبیق ندارد')
   if planar:
    runs={}
    for p,b in joists:
     require_text(p.get('span_ref'),'دیتایل دهانه و انتهای هر قطعه تیرچه')
     run=canonical(p.get('run_id'));center=(b[0][trans]+b[1][trans])/2
     if run in runs and runs[run]!=center:raise ValueError('محور قطعات یک تیرچه تطبیق ندارد')
     runs[run]=center
     if any(overlap(b,c)>0 for _,c in deductions):raise ValueError('قطعه تیرچه وارد بازشو شده است؛ قطعه‌بندی مستقل لازم است')
    if len(set(runs.values()))!=len(runs):raise ValueError('دو شناسه تیرچه روی یک محور تعریف شده است')
   centers=sorted(runs.values()) if planar else sorted((b[0][trans]+b[1][trans])/2 for _,b in joists)
   if any(y-x!=spacing for x,y in zip(centers,centers[1:])):raise ValueError('فاصله تیرچه‌ها با جانمایی واقعی تطبیق ندارد')
   for _,j in joists:
    if sum((overlap(j,b) for p,b in regions if p['component']!='void'),Decimal(0))!=volume(j):raise ValueError('اجزای بتن تیرچه با جانمایی واقعی تطبیق ندارند')
    if not any(overlap(j,b)>0 for p,b in regions if p['component']=='precast'):raise ValueError('تیرچه خریداری‌شده نیازمند دیتایل قطعه پیش‌ساخته است')
   for p,b in regions:
    if p['component'] in ('ribs','precast') and sum((overlap(b,j) for _,j in joists),Decimal(0))!=volume(b):raise ValueError('ریب یا قطعه پیش‌ساخته بیرون جانمایی تیرچه است')
   emit('joists',jc,'عدد','joists','joist-count','تعداد واقعی ردیف‌های تیرچه',{'source_ref':g['source_ref'],'reviewed_by':g['approved_by'],'axis':axis,'spacing_m':wire(spacing),**({'documented_layout':deepcopy(layout)} if planar else {})})
   voids={p['id']:(p,b) for p,b in regions if p['component']=='void'};seen=set()
   for piece in pieces:
    ident=identity(piece,planar);require_text(piece.get('source_ref'),'منبع قطعه');require_text(piece.get('spec_ref'),'مشخصات قطعه')
    region_id=piece['region_id']
    if region_id not in voids or region_id in seen:raise ValueError('قطعه باید به یک ناحیه پرکننده مستقل مرتبط باشد')
    seen.add(region_id);_,b=voids[region_id]
    dims=[n(piece.get(k),k) for k in ('length','width','height')];nums=[n(piece.get(k),k,integer=True) for k in ('nx','ny','nz')];qty=n(piece.get('count'),'تعداد قطعه',integer=True)
    if planar and piece.get('cut_footprint'):
     from core.drawings.planar_geometry import canonical_ring,decimal_text
     require_text(piece.get('cut_ref'),'دیتایل برش قطعه خریداری‌شده');require_text(piece.get('approved_by'),'بازبین قطعه بریده')
     if qty!=1 or nums!=[1,1,1] or canonical_ring(piece['cut_footprint'])!=canonical_ring([(decimal_text(x),decimal_text(y)) for x,y in b.footprint]) or dims[2]!=b[1][2]-b[0][2] or any(dims[k]<b[1][k]-b[0][k] for k in (0,1)):
      raise ValueError('قطعه بریده باید یک قطعه مستقل با هندسه نهایی و پوش خرید صریح باشد')
    elif qty!=nums[0]*nums[1]*nums[2] or any(a*c!=e-s for a,c,s,e in zip(dims,nums,b[0],b[1])):raise ValueError('تعداد و ابعاد قطعات با چیدمان واقعی تطبیق ندارد')
    emit('blocks' if kind=='joist_block' else 'foam',qty,'عدد','blocks' if kind=='joist_block' else 'foam',ident,'چیدمان مستند سه‌محوره قطعات',deepcopy(piece))
   if seen!=set(voids) or not voids:raise ValueError('همه نواحی پرکننده باید دیتایل قطعه داشته باشند')
   # An opening cannot silently remove purchased pieces/joists from their schedules.
   if any(overlap(b,c)>0 for p,b in regions if p['component'] in ('void','ribs','ties') for _,c in deductions):raise ValueError('بازشوی قطع‌کننده تیرچه یا پرکننده نیازمند دیتایل قطعه‌بندی مستقل است')
  bars=d['rebars']
  if set(bars)!=set(BARS):raise ValueError('گروه مستقل میلگرد ناقص یا ناشناخته است')
  for group in BARS:
   part=bars[group];strict(part,('status','approved_by','source_ref','reason','series'),'گروه میلگرد');required=group in (('main_x','main_y') if kind=='solid_slab' else ('rib','thermal')) or (group=='opening' and any(p['kind']=='opening' for p,_ in deductions))
   if kind in WAFFLE_KINDS:
    required=group in ('thermal',('main_x' if g.get('rib_axis')=='x' else 'main_y')) or (kind=='waffle_two_way' and group in ('main_x','main_y')) or (group=='opening' and any(p['kind']=='opening' for p,_ in deductions)) or (group=='solid' and any(p['component']=='solid_zones' for p,_ in regions))
   if kind in VOID_KINDS:required=group in ('main_x','main_y','thermal') or (group=='solid' and any(p['component']=='solid_zones' for p,_ in regions))
   if kind==HOLLOW_KIND:required=(group=='thermal' and n(g.get('topping_thickness'),'ضخامت رویه',True)>0) or (group=='opening' and any(p['kind']=='opening' for p,_ in deductions)) or (group=='solid' and any(p['component']=='solid_zones' for p,_ in regions))
   if not applicable(part,required):continue
   if not part.get('series'):raise ValueError('سری مستقل میلگرد لازم است')
   for series in part['series']:
    strict(series,('id','physical_key','diameter_mm','supply_scope','count','cut_length_m','unit_weight_kg_m','unit_weight_source','shape_ref','source_ref','cut_parts')+(('panel_id','steel_kind') if kind==HOLLOW_KIND else ()),'سری میلگرد')
    ident=identity(series,True)
    for k in ('shape_ref','source_ref','unit_weight_source'):require_text(series.get(k),'دیتایل برش، مرجع و وزن واحد')
    if series.get('supply_scope') not in ('site','factory') or (kind in ('solid_slab',)+WAFFLE_KINDS+VOID_KINDS and series.get('supply_scope')!='site'):raise ValueError('دامنه میلگرد کارگاهی یا داخل تیرچه کارخانه‌ای باید صریح باشد')
    n(series.get('diameter_mm'),'قطر میلگرد');qty=n(series.get('count'),'تعداد میلگرد',integer=True);cut=n(series.get('cut_length_m'),'طول برش');uw=n(series.get('unit_weight_kg_m'),'وزن واحد مستند')
    cut_parts=series.get('cut_parts');cut_ids=set();total=Decimal(0)
    if not isinstance(cut_parts,list) or not cut_parts:raise ValueError('ریز طول مستقیم، خم، قلاب و وصله صریح لازم است')
    for cp in cut_parts:
     ci=canonical(cp.get('id'))
     if ci in cut_ids:raise ValueError('جزء برش تکراری است')
     cut_ids.add(ci);require_text(cp.get('source_ref'),'مرجع جزء برش');total+=n(cp.get('length_m'),'طول جزء برش')
    if total!=cut:raise ValueError('جمع اجزای برش با طول برش یکسان نیست')
    if kind==HOLLOW_KIND:
     if series.get('steel_kind') not in ('reinforcing_bar','prestressing_strand'):raise ValueError('نوع فولاد هالوکور باید صریح باشد')
     if series['supply_scope']=='factory':
      if series.get('panel_id') not in {p['id'] for p in d['panels']}:raise ValueError('فولاد کارخانه‌ای باید به قطعه مستقل متصل باشد')
     elif series.get('panel_id') or series['steel_kind']=='prestressing_strand':raise ValueError('فولاد کارگاهی نباید مالکیت قطعه کارخانه‌ای یا پیش‌تنیدگی نامعتبر داشته باشد')
    emit('prestressing_steel' if kind==HOLLOW_KIND and series['steel_kind']=='prestressing_strand' else 'rebar',qty*cut*uw,'kg','prestressing_steel' if kind==HOLLOW_KIND and series['steel_kind']=='prestressing_strand' else group,ident,'تعداد × مجموع برش مستند × وزن واحد مستند',{'series':deepcopy(series),'source_ref':part['source_ref'],'reviewed_by':part['approved_by']})
  if kind==HOLLOW_KIND:
   covered={s.get('panel_id') for p in bars.values() if p.get('status')=='confirmed' for s in p.get('series',[]) if s.get('supply_scope')=='factory'}
   if covered!={p['id'] for p in d['panels']}:raise ValueError('جدول فولاد کارخانه‌ای هر قطعه باید مستقل و مستند باشد؛ برآورد از جرم قطعه ممنوع است')
  part=d['formwork'];strict(part,('status','approved_by','source_ref','reason','faces'),'قالب')
  if applicable(part):
   if not part.get('faces'):raise ValueError('وجه قالب مستند لازم است')
   for face in part['faces']:
    ident=identity(face,True);require_text(face.get('source_ref'),'مرجع وجه قالب')
    gross_face=n(face.get('length_m'),'طول وجه')*n(face.get('width_m'),'عرض وجه');ded=n(face.get('deduction_m2'),'کسر سطح مستند',True)
    if planar and face.get('footprint'):
     from core.drawings.planar_geometry import evidence,TOPOLOGY_V2
     face_evidence=evidence(face['footprint'],face.get('holes',[]),1,face.get('opening_refs',[]),topology=TOPOLOGY_V2)
     gross_face=number(face_evidence['net_m2'],'سطح هندسی وجه قالب')
     if ded:require_text(face.get('deduction_ref'),'مدرک مستقل کسر وجه قالب')
    if ded>=gross_face:raise ValueError('سطح خالص قالب نامعتبر است')
    emit('formwork',gross_face-ded,'m2','formwork',ident,('مساحت دقیق وجه و بازشوهای مستند − کسر مستقل' if planar and face.get('footprint') else 'طول وجه × عرض وجه − کسر مستند'),deepcopy(face))
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

class PlanarPrism:
 """Exact footprint for the same region-volume/overlap formulas above."""
 def __init__(self,footprint,z0,z1):
  self.footprint=footprint;self.z0=z0;self.z1=z1
  self.bounds=((min(p[0] for p in footprint),min(p[1] for p in footprint),z0),
               (max(p[0] for p in footprint),max(p[1] for p in footprint),z1))
 def __getitem__(self,index):return self.bounds[index]


def planar_box(part,limit,owner,zones=()):
 from core.drawings.planar_geometry import ring,intersection,signed
 from fractions import Fraction
 bounds=box(part,limit)
 points=part.get('footprint') or [(bounds[0][0],bounds[0][1]),(bounds[1][0],bounds[0][1]),(bounds[1][0],bounds[1][1]),(bounds[0][0],bounds[1][1])]
 footprint=ring(points)
 if (min(p[0] for p in footprint),min(p[1] for p in footprint))!=tuple(Fraction(v) for v in bounds[0][:2]) or (max(p[0] for p in footprint),max(p[1] for p in footprint))!=tuple(Fraction(v) for v in bounds[1][:2]):
  raise ValueError('پوش مختصات جزء با رأس‌های واقعی آن یکسان نیست')
 if intersection(owner,footprint)!=abs(signed(footprint)):raise ValueError('جزء از هندسه واقعی سقف خارج است')
 result=PlanarPrism(footprint,bounds[0][2],bounds[1][2])
 if zones and sum((overlap(result,z) for z in zones),Decimal(0))!=volume(result):raise ValueError('جزء وارد ضخامت یا حجم نامعتبر ناحیه شده است')
 return result


def _prism_footprint(value):
 if isinstance(value,PlanarPrism):return value.footprint
 from core.drawings.planar_geometry import ring
 return ring([(value[0][0],value[0][1]),(value[1][0],value[0][1]),(value[1][0],value[1][1]),(value[0][0],value[1][1])])


def _planar_physical_guard(project):
 from core.takeoff.manual_formula_amendments import beam_current
 entries=[]
 for key,record in project.get('reviewed_aec_systems',{}).items():
  current=beam_current(project,key) if key in project.get('beam_amendment_applied',{}) else record
  d=current.get('data',{})
  if d.get('measurement_policy')!=POLICY:continue
  rd=d.get('roof_detail',{});physical=[]
  for group in rd.get('rebars',{}).values():physical.extend(group.get('series',[]))
  physical.extend(rd.get('pieces',[]));physical.extend(rd.get('joist_layout',[]));physical.extend(rd.get('formwork',{}).get('faces',[]));physical.extend(rd.get('shoring',{}).get('props',[]))
  keys={canonical(p['physical_key']) for p in physical if p.get('physical_key')}
  entries.append((key,d.get('building_id'),rd.get('geometry',{}).get('shape')=='documented_planar',keys))
 for i,(key,building,planar,parts) in enumerate(entries):
  for other,other_building,other_planar,other_parts in entries[:i]:
   if (planar or other_planar) and canonical(building)==canonical(other_building) and parts&other_parts:
    raise ValueError('هویت قطعه فیزیکی در سقف دیگری مطالبه شده است؛ مالکیت مشترک بدون سند مستقل دوباره پرداخت نمی‌شود')
