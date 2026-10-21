"""Stair AEC persistence core; financial integration is deliberately not enabled.

The original specialist/bridge remain authoritative and read-only. A valid
source hash and successful preview do not establish shared physical ownership.
"""
from copy import deepcopy
from decimal import Decimal,localcontext,Inexact,Rounded
from core.commercial.exact_values import exact
from core.takeoff.roof_detail import review_digest,validate_roof_source
from core.takeoff.shear_wall_detail import _document,canonical
from core.takeoff.reviewed_components import require_text
from core.takeoff.stair_specialist import preview as engine_preview
from core.takeoff.stair_bridge_chat import compile_preview

POLICY='stair_specialist_reviewed_v1'
KINDS=('stair',)
BAR_LABELS={'flight_main':'میلگرد اصلی بازو','flight_distribution':'میلگرد توزیعی بازو','flight_top_extra':'تقویت بالای بازو','flight_bottom_extra':'تقویت پایین بازو','landing':'میلگرد پاگرد','starter':'میلگرد انتظار','connection':'میلگرد اتصال','special':'میلگرد ویژه'}
LABELS={'waist_concrete':'بتن شمشیری','step_concrete':'بتن مستقل کف‌پله','landing_concrete':'بتن پاگرد','formwork':'قالب‌بندی پله',**{'rebar_'+k:v for k,v in BAR_LABELS.items()}}
PENDING='ثبت مالی پله تا تکمیل مالکیت مستند بتن، قالب و تک‌تک میلگردها و گردش بازبینی مستقل مسدود است'

def new_detail(floor,sid):
 from core.takeoff.reviewed_aec import SPECS
 return {'kind':'stair','floor_id':floor,'system_id':sid,'building_id':'','axis':'','source':{},'components':{k:{'status':'unreviewed'} for k in SPECS['stair'].components},'measurement_policy':POLICY,'stair_detail':{'input':{},'physical_stair_id':'','input_document':{'path':'','sha256':'','reference':''},'preflight':{'reviewer':'','ownership_reference_claim':''}}}

def _validated(data,project_id):
 from core.takeoff.reviewed_aec import SPECS
 if data.get('measurement_policy')!=POLICY or data.get('kind')!='stair':raise ValueError('قرارداد اتصال تخصصی پله لازم است')
 for k in ('system_id','floor_id','building_id','axis'):require_text(data.get(k),'هویت و محل پله')
 validate_roof_source(data['source'],data['system_id'])
 for k in ('plan_ref','detail_ref'):require_text(data['source'].get(k),'پلان و دیتایل')
 if set(data['components'])!=set(SPECS['stair'].components) or any(v!={'status':'unreviewed'} for v in data['components'].values()):raise ValueError('قرارداد عمومی و تخصصی پله هم‌زمان قابل محاسبه نیستند')
 dt=data['stair_detail'];require_text(dt['physical_stair_id'],'هویت فیزیکی پله');e=dt['input']
 if _document(dt['input_document'])!=e:raise ValueError('فایل دیتایل با ورودی جاری یکسان نیست')
 m=e['metadata']
 if m['floor_id']!=data['floor_id'] or m['stair_id']!=data['system_id'] or (project_id is not None and m['project_id']!=project_id):raise ValueError('هویت پروژه، طبقه یا پله با دفتر جاری مطابقت ندارد')
 # The unchanged geometry engine defines a 65-digit Decimal evaluation of
 # irrational lengths. Scope this context so monetary traps cannot leak in.
 with localcontext() as ctx:
  ctx.prec=512;ctx.traps[Inexact]=False;ctx.traps[Rounded]=False
  result=engine_preview(e)
  compiled=compile_preview(e,{'id':m['project_id'],'takeoffs':[]},source_id=data['source']['source_id'],reviewer=require_text(dt['preflight']['reviewer'],'بازبین پیش‌نمایش'),ownership_reference=require_text(dt['preflight']['ownership_reference_claim'],'ادعای مرجع مالکیت'))
 return result,compiled


def ownership_binding(data):
 from core.takeoff.shear_wall_detail import bind_input_digest
 return bind_input_digest({k:data.get(k) for k in ('kind','floor_id','system_id','building_id','axis','source')}|{'input':data['stair_detail']['input'],'physical_stair_id':data['stair_detail']['physical_stair_id']})

def _authors(data,owner):
 from core.takeoff.shear_wall_detail import _actors
 return _actors(data)|_actors(owner)|{canonical(f['reviewed_by']) for f in data['stair_detail']['input']['form_faces']}

