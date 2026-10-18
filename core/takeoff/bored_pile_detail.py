"""Stage-one pile adapter in the existing structural register, draft/preview only.

The original 256-digit Decimal engine and read-only bridge are unchanged.
No ownership adjudication, takeoff authorization, or financial migration exists.
"""
from copy import deepcopy
from core.takeoff.bored_pile_specialist_chat import compile_piles
from core.takeoff.bored_pile_bridge_chat import compile_preview
from core.takeoff.shear_wall_detail import _document,canonical
from core.takeoff.reviewed_components import require_text

POLICY='bored_pile_reviewed_draft_v1'
PENDING='ثبت مالی شمع مسدود است؛ مالکیت بتن، کلاهک، ستون، قالب و تک‌تک میلگردها احراز نشده است'

def new_detail(floor,group):
 from core.takeoff.reviewed_structural import empty_member
 d=empty_member('bored_pile',floor,group);d.update(measurement_policy=POLICY,pile_detail={'input':{},'input_document':{'path':'','sha256':'','reference':''},'ownership_document':{'path':'','sha256':'','reference':''},'preflight':{'reviewer':'','ownership_reference_claim':''}});return d

def validated(data,pid=None):
 from core.takeoff.reviewed_structural import _validate_source,KINDS
 if data.get('kind')!='bored_pile' or data.get('measurement_policy')!=POLICY:raise ValueError('قرارداد تخصصی پیش‌نویس شمع لازم است')
 for k in ('floor_id','member_id'):require_text(data.get(k),'هویت گروه شمع')
 _validate_source(data.get('source'),data['member_id'])
 if data.get('geometry')!={} or data.get('formwork')!={'status':'unreviewed'} or data.get('rebars')!={k:{'status':'unreviewed'} for k in KINDS['bored_pile'][4]}:raise ValueError('قرارداد عمومی و تخصصی شمع هم‌زمان مجاز نیست')
 dt=data['pile_detail'];e=dt['input']
 if _document(dt['input_document'])!=e:raise ValueError('محتوای مدرک با دیتایل شمع مطابقت ندارد')
 if e['group_id']!=data['member_id'] or e['floor_id']!=data['floor_id'] or (pid is not None and e['project_id']!=pid):raise ValueError('هویت پروژه، طبقه یا گروه شمع مغایر است')
 s=data['source'];es=e['source']
 if any(s.get(k)!=es.get(k) for k in ('source_id','approved_by')) or s.get('measurement_ref')!=es.get('source_ref'):raise ValueError('منبع بیرونی با منبع دیتایل شمع یکسان نیست')
 return compile_piles(e)

def preview(data,engine=None,*,project_id=None,project=None):
 out={'ready':False,'engineering_ready':False,'commit_allowed':False,'preview_only':True,'rows':[],'takeoff_candidates':[],'blockers':[],'ownership_audit':None}
 try:
  result=validated(data,project_id);dt=data['pile_detail'];e=dt['input'];image=deepcopy(project or {'id':e['project_id'],'takeoffs':[]})
  from core.takeoff.reviewed_structural import REGISTER,_key
  image.get(REGISTER,{}).pop(_key('bored_pile',data['floor_id'],data['member_id']),None)
  r=compile_preview(e,image,independent_reviewer=require_text(dt['preflight'].get('reviewer'),'بازبین پیش‌ارزیابی'),ownership_reference=require_text(dt['preflight'].get('ownership_reference_claim'),'ادعای مرجع مالکیت'))
  out.update(engineering_ready=True,engineering_rows=deepcopy(result['rows']),physical_claims=deepcopy(result['physical_claims']),totals_exact=deepcopy(r['totals']),input_sha256=r['input_sha256'],takeoff_candidates=deepcopy(r['takeoff_candidates']))
 except (ValueError,KeyError,TypeError,OSError,AttributeError,ArithmeticError) as exc:
  out['blockers'].append('دیتایل، مدرک یا هویت شمع نامعتبر است: '+str(exc))
  out['blockers'].append(PENDING)
  return out
 # Ownership is an optional, independent read-only audit. An absent or
 # invalid document never cancels an otherwise valid engineering preview.
 # It also never authorizes BOQ or removes the project-level financial gate.
 owner_doc=dt.get('ownership_document')
 if not isinstance(owner_doc,dict) or not owner_doc.get('path'):
  out['blockers'].append('سند مستقل مالکیت شمع ارائه نشده است')
 else:
  try:
   from core.takeoff.bored_pile_ownership_preflight import read_evidence,audit
   require_text(owner_doc.get('reference'),'مرجع سند مالکیت شمع')
   evidence=read_evidence(owner_doc['path'],owner_doc['sha256'])
   assessment=audit(e,result,evidence)
   out['ownership_audit']=assessment
   out['ownership_document_sha256']=owner_doc['sha256']
   out['blockers'].extend(assessment['blockers'])
  except (ValueError,KeyError,TypeError,OSError,AttributeError) as exc:
   out['blockers'].append('سند مالکیت شمع نامعتبر یا غیرقابل تطبیق است: '+str(exc))
 out['blockers'].append(PENDING)
 return out

