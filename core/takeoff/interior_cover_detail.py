"""Explicit rectangular interior covering and stock-cut layouts in the AEC ledger.

This is a domain contract adapter, using the existing exact arithmetic,
architecture workflow, SQLite, amendments and report exporters.
"""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
from core.commercial.exact_values import exact,wire
from core.takeoff.architecture_detail import POLICY,COMMON,rect,area,intersection
from core.takeoff.roof_detail import n,strict,checked,canonical,review_digest,validate_roof_source
from core.takeoff.reviewed_components import require_text
CONTRACT='interior_cover_v1'
KINDS=('ceramic_finish','stone_floor','stone_cladding')
GEOMETRY=('physical_surface_id','host_id','space_id','face','plane','shape','length_m','width_m','count','repeat_ref','source_ref','approved_by')
SURFACES=('layer_key','operation','x','y','width_m','height_m','material_ref','payment_unit','payment_ref','opening_ids','deduction_ref','coverage_scope','scope_ref','layout_status','layout_ref')
PIECES=('surface_id','stock_id','piece_type','x','y','width_m','height_m','stock_x','stock_y','cut_ref')
STOCKS=('length_m','width_m','material_ref')
CONSUMPTIONS=('surface_id','operation','basis','thickness_m','rate','rate_ref','material_ref','quantity_unit')
TABLES={'openings':('x','y','width_m','height_m'),'surfaces':SURFACES,'stocks':STOCKS,'pieces':PIECES,'joints':('surface_id','x','y','width_m','height_m'),'consumptions':CONSUMPTIONS}
TITLES={'openings':'بازشوهای مستقل','surfaces':'سطوح و قرارداد نصب','stocks':'قطعات خرید مستند','pieces':'جانمایی و برش قطعات','joints':'ناحیه‌های بند مستند','consumptions':'مصالح نصب؛ اطلاعاتی'}
LABELS={'ceramic_surface':'سطح اجرای کاشی و سرامیک','stone_surface':'سطح اجرای سنگ','installed_pieces':'تعداد قطعات نصب‌شده؛ اطلاعاتی','cut_pieces':'تعداد قطعات برش‌خورده؛ اطلاعاتی','purchase_stock':'تعداد قطعات خرید مستند؛ اطلاعاتی','purchase_area':'مساحت قطعات خرید مستند؛ اطلاعاتی','offcut_area':'باقیمانده واقعی قطعات خرید؛ اطلاعاتی','adhesive':'چسب نصب مستند؛ اطلاعاتی','bedding':'ملات نصب مستند؛ اطلاعاتی','grout':'بندکشی مستند؛ اطلاعاتی'}
FIELD_LABELS={'physical_surface_id':'شناسه فیزیکی سطح','host_id':'شناسه میزبان فیزیکی','plane':'جهت سطح','stock_id':'شناسه قطعه خرید','piece_type':'وضعیت قطعه','stock_x':'ابتدای برش در طول قطعه خرید (متر)','stock_y':'ابتدای برش در عرض قطعه خرید (متر)','cut_ref':'مرجع قطعه و نقشه برش','layout_status':'مبنای جانمایی','layout_ref':'مرجع جانمایی یا مساحت مستقل','basis':'مبنای مصرف مستند','rate':'مصرف مستند (کیلوگرم بر مترمربع)','rate_ref':'مرجع نرخ مصرف','quantity_unit':'واحد مصالح','cut_count':'تعداد واقعی قطعات برش‌خورده','piece_area_m2':'سطح قطعات نصب‌شده (مترمربع)','joint_area_m2':'سطح بندها (مترمربع)','stock_area_m2':'سطح خرید مستند (مترمربع)','stock_used_m2':'سطح برش مستند از خرید (مترمربع)','offcut_area_m2':'باقیمانده واقعی خرید (مترمربع)'}
VALUES={'floor':'کف','ceiling':'سقف','horizontal':'افقی','vertical':'قائم','documented':'جانمایی مستند','area_only':'فقط مساحت؛ شمارش و خرید نامعلوم','full':'قطعه کامل','cut':'قطعه برش‌خورده','net_surface':'سطح خالص مستند','constant_thickness':'ضخامت ثابت مستند','area_rate':'مصرف واحد سطح مستند','litre':'لیتر','عدد':'عدد',**LABELS}
CHOICES={'face':('floor','inside','outside','ceiling'),'plane':('horizontal','vertical'),'operation':('ceramic_surface','stone_surface','adhesive','bedding','grout'),'layout_status':('area_only','documented'),'piece_type':('full','cut'),'basis':('constant_thickness','area_rate'),'quantity_unit':('m3','kg')}

