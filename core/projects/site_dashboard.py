"""Read-only operational projection; missing evidence remains explicit."""
from copy import deepcopy
from core.projects.controls import digest
from core.projects.scheduling import WorkCalendar,current

def snapshot(p,*,as_of,days=7,end=None):
    WorkCalendar.valid_date(as_of)
    from core.projects.physical_progress import calculate
    from core.projects.site_resources import lookahead,capacity
    from core.projects.site_materials import snapshot as materials
    from core.commercial.financial_ledger import verified_snapshot
    out={'project_id':p['id'],'as_of':as_of,'revision':p.get('_meta',{}).get('version'),'missing_message':'اطلاعات کافی ثبت نشده است','errors':{}}
    for key,fn in [('progress',lambda:calculate(p,as_of=as_of)),('schedule',lambda:current(p)),('lookahead',lambda:lookahead(p,start=as_of,days=days,end=end)),('materials',lambda:materials(p,as_of=as_of)),('finance',lambda:verified_snapshot(p))]:
        try:out[key]=fn()
        except ValueError as exc:out[key]=None;out['errors'][key]=str(exc)
    out['resources']=[{**deepcopy(r),'available_capacity':str(c) if (c:=capacity(p,r,as_of)) is not None else None,'assignments':[deepcopy(x) for x in p.get('resource_assignments',[]) if x['resource_id']==r['id']]} for r in p.get('project_resources',[]) if 'capacity' in r]
    from core.projects.site_office import snapshot as office
    out['office']=office(p,as_of=as_of)
    out['source_collections']={k:deepcopy(p.get(k,[])) for k in ('progress_reports','progress_documents','schedule_baselines','resource_assignments','resource_events','project_materials','material_requirements','purchase_drafts','financial_records','statement_periods')}
    out['source_digest']=digest({k:v for k,v in p.items() if k!='_meta'})
    return out