def guard(previous,updated):
 from core.takeoff.reviewed_structural import REGISTER,_key
 registries=(REGISTER,'reviewed_aec_systems','beam_detail_register');seen=set();ids=set();sources=set();identities=set();prefixes=[]
 # Never move a specialist payload into AEC/cap or silently change old policy.
 for registry in registries:
  for key,record in updated.get(registry,{}).items():
   d=record.get('data',{});old=previous.get(registry,{}).get(key,{}).get('data',{})
   if old and old.get('measurement_policy')!=d.get('measurement_policy') and POLICY in (old.get('measurement_policy'),d.get('measurement_policy')):raise ValueError('تبدیل خاموش قرارداد شمع ممنوع است')
   if d.get('measurement_policy')!=POLICY:continue
   if registry!=REGISTER or key!=_key('bored_pile',d.get('floor_id',''),d.get('member_id','')):raise ValueError('تنها مسیر مرجع شمع دفتر اعضای سازه‌ای است')
   if record.get('status')!='draft':raise ValueError(PENDING)
   prior_record=previous.get(REGISTER,{}).get(key)
   if prior_record is None and record.get('revision')!=1:raise ValueError('نسخه اولیه شمع باید یک باشد')
   if prior_record is not None and record!=prior_record and record.get('revision')!=prior_record['revision']+1:raise ValueError('نسخه شمع باید یکنواخت افزایش یابد')
   if d['source']['source_id'] in sources:raise ValueError('منبع گروه شمع تکراری است')
   result=validated(d,updated['id']);sources.add(d['source']['source_id']);identities.add((d['floor_id'],d['member_id']));prefixes.append('aec:bored_pile:'+d['floor_id']+':'+d['member_id']+':')
   claims=[p['physical_id'] for p in d['pile_detail']['input']['piles']]+[r['physical_id'] for r in result['rows']]
   for value in claims:
    c=canonical(value)
    if c in seen:raise ValueError('هویت فیزیکی شمع، بتن، قالب یا میلگرد تکراری است')
    seen.add(c)
   for p in d['pile_detail']['input']['piles']:
    if canonical(p['id']) in ids:raise ValueError('شناسه قطعه شمع تکراری است')
    ids.add(canonical(p['id']));identities.add((d['floor_id'],p['id']))
   prior=previous.get(REGISTER,{}).get(key,{}).get('data')
   if prior:
    if any(prior.get(k)!=d.get(k) for k in ('floor_id','member_id','source')) or {(p['id'],p['physical_id']) for p in prior['pile_detail']['input']['piles']}!={(p['id'],p['physical_id']) for p in d['pile_detail']['input']['piles']}:raise ValueError('تغییر هویت یا منبع شمع نیازمند گردش مستقل است')
 # Known historical claims cannot be relabelled as a new specialist group.
 for image in (previous,updated):
  for registry in registries:
   for record in image.get(registry,{}).values():
    d=record.get('data',{})
    if d.get('measurement_policy')==POLICY:continue
    if d.get('kind') in ('bored_pile','pile_foundation'):
     g=d.get('geometry',{})
     values=[g.get(k) for k in ('physical_id','physical_pile_id')]+[d.get('member_id'),d.get('system_id')]
     if any(v and (canonical(v) in seen or canonical(v) in ids or (d.get('floor_id'),v) in identities) for v in values):raise ValueError('شمع تاریخی دارای هویت مشترک است؛ مهاجرت خاموش ممنوع است')
 for image in (previous,updated):
  for record in image.get(REGISTER,{}).values():
   d=record.get('data',{})
   if d.get('measurement_policy')==POLICY:
    sources.add(d.get('source',{}).get('source_id'));identities.add((d.get('floor_id'),d.get('member_id')));prefixes.append('aec:bored_pile:'+d.get('floor_id','')+':'+d.get('member_id','')+':')
 def forbidden(row):
  params=row.get('params',{});provenance=row.get('provenance',{});sids=[row.get('source_id','')]+row.get('source_ids',[])
  return params.get('pile_policy')==POLICY or params.get('bridge_policy')=='bored_pile_aec_bridge_chat_v1' or (row.get('system'),row.get('member_code')) in identities or provenance.get('source_id') in (sources-{None}) or any(str(s).startswith(tuple(prefixes)) for s in sids) or any(params.get(k) and canonical(params[k]) in seen for k in ('physical_pile_id','component_physical_id'))
 for entry in previous.get('structural_member_history',[]):
  if entry.get('previous',{}).get('data',{}).get('measurement_policy')==POLICY and entry not in updated.get('structural_member_history',[]):raise ValueError('حذف تاریخچه شمع ممنوع است')
 for book in ('takeoffs','boq'):
  for row in updated.get(book,[]):
   if row not in previous.get(book,[]) and forbidden(row):raise ValueError(PENDING)
