"""Read-only activity handoff to existing, verified drawing/member identities."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from core.projects.controls import find,basis_stale


def targets(service,pid,activity_id):
    p=service.open_project(pid);a=find(p.get('project_schedule_tasks',[]),activity_id,'فعالیت')
    if basis_stale(p,a):raise ValueError('مبنای مقدار فعالیت تغییر کرده است')
    members=set(a.get('member_ids',[]));bindings=[]
    for key,original in (p.get('reviewed_aec_systems') or {}).items():
        record=original
        if key in p.get('beam_amendment_applied',{}):
            from core.takeoff.manual_formula_amendments import beam_current
            record=beam_current(p,key)
        data=record.get('data',{});source=data.get('source',{})
        if data.get('system_id') in members and data.get('floor_id') in a.get('floor_ids',[]) and source.get('roof_binding') and record.get('status')=='committed':
            from core.drawings.roof_region import validate_source
            binding=validate_source(source)
            current=service.load_drawing_takeoff_session(pid,binding['session_id'])
            if current['revision']!=binding['revision'] or current['session']!=binding['session']:raise ValueError('نشست نقشه عضو تغییر نسخه داده است')
            bindings.append((binding['session_id'],binding['item_id']))
    for r in p.get('takeoffs',[]):
        if r.get('source_id') in set(a.get('measurement',{}).get('source_ids',[])) and r.get('drawing_session_id') and r.get('drawing_takeoff_id'):
            bindings.append((r['drawing_session_id'],r['drawing_takeoff_id']))
    result=[]
    for sid,item_id in sorted(set(bindings)):
        record=service.load_drawing_takeoff_session(pid,sid);session=record['session'];source=Path(session['drawing_source'])
        if not source.is_file() or sha256(source.read_bytes()).hexdigest()!=session.get('source_sha256'):raise ValueError('فایل نقشه تغییر کرده یا موجود نیست')
        if not any(i['id']==item_id for i in session['items']):raise ValueError('شناسه ناحیه در نشست موجود نیست')
        result.append({'key':'drawing:'+sid+':'+item_id,'kind':'drawing','path':str(source),'session':deepcopy(record),'item_id':item_id,'label':'ناحیه نقشه — '+item_id})
    for decision in p.get('ifc_identity_reviews',[]):
        if decision['member_id'] not in members or decision['floor_id'] not in a.get('floor_ids',[]):continue
        proposal=decision['proposal_id']
        if any(x.get('supersedes')==proposal for x in p.get('ifc_identity_reviews',[])):continue
        from core.drawings.ifc_pipeline import _binding,lineage_view_binding
        in_lineage=any(proposal in x.get('previous_proposal_ids',[])+x.get('current_proposal_ids',[]) for x in p.get('ifc_identity_lineages',[]))
        bound,_=lineage_view_binding(p,proposal) if in_lineage else _binding(p,proposal)
        result.append({'key':'ifc:'+proposal,'kind':'ifc','path':bound['document']['source_path'],'global_id':bound['global_id'],'label':'عضو IFC — '+bound['member_id']})
    return result
