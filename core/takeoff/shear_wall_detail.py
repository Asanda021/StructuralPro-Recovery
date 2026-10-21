"""Versioned shear-wall integration; Chat engine/bridge remain unchanged.

Only globally located, independent rectangular wall parts are payable here.
Unknown foreign-member geometry and shared interfaces remain fail-closed.
"""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from decimal import Decimal,localcontext,Inexact,Rounded
import json
from core.takeoff.roof_detail import review_digest
from core.commercial.exact_values import exact
from core.takeoff.reviewed_components import require_text
from core.takeoff.shear_wall_specialist_chat import preview as calculate,ident
from core.takeoff.shear_wall_bridge_chat import compile_preview

POLICY='shear_wall_specialist_v1'
KINDS=('shear_wall',)
BAR_LABELS={'vertical':'میلگرد قائم','horizontal':'میلگرد افقی','boundary_longitudinal':'میلگرد طولی مرزی','boundary_ties':'خاموت مرزی','crossties':'سنجاقی','opening_reinforcement':'تقویت بازشو','starters_connections':'انتظار و اتصال'}
def canonical(value):return ident(value,label='هویت مستقل')

LABELS={'concrete_net':'بتن خالص دیوار برشی','formwork_main':'قالب وجه اصلی دیوار برشی','formwork_edge':'قالب وجه جانبی دیوار برشی',**{'rebar_'+k:v for k,v in BAR_LABELS.items()}}

def bind_input_digest(data):
 return sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()).hexdigest()

def new_detail(floor,sid):
 from core.takeoff.reviewed_aec import empty_system,SPECS
 d=empty_system('shear_wall',floor,sid) if floor and sid else {'kind':'shear_wall','floor_id':floor,'system_id':sid,'source':{},'components':{k:{'status':'unreviewed'} for k in SPECS['shear_wall'].components}};d.update(building_id='',axis='',measurement_policy=POLICY,shear_wall_detail={'input':{},'input_document':{'path':'','sha256':'','reference':''},'ownership_document':{'path':'','sha256':'','reference':''}});return d

def _object(v,fields,label):
 if not isinstance(v,dict) or set(v)!=set(fields):raise ValueError(label+' ناقص یا خارج از قرارداد است')

def _document(spec):
 from core.takeoff.structural_handoff_work import parse_request
 _object(spec,('path','sha256','reference'),'مدرک');require_text(spec['reference'],'مرجع مدرک');path=Path(require_text(spec['path'],'مسیر مدرک'));h=require_text(spec['sha256'],'هش مدرک')
 if not path.is_file() or path.stat().st_size>16*1024*1024:raise ValueError('فایل واقعی مدرک یافت نشد یا بیش از حد بزرگ است')
 raw=path.read_bytes()
 if sha256(raw).hexdigest()!=h:raise ValueError('محتوای مدرک با SHA-256 معتبر مطابقت ندارد')
 return parse_request(raw.decode('utf-8-sig'))

def _actors(value):
 actors=[]
 if isinstance(value,dict):
  for k,v in value.items():
   if k in ('approved_by','payment_approved_by','prepared_by'):actors.append(v)
   actors.extend(_actors(v))
 elif isinstance(value,list):
  for v in value:actors.extend(_actors(v))
 return {canonical(a) for a in actors if isinstance(a,str) and a.strip()}

def check_reviewer(data,reviewer):
 actor=canonical(require_text(reviewer,'بازبین مستقل'));owner=_document(data['shear_wall_detail']['ownership_document'])
 if actor in _actors(data)|_actors(owner):raise ValueError('بازبین باید از تهیه‌کننده و تأییدکنندگان دیتایل مستقل باشد')