def is_cover(data):return data.get('architecture_detail',{}).get('contract')==CONTRACT

@exact
def preview(data,engine,require_review=False):
 rows=[];errors=[];source=data.get('source',{});kind=data.get('kind')
 try:
  if kind not in KINDS or data.get('measurement_policy')!=POLICY or not is_cover(data):raise ValueError('قرارداد پوشش داخلی معتبر نیست')
  strict(data,('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','architecture_detail','roof_review'),'پوشش داخلی')
  for k in ('building_id','floor_id','system_id','axis'):require_text(data.get(k),'هویت و موقعیت')
  validate_roof_source(source,data['system_id'])
  for k in ('plan_ref','detail_ref'):require_text(source.get(k),'نقشه و دیتایل')
  if any(v!={'status':'unreviewed'} for v in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی هم‌زمان ممنوع است')
  a=data['architecture_detail'];strict(a,('contract','geometry')+tuple(TABLES),'دیتایل پوشش');g=a['geometry'];strict(g,GEOMETRY+('unit',),'هندسه سطح');checked(g)
  for k in ('physical_surface_id','host_id','space_id','repeat_ref'):require_text(g.get(k),'هویت سطح و میزبان و دامنه تکرار')
  if g.get('unit')!='m' or g.get('shape')!='rectangle' or g.get('face') not in ('floor','ceiling','inside','outside') or g.get('plane')!=('horizontal' if g['face'] in ('floor','ceiling') else 'vertical'):raise ValueError('فقط سطح مستطیلی افقی یا قائم با وجه صریح معتبر است')
  if kind=='stone_floor' and g['face']!='floor':raise ValueError('سنگ کف فقط وجه کف را می‌پذیرد؛ پله نیازمند قرارداد مستقل است')
  if kind=='stone_cladding' and g['plane']!='vertical':raise ValueError('سنگ دیوار در این قرارداد فقط سطح قائم داخلی است')
  L,W=n(g.get('length_m'),'طول سطح'),n(g.get('width_m'),'امتداد دوم سطح');count=n(g.get('count'),'تعداد مستقل',integer=True);ids=set();physical=set()
  for name,fields in TABLES.items():
   if not isinstance(a.get(name),list) or len(a[name])>512:raise ValueError('جدول مستقل با حداکثر ۵۱۲ جزء صریح لازم است')
   for p in a[name]:
    strict(p,COMMON+fields,'جزء پوشش');checked(p);i,pk=canonical(p.get('id')),canonical(p.get('physical_key'))
    if '|' in p['id'] or i in ids or pk in physical:raise ValueError('شناسه یا جزء فیزیکی پوشش تکراری است')
    ids.add(i);physical.add(pk)
  holes={}
  for p in a['openings']:
   b=rect(p,L,W)
   if any(intersection(b,h)>0 for h in holes.values()):raise ValueError('بازشو تکراری یا هم‌پوشان است')
   holes[p['id']]=b
  net=L*W-sum((area(h) for h in holes.values()),Decimal(0))
  if net<=0 or not a['surfaces']:raise ValueError('سطح خالص و ردیف پوشش لازم است')
  surfaces={};layer_boxes={};complete={};all_surface_boxes=[]
  def emit(code,q,unit,i,p,formula,role='material'):
   if q==0 and role=='material':return
   rows.append(dict(source_id=f"aec:{kind}:{data['floor_id']}:{data['system_id']}:{i}",line_id=i,item_code=code,quantity=wire(q*count),unit=unit,domain='building',description=LABELS[code]+' '+data['system_id'],formula='تعداد صریح × ('+formula+')',params=wire(deepcopy(p)),component=code,method=POLICY,source_ref=p['source_ref'],role=role))
  for p in a['surfaces']:
   for k in ('layer_key','material_ref','payment_ref','deduction_ref','scope_ref','layout_ref'):require_text(p.get(k),'مدرک مستقل سطح و پرداخت و جانمایی')
   expected='ceramic_surface' if kind=='ceramic_finish' else 'stone_surface'
   if p.get('operation')!=expected or p.get('payment_unit')!='m2' or p.get('layout_status') not in ('area_only','documented') or p.get('coverage_scope') not in ('complete','partial'):raise ValueError('عملیات، واحد یا قرارداد سطح معتبر نیست')
   b=rect(p,L,W);key=canonical(p['layer_key']);boxes=layer_boxes.setdefault(key,[])
   if any(intersection(b,v)>0 for v in boxes):raise ValueError('یک لایه پوشش دوباره شمرده شده است')
   if any(intersection(b,v)>0 for v in all_surface_boxes):raise ValueError('دو پوشش نهایی روی یک محدوده هم‌پوشان هستند')
   all_surface_boxes.append(b);boxes.append(b);links=p.get('opening_ids')
   if not isinstance(links,str):raise ValueError('لینک صریح کسورات لازم است')
   links=links.split('|') if links else [];actual={i for i,h in holes.items() if intersection(b,h)>0}
   if len(links)!=len(set(links)) or set(links)!=actual:raise ValueError('لینک کسورات باید تمام بازشوهای متقاطع را دقیقاً یک بار کسر کند')
   deducted=sum((intersection(b,holes[i]) for i in links),Decimal(0));q=area(b)-deducted
   if q<=0:raise ValueError('سطح خالص پوشش مثبت نیست')
   prior=complete.setdefault(key,[p['coverage_scope'],Decimal(0)])
   if prior[0]!=p['coverage_scope']:raise ValueError('دامنه قطعات یک لایه ناسازگار است')
   prior[1]+=q;surfaces[p['id']]=(p,b,q,{**p,'gross_area_m2':area(b),'deducted_area_m2':deducted,'net_area_m2':q,'repeat_count':count})
  if any(scope=='complete' and q!=net for scope,q in complete.values()):raise ValueError('سطح کامل اعلام‌شده تمام سطح خالص را نمی‌پوشاند')
  stocks={p['id']:(p,n(p.get('length_m'),'طول واقعی خرید'),n(p.get('width_m'),'عرض واقعی خرید')) for p in a['stocks']};used={k:[] for k in stocks};installed={k:[] for k in surfaces};pieces={k:[] for k in surfaces};joints={k:[] for k in surfaces}
  for name in ('pieces','joints'):
   for p in a[name]:
    if p.get('surface_id') not in surfaces:raise ValueError('سطح مرجع جزء یافت نشد')
    surface,b,q,params=surfaces[p['surface_id']]
    if surface['layout_status']!='documented':raise ValueError('مساحت بدون جانمایی نمی‌تواند قطعه یا بند تولید کند')
    box=rect(p,L,W)
    if box[0]<b[0] or box[1]<b[1] or box[2]>b[2] or box[3]>b[3] or any(intersection(box,h)>0 for h in holes.values()) or any(intersection(box,v)>0 for v in installed[p['surface_id']]):raise ValueError('جزء خارج از سطح یا متداخل با قطعه، بند یا بازشو است')
    installed[p['surface_id']].append(box)
    if name=='joints':joints[p['surface_id']].append(box);continue
    if p.get('stock_id') not in stocks or p.get('piece_type') not in ('full','cut'):raise ValueError('قطعه خرید و نوع برش معتبر لازم است')
    stock,sl,sw=stocks[p['stock_id']];require_text(p.get('cut_ref'),'دیتایل قطعه کامل یا نقشه برش')
    if stock.get('material_ref')!=surface['material_ref']:raise ValueError('مشخصات قطعه خرید با سطح سازگار نیست')
    cut=rect(dict(x=p.get('stock_x'),y=p.get('stock_y'),width_m=p['width_m'],height_m=p['height_m']),sl,sw)
    if any(intersection(cut,v)>0 for v in used[p['stock_id']]):raise ValueError('یک بخش قطعه خرید در چند قطعه برش دوباره شمرده شده است')
    if (p['piece_type']=='full')!=(cut==(Decimal(0),Decimal(0),sl,sw)):raise ValueError('وضعیت قطعه کامل و برش‌خورده با ابعاد خرید منطبق نیست')
    used[p['stock_id']].append(cut);pieces[p['surface_id']].append((p,box))
  for sid,(p,b,q,params) in surfaces.items():
   emit(p['operation'],q,'m2',sid,params,'مساحت مستقل سطح − تقاطع کسورات؛ قطعات و خرید دوباره پرداخت نمی‌شوند','work')
   if p['layout_status']=='documented':
    if not pieces[sid] or sum((area(v) for v in installed[sid]),Decimal(0))!=q:raise ValueError('قطعه‌بندی و بندها کل سطح خالص مستند را نمی‌پوشانند')
    params.update(installed_count=len(pieces[sid]),cut_count=sum(v['piece_type']=='cut' for v,box in pieces[sid]),piece_area_m2=sum((area(box) for v,box in pieces[sid]),Decimal(0)),joint_area_m2=sum((area(v) for v in joints[sid]),Decimal(0)))
    emit('installed_pieces',Decimal(len(pieces[sid])),'عدد',sid+'-pieces',params,'تعداد قطعات مستقل جانمایی؛ بدون تقسیم مساحت')
    emit('cut_pieces',Decimal(sum(v['piece_type']=='cut' for v,box in pieces[sid])),'عدد',sid+'-cut',params,'تعداد واقعی قطعات دارای نقشه برش')
  for sid,(p,l,w) in stocks.items():
   require_text(p.get('material_ref'),'مشخصات خرید')
   if not used[sid]:raise ValueError('قطعه خرید بدون جانمایی مرتبط پذیرفته نیست')
   q=sum((area(v) for v in used[sid]),Decimal(0));params={**p,'stock_area_m2':l*w,'stock_used_m2':q,'offcut_area_m2':l*w-q,'repeat_count':count}
   emit('purchase_stock',Decimal(1),'عدد',sid+'-stock',params,'یک قطعه خرید فیزیکی مستند')
   emit('purchase_area',l*w,'m2',sid+'-area',params,'طول واقعی قطعه خرید × عرض واقعی')
   emit('offcut_area',l*w-q,'m2',sid+'-offcut',params,'مساحت قطعه خرید − برش‌های غیرهم‌پوشان واقعی؛ بدون درصد پرت')
  consumed=set()
  for p in a['consumptions']:
   if p.get('surface_id') not in surfaces or p.get('operation') not in ('adhesive','bedding','grout'):raise ValueError('مصالح و سطح مرجع معتبر نیست')
   require_text(p.get('material_ref'),'مشخصات مصالح');require_text(p.get('rate_ref'),'مدرک مصرف یا ضخامت')
   key=(p['surface_id'],p['operation'])
   if key in consumed:raise ValueError('مصرف مصالح یک سطح تکراری است')
   consumed.add(key);q=surfaces[p['surface_id']][2];unit=p.get('quantity_unit')
   if p['operation']=='grout':
    if surfaces[p['surface_id']][0]['layout_status']!='documented':raise ValueError('بندکشی نیازمند جانمایی معتبر بندها است')
    q=sum((area(v) for v in joints[p['surface_id']]),Decimal(0))
    if q<=0:raise ValueError('مصرف بندکشی بدون ناحیه بند مستند معتبر نیست')
   if p.get('basis')=='constant_thickness':
    if unit!='m3' or p.get('rate') not in ('',None):raise ValueError('ضخامت ثابت فقط حجم و بدون نرخ مصرف است')
    q*=n(p.get('thickness_m'),'ضخامت مستند')
   elif p.get('basis')=='area_rate':
    if unit!='kg' or p.get('thickness_m') not in ('',None):raise ValueError('مصرف سطحی این قرارداد فقط جرم مستند است؛ واحد حجمی مصرفی دیگر نیازمند قرارداد معتبر است')
    q*=n(p.get('rate'),'مصرف مستند واحد سطح')
   else:raise ValueError('مبنای مصرف مصالح معتبر نیست')
   emit(p['operation'],q,unit,p['id'],p,('سطح بندهای جانمایی‌شده' if p['operation']=='grout' else 'سطح خالص همین پوشش')+' × ضخامت یا مصرف واحد سطح مستند؛ اطلاعاتی')
  if len({canonical(v['source_id']) for v in rows})!=len(rows):raise ValueError('شناسه ردیف تولیدشده تکراری است')
  if require_review:
   rv=data.get('roof_review',{});require_text(rv.get('reviewer'),'بازبین');require_text(rv.get('note'),'یادداشت')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
 except (ValueError,KeyError,TypeError,AttributeError,OverflowError) as exc:errors.append(str(exc))
 return dict(kind=kind,floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=source.get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)


def remap_copy(data,replacements):
 a=data['architecture_detail'];g=a['geometry'];g['physical_surface_id']='CS-'+uuid4().hex;g['host_id']='CH-'+uuid4().hex
 keys={}
 for p in a['surfaces']:
  keys.setdefault(p.get('layer_key'),'CL-'+uuid4().hex);p['layer_key']=keys[p.get('layer_key')]
  if isinstance(p.get('opening_ids'),str):p['opening_ids']='|'.join(replacements.get(i,i) for i in p['opening_ids'].split('|')) if p['opening_ids'] else ''
 for name in ('pieces','joints','consumptions'):
  for p in a[name]:
   for k in ('surface_id','stock_id'):
    if p.get(k):p[k]=replacements.get(p[k],p[k])

@exact
def guard(project):
 from core.takeoff.manual_formula_amendments import beam_current
 register=project.get('reviewed_aec_systems',{});hosts={};faces={};boxes={};parts=set();wall_geometry={};surface_owners={}
 for key,r in register.items():
  if r.get('data',{}).get('measurement_policy')!=POLICY:continue
  d=beam_current(project,key)['data'];a=d.get('architecture_detail',{});g=a.get('geometry',{});building=canonical(d.get('building_id'))
  for name in TABLES:
   for p in a.get(name,[]):
    if p.get('physical_key'):
     pk=(building,canonical(p['physical_key']))
     if pk in parts:raise ValueError('جزء فیزیکی معماری در چند رکورد تکراری است')
     parts.add(pk)
  if not is_cover(d):
   if g.get('physical_wall_id'):
    for side in ('inside','outside'):wall_geometry[(building,canonical(g['physical_wall_id']),side)]=(str(d.get('floor_id','')),str(g.get('length_m','')),str(g.get('height_m','')),str(g.get('count','')))
    for p in a.get('surfaces',[]):
     if p.get('face') and p.get('surface_id'):faces[(building,canonical(g['physical_wall_id']),p['face'])]=canonical(p['surface_id'])
   continue
  if not all(g.get(k) for k in ('host_id','physical_surface_id','face','length_m','width_m','count')):continue
  face=(building,canonical(g['host_id']),g['face']);identity=tuple(str(d.get(k,'')) for k in ('floor_id','axis'))+tuple(str(g.get(k,'')) for k in ('physical_surface_id','space_id','plane','length_m','width_m','count','repeat_ref'))
  if face in hosts and hosts[face]!=identity:raise ValueError('هویت یا هندسه یک وجه فیزیکی ناسازگار است')
  hosts[face]=identity
  surface=(building,canonical(g['physical_surface_id']))
  if surface in surface_owners and surface_owners[surface]!=face:raise ValueError('هویت سطح نمی‌تواند برای دو وجه یا میزبان به‌کار رود')
  surface_owners[surface]=face
  for p in a.get('surfaces',[]):
   if not all(p.get(k) not in ('',None) for k in ('x','y','width_m','height_m','layer_key')):continue
   b=rect(p,n(g['length_m'],'طول'),n(g['width_m'],'امتداد دوم'));scope=face
   if any(intersection(b,v)>0 for v in boxes.get(scope,[])):raise ValueError('یک پوشش فیزیکی در چند رکورد دوباره شمرده شده است')
   boxes.setdefault(scope,[]).append(b)
 for face,identity in hosts.items():
  if face in faces and faces[face]!=canonical(identity[2]):raise ValueError('هویت سطح پوشش با وجه دیوار موجود ناسازگار است')
  if face in wall_geometry:
   floor,L,H,count=wall_geometry[face]
   if identity[0]!=floor or n(identity[5],'طول')!=n(L,'طول دیوار') or n(identity[6],'امتداد دوم')!=n(H,'ارتفاع دیوار') or n(identity[7],'تعداد')!=n(count,'تعداد دیوار'):raise ValueError('هندسه یا تکرار سطح با دیوار میزبان موجود سازگار نیست')
