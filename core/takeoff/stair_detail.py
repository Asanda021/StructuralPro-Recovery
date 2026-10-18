"""Stair AEC persistence core; financial integration is deliberately not enabled.

The original specialist/bridge remain authoritative and read-only. A valid
source hash and successful preview do not establish shared physical ownership.
"""
from copy import deepcopy
from decimal import localcontext,Inexact,Rounded
from core.takeoff.roof_detail import review_digest,validate_roof_source
from core.takeoff.shear_wall_detail import _document,canonical
from core.takeoff.reviewed_components import require_text
from core.takeoff.stair_specialist import preview as engine_preview
from core.takeoff.stair_bridge_chat import compile_preview

POLICY='stair_specialist_reviewed_v1'
KINDS=('stair',)
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

def preview(data,engine,require_review=False,*,project_id=None):
 out={'kind':'stair','floor_id':data.get('floor_id'),'system_id':data.get('system_id'),'source_id':data.get('source',{}).get('source_id'),'ready':False,'engineering_ready':False,'commit_allowed':False,'preview_only':True,'rows':[],'takeoff_candidates':[],'blockers':[]}
 try:
  result,compiled=_validated(data,project_id)
  out.update(engineering_ready=True,totals_exact=deepcopy(compiled['totals_exact']),component_calculations=deepcopy(result['component_calculations']),engineering_rows=deepcopy(result['rows']),takeoff_candidates=deepcopy(compiled['takeoff_candidates']),input_sha256=result['input_sha256'])
 except (ValueError,KeyError,TypeError,OSError,AttributeError,ArithmeticError) as exc:out['blockers'].append('دیتایل پله یا مدرک نامعتبر است: '+str(exc))
 out['blockers'].append(PENDING)
 return out

def takeoffs(data,version):
 raise ValueError(PENDING)

def guard(previous,updated):
 """Prevent silent policy conversion and bypass via the shared ProjectStore."""
 reg=updated.get('reviewed_aec_systems',{});seen=set();identities=set();sources=set()
 for key,record in reg.items():
  d=record.get('data',{});old=previous.get('reviewed_aec_systems',{}).get(key,{}).get('data',{})
  if old.get('kind')=='stair' and old.get('measurement_policy')!=d.get('measurement_policy') and POLICY in (old.get('measurement_policy'),d.get('measurement_policy')):raise ValueError('تبدیل خاموش قرارداد تاریخی پله ممنوع است')
  if d.get('measurement_policy')!=POLICY:continue
  if d.get('kind')!='stair':raise ValueError('قرارداد پله در خانواده دیگر مجاز نیست')
  if record.get('status')!='draft':raise ValueError(PENDING)
  dt=d.get('stair_detail',{});physical=dt.get('physical_stair_id')
  if physical:
   identity=canonical(physical)
   if identity in seen:raise ValueError('هویت فیزیکی پله تکراری است')
   seen.add(identity)
  m=dt.get('input',{}).get('metadata',{})
  if m.get('project_id') and m['project_id']!=updated['id']:raise ValueError('پروژه دیتایل پله با SQLite مطابقت ندارد')
  identities.add((d.get('floor_id'),d.get('system_id')));sources.add(d.get('source',{}).get('source_id'))
 for row in updated.get('takeoffs',[]):
  if row in previous.get('takeoffs',[]):continue
  params=row.get('params',{});provenance=row.get('provenance',{})
  if params.get('stair_policy')==POLICY or (row.get('system'),row.get('member_code')) in identities or (provenance.get('source_id') and provenance.get('source_id') in sources):raise ValueError(PENDING)