def _validated(data):
 if data.get('kind')!='shear_wall' or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد تخصصی دیوار برشی لازم است')
 _object({k:v for k,v in data.items() if k!='roof_review'},('kind','floor_id','system_id','building_id','axis','source','measurement_policy','components','shear_wall_detail'),'دیوار برشی')
 for k in ('floor_id','system_id','building_id','axis'):require_text(data.get(k),'هویت و محل دیوار')
 from core.takeoff.roof_detail import validate_roof_source
 validate_roof_source(data['source'],data['system_id'])
 for k in ('plan_ref','detail_ref'):require_text(data['source'].get(k),'پلان و دیتایل')
 if any(v!={'status':'unreviewed'} for v in data['components'].values()):raise ValueError('پرداخت هم‌زمان قرارداد عمومی و تخصصی ممنوع است')
 detail=data['shear_wall_detail'];_object(detail,('input','input_document','ownership_document'),'دیتایل دیوار');e=detail['input']
 if _document(detail['input_document'])!=e:raise ValueError('مدرک ورودی با دیتایل جاری مطابقت ندارد')
 result=calculate(e)
 if data['axis']!=e['datum']['axis_ref']:raise ValueError('محور دفتر با دیتایل و مختصات دیوار یکسان نیست')
 if e['floor_id']!=data['floor_id'] or e['wall_id']!=data['system_id'] or e['source']['source_id']!=data['source']['source_id']:raise ValueError('هویت موتور با دفتر اصلی مطابقت ندارد')
 if e['datum']['orientation']!='positive_x':raise ValueError('تبدیل دستگاه مختصات جهت منفی نیازمند قرارداد مستقل است')
 if e['interfaces'] or any(f.get('contact_rectangles') for f in e['formwork']['main_faces']):raise ValueError('اشتراک بتن یا تماس قالب با عضو دیگر تا قرارداد مالکیت هندسی مشترک مسدود است')
 o=_document(detail['ownership_document']);_object(o,('schema','project_id','physical_wall_id','coordinate_ref','input_digest','input_document_sha256','prepared_by','reviewer','reference','concrete_scopes','formwork_scopes','bar_pieces'),'مالکیت مستقل')
 if o['schema']!='shear_wall_independent_ownership_v1' or any(o[k]!=v for k,v in {'project_id':e['project_id'],'physical_wall_id':e['physical_wall_id'],'coordinate_ref':e['datum']['coordinate_ref'],'input_digest':bind_input_digest(e),'input_document_sha256':detail['input_document']['sha256']}.items()):raise ValueError('سند مالکیت به نسخه، هویت یا مختصات دیگری تعلق دارد')
 for k in ('prepared_by','reviewer','reference'):require_text(o[k],'تهیه‌کننده، بازبین و مرجع مالکیت')
 if canonical(o['reviewer']) in _actors(e)|{canonical(o['prepared_by']),canonical(data['source']['approved_by'])}:raise ValueError('بازبینی مالکیت مستقل نیست')
 parts={v['id'] for v in e['segments']};faces={v['id'] for v in e['formwork']['main_faces']+e['formwork']['edge_faces']};bars={v['physical_bar_set_id']:v for g in e['rebars'].values() for v in g.get('series',[])}
 for field,keys in [('concrete_scopes',parts),('formwork_scopes',faces),('bar_pieces',set(bars))]:
  if not isinstance(o[field],dict) or set(o[field])!=keys:raise ValueError('پوشش مالکیت قطعه، وجه یا میلگرد ناقص است')
 claims=[('part',canonical(s['physical_part_id'])) for s in e['segments']]+[('bar_set',canonical(k)) for k in bars]
 for field,category in [('concrete_scopes','concrete'),('formwork_scopes','formwork')]:
  claims.extend((category,canonical(require_text(v,'هویت فیزیکی محدوده'))) for v in o[field].values())
 for key,bar in bars.items():
  values=o['bar_pieces'][key]
  if not isinstance(values,list) or len(values)!=int(Decimal(str(bar['count']))):raise ValueError('هویت تک‌تک میلگردها با تعداد دیتایل برابر نیست')
  claims.extend(('bar',canonical(require_text(v,'هویت میلگرد فیزیکی'))) for v in values)
 if len(set(claims))!=len(claims):raise ValueError('مالکیت فیزیکی یا میلگرد تکراری است')
 return e,o,result,sorted(claims)

@exact
def preview(data,engine,require_review=False):
 rows=[];errors=[]
 try:
  e,o,result,claims=_validated(data)
  if require_review:
   rv=data.get('roof_review',{});check_reviewer(data,rv.get('reviewer'));require_text(rv.get('note'),'یادداشت بازبینی')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
  compiled=compile_preview(e,{'id':e['project_id'],'takeoffs':[]},reviewer=o['reviewer'],review_reference=o['reference'])
  for v in compiled['preview_rows']:
   row=deepcopy(v);kind=row['params']['physical_kind'];row['description']=LABELS[kind]+' '+data['system_id'];row['method']=POLICY;row['params'].update(shear_wall_policy=POLICY,ownership_claims=[list(v) for v in claims],input_document_sha256=data['shear_wall_detail']['input_document']['sha256'],ownership_document_sha256=data['shear_wall_detail']['ownership_document']['sha256']);rows.append(row)
 except (ValueError,KeyError,TypeError,OSError,AttributeError) as exc:errors.append(str(exc))
 return dict(kind='shear_wall',floor_id=data.get('floor_id'),system_id=data.get('system_id'),source_id=data.get('source',{}).get('source_id'),ready=not errors,blockers=errors,rows=rows,preview_only=True)