def check_reviewer(data,reviewer):
 owner=_document(data['stair_detail']['ownership_document'])
 if canonical(require_text(reviewer,'بازبین مستقل')) in _authors(data,owner):raise ValueError('بازبین از تهیه‌کننده و تأییدکنندگان دیتایل، قالب و مالکیت مستقل نیست')

@exact
def _ownership(data,result,compiled):
 from core.takeoff.shear_wall_detail import _object
 dt=data['stair_detail'];e=dt['input'];o=_document(dt['ownership_document'])
 _object(o,('schema','project_id','physical_stair_id','coordinate_ref','binding_sha256','input_document_sha256','prepared_by','reviewer','reference','envelope_scope','bounds','allocations'),'سند مالکیت پله')
 if o['schema']!='stair_payment_ownership_v1' or o['project_id']!=e['metadata']['project_id'] or o['physical_stair_id']!=dt['physical_stair_id'] or o['binding_sha256']!=ownership_binding(data) or o['input_document_sha256']!=dt['input_document']['sha256']:raise ValueError('سند مالکیت به هویت، منبع یا نسخه جاری تعلق ندارد')
 for key in ('coordinate_ref','prepared_by','reviewer','reference'):require_text(o[key],'مدرک مالکیت')
 if canonical(o['reviewer']) in _authors(data,o):raise ValueError('بازبین مالکیت مستقل نیست')
 if o['envelope_scope']!='complete_assembly_including_bars_forms_connections':raise ValueError('حدود کل مجموعه شامل اتصال و آرماتور مستند نیست')
 _object(o['bounds'],('min_x_m','max_x_m','min_y_m','max_y_m','min_z_m','max_z_m'),'حدود جهانی مستند')
 bounds={}
 for k,v in o['bounds'].items():
  if not isinstance(v,str):raise ValueError('حدود باید رشته عددی دقیق باشند')
  n=Decimal(v)
  if not n.is_finite():raise ValueError('حدود متناهی لازم است')
  bounds[k]=n
 low=tuple(bounds['min_'+a+'_m'] for a in 'xyz');high=tuple(bounds['max_'+a+'_m'] for a in 'xyz')
 if any(a>=b for a,b in zip(low,high)):raise ValueError('حدود مالکیت نامعتبر است')
 calculations={x['component']:x for x in result['component_calculations']}
 for f in e['flights']:
  x,y,z=map(Decimal,(f['start_x_m'],f['start_y_m'],f['start_top_z_m']));run=Decimal(f['horizontal_run_m']);left=x if f['direction']=='x_positive' else x-run
  a=(left,y,low[2]);b=(left+run,y+Decimal(f['width_m']),Decimal(f['end_top_z_m'])+Decimal(f['riser_m']))
  if (z-low[2])*run<Decimal(f['normal_waist_thickness_m'])*Decimal(calculations[f['id']]['sloped_length_m']) or any(l>s or h<t for l,h,s,t in zip(low,high,a,b)):raise ValueError('حدود مالکیت تمام بازو را پوشش نمی‌دهد')
 for p in e['landings']:
  a=(Decimal(p['x_m']),Decimal(p['y_m']),Decimal(p['top_z_m'])-Decimal(p['thickness_m']));b=(a[0]+Decimal(p['length_m']),a[1]+Decimal(p['width_m']),Decimal(p['top_z_m']))
  if any(l>s or h<t for l,h,s,t in zip(low,high,a,b)):raise ValueError('حدود مالکیت پاگرد را پوشش نمی‌دهد')
 if not isinstance(o['allocations'],list) or not o['allocations']:raise ValueError('حداقل یک عملیات با مالکیت واقعی لازم است')
 available={(r['operation'],r['physical_id']):r for r in result['rows']};bars={r['physical_id']:r for r in e['rebars']};selected=set();claims=[]
 for allocation in o['allocations']:
  _object(allocation,('operation','physical_id','scope_id','bar_pieces'),'تخصیص مالکیت');key=(allocation['operation'],allocation['physical_id'])
  if key not in available or key in selected:raise ValueError('عملیات مالکیت نامعتبر یا تکراری است')
  selected.add(key);scope=canonical(require_text(allocation['scope_id'],'هویت محدوده مستقل'));pieces=allocation['bar_pieces']
  if not isinstance(pieces,list):raise ValueError('فهرست هویت فردی میلگرد لازم است')
  if key[0].startswith('rebar_'):
   if len(pieces)!=int(Decimal(str(bars[key[1]]['count']))):raise ValueError('هویت تک‌تک میلگردها با تعداد دیتایل برابر نیست')
   claims.extend([('bar_set',canonical(key[1])),('bar_scope',scope)]);claims.extend(('bar',canonical(require_text(x,'هویت میلگرد'))) for x in pieces)
  else:
   if pieces:raise ValueError('هویت میلگرد برای عملیات غیرآرماتور مجاز نیست')
   claims.append(('formwork' if key[0]=='formwork' else 'concrete',scope))
 if len(set(claims))!=len(claims):raise ValueError('مالکیت فیزیکی یا میلگرد دوباره شمرده شده است')
 if any(k[0]=='formwork' for k in selected):_form_contract(e,result)
 return o,selected,sorted(claims)

