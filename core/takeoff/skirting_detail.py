"""Documented linear skirting adapter in the existing architecture AEC contract."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
from core.commercial.exact_values import exact,wire
from core.takeoff.architecture_detail import POLICY,COMMON
from core.takeoff.roof_detail import n,strict,checked,canonical,review_digest,validate_roof_source
from core.takeoff.reviewed_components import require_text
CONTRACT='interior_skirting_v1'
GEOMETRY=('physical_space_id','space_id','count','repeat_ref','corner_status','corner_ref','source_ref','approved_by')
TABLES={'runs':('side_key','length_m','height_m','material_ref','payment_ref','layout_status','layout_ref','deduction_ref'),'openings':('run_id','start_m','length_m'),'stocks':('length_m','material_ref'),'pieces':('run_id','stock_id','start_m','length_m','stock_start_m','piece_type','cut_ref'),'corners':('run_id','at_m','corner_type','detail_ref')}
TITLES={'runs':'اضلاع دارای قرنیز','openings':'درگاه و بخش فاقد اجرا','stocks':'قطعات خرید مستند','pieces':'آرایش قطعات و برش','corners':'کنج‌های دارای دیتایل مستقل'}
LABELS={'skirting_work':'طول خالص اجرای قرنیز','skirting_pieces':'قطعات نصب‌شده قرنیز؛ اطلاعاتی','skirting_cuts':'قطعات برش‌خورده قرنیز؛ اطلاعاتی','skirting_stock':'قطعات خرید قرنیز؛ اطلاعاتی','skirting_purchase_length':'طول خرید مستند قرنیز؛ اطلاعاتی','skirting_offcut_length':'باقیمانده واقعی خرید قرنیز؛ اطلاعاتی','skirting_corners':'کنج‌های مستند قرنیز؛ اطلاعاتی'}
FIELD_LABELS={'physical_space_id':'هویت فیزیکی محدوده قرنیز','side_key':'هویت ضلع فیزیکی','run_id':'شناسه ضلع مرجع','start_m':'ابتدای بازه (متر)','stock_start_m':'ابتدای برش روی قطعه خرید (متر)','at_m':'محل کنج روی ضلع (متر)','corner_type':'نوع کنج','corner_status':'وضعیت دیتایل کنج','corner_ref':'مرجع وضعیت کنج','detail_ref':'مرجع دیتایل مستقل','gross_length_m':'طول ناخالص (متر)','deducted_length_m':'طول کسورات (متر)','net_length_m':'طول خالص (متر)','offcut_length_m':'باقیمانده واقعی طول خرید (متر)'}
VALUES={'length_only':'فقط طول؛ خرید و تعداد نامعلوم','unknown':'نیازمند اطلاعات','not_applicable':'عدم کاربرد مستند','inner':'کنج داخلی','outer':'کنج خارجی',**LABELS}
CHOICES={'layout_status':('length_only','documented'),'corner_type':('inner','outer'),'corner_status':('unknown','not_applicable','documented'),'piece_type':('full','cut')}
def is_skirting(d):return d.get('architecture_detail',{}).get('contract')==CONTRACT

def interval(p,limit,start='start_m'):
 s=n(p.get(start),'ابتدای بازه',True);e=s+n(p.get('length_m'),'طول واقعی')
 if e>limit:raise ValueError('بازه خارج از طول مستند است')
 return s,e

def overlap(a,b):return min(a[1],b[1])-max(a[0],b[0])>0

@exact
def preview(d,engine,require_review=False):
 rows=[];errors=[];source=d.get('source',{})
 try:
  if d.get('kind')!='floor_finish' or d.get('measurement_policy')!=POLICY or not is_skirting(d):raise ValueError('قرارداد طولی قرنیز معتبر نیست')
  strict(d,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','architecture_detail','roof_review'),'قرنیز')
  for k in ('building_id','floor_id','system_id','axis'):require_text(d.get(k),'هویت و موقعیت')
  validate_roof_source(source,d['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(v!={'status':'unreviewed'} for v in d['components'].values()):raise ValueError('قرارداد عمومی هم‌زمان ممنوع است')
  a=d['architecture_detail'];strict(a,('contract','geometry')+tuple(TABLES),'دیتایل قرنیز');g=a['geometry'];strict(g,GEOMETRY+('unit',),'محدوده قرنیز');checked(g)
  for k in ('physical_space_id','space_id','repeat_ref','corner_ref'):require_text(g.get(k),'هویت و مرجع محدوده و کنج')
  if g.get('unit')!='m' or g.get('corner_status') not in ('unknown','not_applicable','documented'):raise ValueError('واحد یا وضعیت کنج معتبر نیست')
  count=n(g.get('count'),'تعداد مستقل',integer=True);ids=set();physical=set()
  for name,fields in TABLES.items():
   if not isinstance(a.get(name),list) or len(a[name])>512:raise ValueError('جدول مستقل و محدود لازم است')
   for p in a[name]:
    strict(p,COMMON+fields,'جزء قرنیز');checked(p);i,pk=canonical(p.get('id')),canonical(p.get('physical_key'))
    if i in ids or pk in physical:raise ValueError('شناسه یا جزء فیزیکی قرنیز تکراری است')
    ids.add(i);physical.add(pk)
  if not a['runs']:raise ValueError('ضلع دارای دیتایل لازم است')
  runs={};sides=set()
  for p in a['runs']:
   for k in ('side_key','material_ref','payment_ref','layout_ref','deduction_ref'):require_text(p.get(k),'هویت و مرجع ضلع')
   if p.get('layout_status') not in ('length_only','documented') or canonical(p['side_key']) in sides:raise ValueError('ضلع یا مبنای جانمایی تکراری یا نامعتبر است')
   sides.add(canonical(p['side_key']));L=n(p.get('length_m'),'طول ضلع');n(p.get('height_m'),'ارتفاع مقطع قرنیز');runs[p['id']]=dict(p=p,L=L,holes=[],pieces=[])
  for p in a['openings']:
   if p.get('run_id') not in runs:raise ValueError('ضلع مرجع کسورات موجود نیست')
   r=runs[p['run_id']];b=interval(p,r['L'])
   if any(overlap(b,v) for v in r['holes']):raise ValueError('درگاه یا کسر تکراری و هم‌پوشان است')
   r['holes'].append(b)
  stocks={p['id']:dict(p=p,L=n(p.get('length_m'),'طول خرید'),cuts=[]) for p in a['stocks']}
  for p in a['pieces']:
   if p.get('run_id') not in runs or p.get('stock_id') not in stocks or p.get('piece_type') not in ('full','cut'):raise ValueError('ضلع، قطعه خرید و نوع قطعه معتبر لازم است')
   require_text(p.get('cut_ref'),'مرجع برش');r=runs[p['run_id']];s=stocks[p['stock_id']]
   if r['p']['layout_status']!='documented' or r['p']['material_ref']!=s['p'].get('material_ref'):raise ValueError('جانمایی و مصالح قطعه خرید منطبق نیست')
   b=interval(p,r['L']);c=interval(p,s['L'],'stock_start_m')
   if any(overlap(b,v) for v in r['holes']) or any(overlap(b,v[1]) for v in r['pieces']) or any(overlap(c,v) for v in s['cuts']):raise ValueError('قطعه در محل درگاه یا قطعه دیگر هم‌پوشان است')
   if (p['piece_type']=='full')!=(c==(Decimal(0),s['L'])):raise ValueError('وضعیت قطعه کامل با طول خرید منطبق نیست')
   r['pieces'].append((p,b));s['cuts'].append(c)
  def emit(code,q,unit,i,p,formula,role='material'):
   if q==0 and role=='material':return
   rows.append(dict(source_id=f"aec:floor_finish:{d['floor_id']}:{d['system_id']}:{i}",line_id=i,item_code=code,quantity=wire(q*count),unit=unit,domain='building',description=LABELS[code]+' '+d['system_id'],formula='تعداد صریح × ('+formula+')',params=wire(deepcopy(p)),component=code,method=POLICY,source_ref=p['source_ref'],role=role))
  for rid,r in runs.items():
   p=r['p'];deduct=sum((e-s for s,e in r['holes']),Decimal(0));q=r['L']-deduct
   if q<=0:raise ValueError('طول خالص قرنیز باید مثبت باشد')
   params={**p,'gross_length_m':r['L'],'deducted_length_m':deduct,'net_length_m':q,'repeat_count':count};emit('skirting_work',q,'m',rid,params,'طول واقعی ضلع − بازه‌های مستقل درگاه و عدم اجرا','work')
   if p['layout_status']=='documented':
    if not r['pieces'] or sum((e-s for v,(s,e) in r['pieces']),Decimal(0))!=q:raise ValueError('قطعات مستند تمام طول خالص را نمی‌پوشانند')
    params.update(installed_count=len(r['pieces']),cut_count=sum(v['piece_type']=='cut' for v,b in r['pieces']))
    emit('skirting_pieces',Decimal(len(r['pieces'])),'عدد',rid+'-pieces',params,'تعداد واقعی جانمایی')
    emit('skirting_cuts',Decimal(sum(v['piece_type']=='cut' for v,b in r['pieces'])),'عدد',rid+'-cuts',params,'قطعات دارای نقشه برش')
  for sid,s in stocks.items():
   require_text(s['p'].get('material_ref'),'مشخصات خرید')
   if not s['cuts']:raise ValueError('خرید بدون جانمایی قطعه پذیرفته نیست')
   used=sum((e-b for b,e in s['cuts']),Decimal(0));params={**s['p'],'offcut_length_m':s['L']-used};emit('skirting_stock',Decimal(1),'عدد',sid+'-stock',params,'یک قطعه خرید فیزیکی مستند');emit('skirting_purchase_length',s['L'],'m',sid+'-length',params,'طول واقعی خرید مستقل');emit('skirting_offcut_length',s['L']-used,'m',sid+'-offcut',params,'طول خرید − برش‌های واقعی؛ بدون درصد پرت')
  if (g['corner_status']=='documented')!=bool(a['corners']):raise ValueError('وضعیت کنج با جدول دیتایل مستقل منطبق نیست')
  corners=set()
  for p in a['corners']:
   if p.get('run_id') not in runs or p.get('corner_type') not in ('inner','outer'):raise ValueError('کنج یا ضلع مرجع معتبر نیست')
   require_text(p.get('detail_ref'),'دیتایل کنج');r=runs[p['run_id']];at=n(p.get('at_m'),'محل کنج',True);key=(p['run_id'],at)
   if at>r['L'] or any(s<at<e for s,e in r['holes']) or key in corners:raise ValueError('کنج تکراری، خارج از ضلع یا در درگاه است')
   corners.add(key);emit('skirting_corners',Decimal(1),'عدد',p['id'],p,'کنج مستقل با دیتایل؛ بدون تولید خودکار از تعداد اضلاع')
  if len({canonical(v['source_id']) for v in rows})!=len(rows):raise ValueError('شناسه ردیف تولیدشده تکراری است')
  if require_review:
   rv=d.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین');require_text(rv.get('note'),'یادداشت')
   if rv.get('digest')!=review_digest(d):raise ValueError('بازبینی نسخه جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=d.get('kind'),floor_id=d.get('floor_id'),system_id=d.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

def remap_copy(d,replacements):
 a=d['architecture_detail'];a['geometry']['physical_space_id']='KS-'+uuid4().hex
 for p in a['runs']:p['side_key']='KE-'+uuid4().hex
 for name in ('openings','pieces','corners'):
  for p in a[name]:
   for k in ('run_id','stock_id'):
    if p.get(k):p[k]=replacements.get(p[k],p[k])

def guard(project):
 from core.takeoff.manual_formula_amendments import beam_current
 owners={};sides=set();parts=set()
 for key,r in project.get('reviewed_aec_systems',{}).items():
  if r.get('data',{}).get('measurement_policy')!=POLICY:continue
  d=beam_current(project,key)['data'];a=d.get('architecture_detail',{});b=canonical(d.get('building_id'))
  for table in a.values():
   if isinstance(table,list):
    for p in table:
     if isinstance(p,dict) and p.get('physical_key'):
      pk=(b,canonical(p['physical_key']))
      if pk in parts:raise ValueError('جزء فیزیکی معماری در چند رکورد تکراری است')
      parts.add(pk)
  if not is_skirting(d):continue
  g=a.get('geometry',{});space=(b,canonical(g.get('physical_space_id')));identity=tuple(str(d.get(k,'')) for k in ('floor_id','axis'))+tuple(str(g.get(k,'')) for k in ('space_id','count','repeat_ref'))
  if g.get('physical_space_id'):
   if space in owners and owners[space]!=identity:raise ValueError('هویت یا دامنه فضای قرنیز ناسازگار است')
   owners[space]=identity
  for p in a.get('runs',[]):
   if p.get('side_key'):
    k=space+(canonical(p['side_key']),)
    if k in sides:raise ValueError('یک ضلع قرنیز در چند رکورد دوباره شمرده شده است')
    sides.add(k)