def takeoffs(data,version):
 result=preview(data,None)
 if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
 return [{'id':r['source_id'],'source_id':r['source_id'],'member_code':data['system_id'],'system':data['floor_id'],'domain':'building','item':r['item_code'],'description':r['description'],'params':deepcopy(r['params']),'provenance':deepcopy(data['source']),'revision':version,'quantities':[{'code':r['item_code'],'title':r['description'],'unit':r['unit'],'amount':r['quantity'],'role':'work','formula':r['formula'],'price_code':None,'unit_price':None}]} for r in result['rows']]

def _boxes(e):
 return [(tuple(Decimal(str(s[k])) for k in ('x_m','y_m','z_m')),tuple(Decimal(str(s[k]))+Decimal(str(s[d])) for k,d in zip(('x_m','y_m','z_m'),('length_m','thickness_m','height_m')))) for s in e['segments']]

@exact
def project_gate(project,key):
 """Unknown foreign geometry is blocked, never guessed from a member name."""
 from core.takeoff.manual_formula_amendments import beam_current
 reg=project.get('reviewed_aec_systems',{});d=beam_current(project,key)['data'];e,o,_,claims=_validated(d)
 if e['project_id']!=project['id']:raise ValueError('شناسه پروژه موتور با SQLite یکسان نیست')
 used=set(claims);boxes=_boxes(e)
 from core.takeoff.roof_detail import KINDS as roofs
 foreign_kinds=set(roofs)|{'stair','steel_frame','steel_deck','composite_frame','composite_roof','hollow_core','waffle','kromit_roof','precast_roof'}
 if project.get('beam_detail_register') or project.get('reviewed_structural_members'):raise ValueError('عضو تیر، ستون، پی یا شناژ فاقد قرارداد مختصات و مالکیت مشترک سازگار است؛ ثبت دیوار مسدود')
 owned_sources=set()
 for rk,record in reg.items():
  owned_sources.update(record.get('source_ids',[]));owned_sources.update(record.get('committed_source_ids',[]))
  aid=project.get('beam_amendment_applied',{}).get(rk)
  if aid:owned_sources.update(r['source_id'] for r in project['beam_amendments'][aid]['rows'])
  other=record.get('data',{})
  if rk==key:continue
  if other.get('kind') in foreign_kinds:raise ValueError('عضو سازه‌ای دیگر نیازمند تطبیق هندسی و مالکیت مشترک مستند است')
  if other.get('kind')!='shear_wall':
   if other.get('measurement_policy')!='architecture_specialist_v1':raise ValueError('رکورد قدیمی یا خانواده دیگر فاقد قرارداد هندسی سازگار است')
   if other.get('kind') in ('brick_wall','block_wall') and other.get('architecture_detail',{}).get('geometry',{}).get('physical_wall_id') and canonical(other['architecture_detail']['geometry']['physical_wall_id'])==canonical(e['physical_wall_id']):raise ValueError('یک بدنه فیزیکی هم‌زمان دیوار بنایی و بتن‌آرمه قابل پرداخت نیست')
   continue
  if other.get('measurement_policy')!=POLICY:raise ValueError('رکورد تاریخی دیوار برشی بدون مهاجرت و هندسه معتبر مسدود است')
  other=beam_current(project,rk)['data'];oe,oo,_,oc=_validated(other)
  if oe['project_id']!=project['id'] or canonical(oe['datum']['coordinate_ref'])!=canonical(e['datum']['coordinate_ref']):raise ValueError('مختصات جهانی دو دیوار هم‌مرجع نیست')
  if used.intersection(oc):raise ValueError('مالک پرداخت بتن، قالب یا میلگرد بین اعضا تکراری است')
  for a,b in boxes:
   for c,f in _boxes(oe):
    ext=[min(x,y)-max(s,t) for s,x,t,y in zip(a,b,c,f)]
    if all(v>=0 for v in ext):raise ValueError('هم‌پوشانی یا تماس قطعات دیوار نیازمند قرارداد مشترک مستقل است')
 for row in project.get('takeoffs',[]):
  if row.get('source_id') in owned_sources:continue
  raise ValueError('برداشت تاریخی خارج از دفتر AEC فاقد طبقه‌بندی و هندسه قابل تطبیق است')
 return True