def _form_contract(e,result):
 areas={p['key']:Decimal(p['geometry_area_m2']) for p in result['form_faces']};faces={p['key']:p for p in e['form_faces']};flights={p['id']:p for p in e['flights']};landings={p['id']:p for p in e['landings']};allowed={p['id']+':waist_contact' for p in e['steps']}
 for c in e['connections']:
  f=flights[c['flight_id']];l=landings[c['landing_id']];fk=f['id']+':end_'+c['flight_end'];lk=l['id']+':side_'+c['landing_edge']
  if Decimal(f['start_y_m'])==Decimal(l['y_m']) and Decimal(f['width_m'])==Decimal(l['width_m']) and areas[fk]==areas[lk]:allowed.update((fk,lk))
  if faces[fk]['treatment']=='form' and faces[lk]['treatment']=='form':raise ValueError('دو وجه مرز مشترک قابل پرداخت مضاعف نیستند')
 for p in e['steps']:
  if faces[p['id']+':waist_contact']['treatment']!='contact':raise ValueError('قالب مستقل مرز داخلی کف‌پله و شمشیری مجاز نیست')
 for f in e['form_faces']:
  if f['treatment']=='contact' and f['key'] not in allowed:raise ValueError('تماس خارجی یا بخشی از وجه فاقد قرارداد مشترک معتبر است')

@exact
def payable_totals(rows):
 totals={}
 for r in rows:totals[r['unit']]=totals.get(r['unit'],Decimal(0))+Decimal(r['quantity'])
 return {k:str(v) for k,v in totals.items()}

def preview(data,engine,require_review=False,*,project_id=None):
 out={'kind':'stair','floor_id':data.get('floor_id'),'system_id':data.get('system_id'),'source_id':data.get('source',{}).get('source_id'),'ready':False,'engineering_ready':False,'commit_allowed':False,'preview_only':True,'rows':[],'takeoff_candidates':[],'blockers':[],'excluded_operations':[]}
 try:
  result,compiled=_validated(data,project_id)
  out.update(engineering_ready=True,totals_exact=deepcopy(compiled['totals_exact']),component_calculations=deepcopy(result['component_calculations']),engineering_rows=deepcopy(result['rows']),takeoff_candidates=deepcopy(compiled['takeoff_candidates']),input_sha256=result['input_sha256'])
  if not data['stair_detail'].get('ownership_document',{}).get('path'):out['blockers'].append(PENDING);return out
  owner,selected,claims=_ownership(data,result,compiled)
  if require_review:
   rv=data.get('roof_review',{});check_reviewer(data,rv.get('reviewer'));require_text(rv.get('note'),'یادداشت بازبینی')
   if rv.get('digest')!=review_digest(data):raise ValueError('بازبینی نسخه جاری معتبر نیست')
  for v in compiled['takeoff_candidates']:
   params=deepcopy(v['params']);key=(params['physical_operation'],params['physical_component_id']);q=v['quantities'][0]
   if key not in selected:out['excluded_operations'].append({'operation':key[0],'physical_id':key[1],'reason':'مالکیت احراز نشده؛ خارج از BOQ'});continue
   params.update(stair_policy=POLICY,physical_stair_id=data['stair_detail']['physical_stair_id'],ownership_claims=[list(c) for c in claims],input_document_sha256=data['stair_detail']['input_document']['sha256'],ownership_document_sha256=data['stair_detail']['ownership_document']['sha256'])
   title=LABELS[key[0]]+' '+data['system_id'];out['rows'].append(dict(source_id=v['source_id'],domain='building',item_code=v['item'],component=key[0],description=title,quantity=q['amount'],unit=q['unit'],formula=q['formula'],role='work',method=POLICY,source_ref=params['source_reference'],params=params))
  out['payable_totals_exact']=payable_totals(out['rows'])
  out['ready']=bool(out['rows']);out['commit_allowed']=False  # Only the workflow can authorize a project-level commit.
 except (ValueError,KeyError,TypeError,OSError,AttributeError,ArithmeticError) as exc:out['rows']=[];out['blockers'].append('دیتایل یا مالکیت پله نامعتبر است: '+str(exc))
 return out