def guard(previous,updated):
 from core.takeoff.reviewed_aec import _id
 seen=set();walls=[]
 for key,record in updated.get('reviewed_aec_systems',{}).items():
  d=record.get('data',{});old=previous.get('reviewed_aec_systems',{}).get(key,{}).get('data',{})
  if old.get('kind')=='shear_wall' and old.get('measurement_policy')!=d.get('measurement_policy') and POLICY in (old.get('measurement_policy'),d.get('measurement_policy')):raise ValueError('تبدیل خاموش رکورد تاریخی دیوار ممنوع است')
  if d.get('measurement_policy')!=POLICY:continue
  if d.get('kind')!='shear_wall':raise ValueError('قرارداد دیوار برشی در خانواده دیگر مجاز نیست')
  e=d.get('shear_wall_detail',{}).get('input',{})
  if e.get('physical_wall_id'):
   identity=canonical(e['physical_wall_id'])
   if identity in seen:raise ValueError('هویت فیزیکی دیوار تکراری است')
   seen.add(identity)
   for ok,orec in updated.get('reviewed_aec_systems',{}).items():
    od=orec.get('data',{})
    if ok!=key and od.get('kind')=='shear_wall' and od.get('floor_id')==d.get('floor_id') and canonical(od.get('system_id'))==canonical(d.get('system_id')):raise ValueError('هویت دیوار تاریخی با تخصصی مشترک است')
  if record.get('status')=='committed':
   walls.append(key)
   prior=previous.get('reviewed_aec_systems',{}).get(key,{})
   if prior.get('status')!='committed':
    result=preview(d,None,require_review=True)
    if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
    if not prior or prior.get('revision')!=record.get('revision') or d.get('roof_review',{}).get('base_revision')!=record['revision']-1:raise ValueError('مبنای بازبینی و ثبت دیوار معتبر نیست')
    from core.takeoff.manual_formula_amendments import financial_block
    financial_block(previous)
    expected=takeoffs(d,record['revision']);actual={r.get('source_id'):r for r in updated.get('takeoffs',[])}
    if set(record.get('committed_source_ids',[]))!={r['source_id'] for r in expected}:raise ValueError('هویت ریزمتره قطعی دیوار معتبر نیست')
    fields=('code','title','unit','amount','role','formula','price_code','unit_price')
    for r in expected:
     saved=actual.get(r['source_id'],{})
     if saved.get('params')!=r['params'] or saved.get('provenance')!=d['source'] or len(saved.get('quantities',[]))!=1 or any(saved['quantities'][0].get(f)!=r['quantities'][0].get(f) for f in fields):raise ValueError('ریزمتره قطعی دیوار با موتور و مدرک یکسان نیست')
 if previous.get('takeoffs',[])!=updated.get('takeoffs',[]) or previous.get('beam_amendment_applied',{})!=updated.get('beam_amendment_applied',{}):
  for key in walls:project_gate(updated,key)

def validate_amendment(old,new):
 a=old['shear_wall_detail']['input'];b=new['shear_wall_detail']['input']
 for field in ('project_id','floor_id','wall_id','physical_wall_id','datum','source'):
  if a.get(field)!=b.get(field):raise ValueError('تغییر هویت، مرجع مختصات یا منبع اولیه دیوار در اصلاحیه ممنوع است')

def remap_copy(data,replacements):
 def remap(v):
  if isinstance(v,dict):
   for k,x in v.items():
    if k in ('segment_id','opening_id') and x in replacements:v[k]=replacements[x]
    else:remap(x)
  elif isinstance(v,list):
   for x in v:remap(x)
 remap(data)
 data.pop('roof_review',None);detail=data['shear_wall_detail'];e=detail['input'];e['wall_id']=data['system_id'];e['source']['source_id']=data['source']['source_id'];e['physical_wall_id']=''
 for s in e['segments']:s['physical_part_id']=''
 for f in e['formwork']['edge_faces']:f['physical_face_id']=''
 for group in e['rebars'].values():
  for bar in group.get('series',[]):bar['physical_bar_set_id']=''
 for k in ('input_document','ownership_document'):detail[k]={'path':'','sha256':'','reference':''}