def takeoffs(data,version):
 result=preview(data,None)
 if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
 return [dict(id=r['source_id'],source_id=r['source_id'],member_code=data['system_id'],system=data['floor_id'],domain='building',item=r['item_code'],description=r['description'],params=deepcopy(r['params']),provenance=deepcopy(data['source']),revision=version,quantities=[dict(code=r['item_code'],title=r['description'],unit=r['unit'],amount=r['quantity'],role='work',formula=r['formula'],price_code=None,unit_price=None)]) for r in result['rows']]

@exact
def project_gate(project,key):
 from core.takeoff.manual_formula_amendments import beam_current
 d=beam_current(project,key)['data'];r,c=_validated(d,project['id']);o,selected,claims=_ownership(d,r,c)
 if project.get('beam_detail_register') or project.get('reviewed_structural_members'):raise ValueError('تیر، ستون، پی یا شناژ فاقد قرارداد مشترک هندسی و مالکیت سازگار است')
 owned=set()
 for other_key,record in project.get('reviewed_aec_systems',{}).items():
  owned.update(record.get('source_ids',[]));owned.update(record.get('committed_source_ids',[]));aid=project.get('beam_amendment_applied',{}).get(other_key)
  if aid:owned.update(x['source_id'] for x in project['beam_amendments'][aid]['rows'])
  if other_key==key:continue
  other=record['data']
  if other.get('measurement_policy')=='architecture_specialist_v1':continue
  if other.get('measurement_policy')!=POLICY:raise ValueError('عضو تاریخی، دیوار، دال یا خانواده دیگر فاقد قرارداد هندسی مشترک است')
  other=beam_current(project,other_key)['data'];rr,cc=_validated(other,project['id']);oo,ss,oc=_ownership(other,rr,cc)
  if canonical(oo['coordinate_ref'])!=canonical(o['coordinate_ref']):raise ValueError('مرجع مختصات جهانی دو مجموعه یکسان نیست')
  if set(claims).intersection(oc):raise ValueError('مالکیت بتن، قالب یا میلگرد بین دو پله تکراری است')
  if all(min(Decimal(o['bounds']['max_'+a+'_m']),Decimal(oo['bounds']['max_'+a+'_m']))>=max(Decimal(o['bounds']['min_'+a+'_m']),Decimal(oo['bounds']['min_'+a+'_m'])) for a in 'xyz'):raise ValueError('تماس یا هم‌پوشانی محدوده‌ها نیازمند قرارداد مستقل است')
 for row in project.get('takeoffs',[]):
  if row.get('source_id') not in owned:raise ValueError('برداشت تاریخی خارج از دفتر AEC فاقد هندسه و مالکیت قابل تطبیق است')
 return True

def validate_amendment(old,new):
 for k in ('project_id','floor_id','stair_id'):
  if old['stair_detail']['input']['metadata'][k]!=new['stair_detail']['input']['metadata'][k]:raise ValueError('تغییر هویت اولیه پله در اصلاحیه ممنوع است')
 if old['stair_detail']['physical_stair_id']!=new['stair_detail']['physical_stair_id']:raise ValueError('تغییر هویت فیزیکی در اصلاحیه ممنوع است')
 a=_document(old['stair_detail']['ownership_document']);b=_document(new['stair_detail']['ownership_document'])
 if canonical(a['coordinate_ref'])!=canonical(b['coordinate_ref']):raise ValueError('تغییر دستگاه مختصات در اصلاحیه ممنوع است')

def remap_copy(data,replacements):
 dt=data['stair_detail'];dt['physical_stair_id']='';dt['input']['metadata']['stair_id']=data['system_id']
 def visit(v):
  if isinstance(v,dict):
   for k,x in v.items():
    if k in ('owner_id','flight_id','landing_id') and x in replacements:v[k]=replacements[x]
    elif k=='key' and isinstance(x,str):v[k]=':'.join(replacements.get(p,p) for p in x.split(':'))
    elif k in ('physical_id','reviewed_by'):v[k]=''
    else:visit(x)
  elif isinstance(v,list):
   for x in v:visit(x)
 visit(dt['input']);dt['preflight']={'reviewer':'','ownership_reference_claim':''}
 for k in ('input_document','ownership_document'):dt[k]={'path':'','sha256':'','reference':''}

def guard(previous,updated):
 reg=updated.get('reviewed_aec_systems',{});seen=set();active=[];stair_keys={};stair_sources={}
 for key,record in reg.items():
  d=record.get('data',{});prior=previous.get('reviewed_aec_systems',{}).get(key,{});old=prior.get('data',{})
  if old.get('kind')=='stair' and old.get('measurement_policy')!=d.get('measurement_policy') and POLICY in (old.get('measurement_policy'),d.get('measurement_policy')):raise ValueError('تبدیل خاموش قرارداد تاریخی پله ممنوع است')
  if d.get('measurement_policy')!=POLICY:continue
  if d.get('kind')!='stair':raise ValueError('قرارداد پله در خانواده دیگر مجاز نیست')
  stair_keys[(d.get('floor_id'),d.get('system_id'))]=record;stair_sources[d.get('source',{}).get('source_id')]=record
  dt=d.get('stair_detail',{});physical=dt.get('physical_stair_id')
  if physical:
   identity=canonical(physical)
   if identity in seen:raise ValueError('هویت فیزیکی پله تکراری است')
   seen.add(identity)
  m=dt.get('input',{}).get('metadata',{})
  if m.get('project_id') and m['project_id']!=updated['id']:raise ValueError('پروژه دیتایل با SQLite مطابقت ندارد')
  if record.get('status')!='committed':continue
  active.append(key)
  if prior.get('status')=='committed':continue
  result=preview(d,None,require_review=True,project_id=updated['id'])
  if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
  if not prior or prior.get('revision')!=record.get('revision') or d.get('roof_review',{}).get('base_revision')!=record['revision']-1:raise ValueError('مبنای بازبینی و ثبت پله معتبر نیست')
  from core.takeoff.manual_formula_amendments import financial_block
  financial_block(previous);expected=takeoffs(d,record['revision']);actual={r.get('source_id'):r for r in updated.get('takeoffs',[])}
  if set(record.get('committed_source_ids',[]))!={r['source_id'] for r in expected}:raise ValueError('هویت ریزمتره قطعی معتبر نیست')
  for r in expected:
   saved=actual.get(r['source_id'],{});q=saved.get('quantities',[])
   if saved.get('params')!=r['params'] or saved.get('provenance')!=d['source'] or len(q)!=1 or any(q[0].get(k)!=r['quantities'][0].get(k) for k in ('code','title','unit','amount','role','formula','price_code','unit_price')):raise ValueError('ریزمتره با دیتایل و مالکیت معتبر برابر نیست')
 for row in updated.get('takeoffs',[]):
  if row in previous.get('takeoffs',[]):continue
  record=stair_keys.get((row.get('system'),row.get('member_code'))) or stair_sources.get(row.get('provenance',{}).get('source_id'))
  if record is not None and record.get('status')!='committed':raise ValueError('ریزمتره پله بازبینی و ثبت قطعی نشده است')
  if row.get('params',{}).get('stair_policy')==POLICY and record is None:raise ValueError('ردیف پله فاقد عضو قطعی ثبت‌شده است')
 if stair_keys:
  approved=set()
  for record in reg.values():
   if record.get('status')=='committed':approved.update(record.get('committed_source_ids',[]))
  for aid in updated.get('beam_amendment_applied',{}).values():approved.update(r['source_id'] for r in updated['beam_amendments'][aid]['rows'])
  for row in updated.get('boq',[]):
   if row in previous.get('boq',[]) or not str(row.get('item_code','')).startswith('stair_'):continue
   ids=row.get('source_ids') or ([row['source_id']] if row.get('source_id') else [])
   if not ids or not set(ids)<=approved:raise ValueError('BOQ پله فاقد ریزمتره قطعی با هویت معتبر است')
 for a in updated.get('beam_amendments',{}).values():
  if a.get('proposal',{}).get('measurement_policy')==POLICY and a.get('status') in ('reviewed','applied'):
   actor=a['review']['reviewer'];check_reviewer(a['proposal'],actor)
   if canonical(actor)==canonical(a['created_by']):raise ValueError('بازبین اصلاحیه همان درخواست‌کننده است')
 if previous.get('takeoffs',[])!=updated.get('takeoffs',[]) or previous.get('beam_amendment_applied',{})!=updated.get('beam_amendment_applied',{}):
  for key in active:project_gate(updated,key)
