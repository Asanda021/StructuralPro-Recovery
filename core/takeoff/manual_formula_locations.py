"""Atomic location changes inside the existing project/register transaction."""
from copy import deepcopy
from uuid import uuid4
from core.takeoff.manual_formula_register import load,save_many,text,revision

def relocate(service,pid,keys,*,destination,mode,expected_revisions,reason,deduction_sources=None):
    if not isinstance(destination,dict) or set(destination)!={'project_id','block','floor','location'}:raise ValueError('پروژه، بلوک، طبقه و محل مقصد باید صریح باشند')
    labels={'project_id':'پروژه','block':'بلوک','floor':'طبقه','location':'محل'}
    dest={k:text(v,'مقصد '+labels[k]) for k,v in destination.items()};text(reason,'علت انتقال یا کپی')
    if dest['project_id']!=pid:raise ValueError('انتقال یا کپی بین پروژه‌ها به گردش مستقل و مجوز مبنا نیاز دارد؛ هیچ پروژه‌ای تغییر نکرد')
    if mode not in {'move','copy'}:raise ValueError('عملیات باید انتقال یا کپی صریح باشد')
    if not keys or len(keys)!=len(set(keys)) or set(keys)!=set(expected_revisions):raise ValueError('ردیف‌ها و نسخه‌ها باید یکتا و صریح باشند')
    reg=load(service,pid);selected=set(keys);proposed={};mapping={k:k if mode=='move' else 'MF-'+uuid4().hex for k in keys}
    if mode=='move' and any(set(v['data']['references'].values()) & selected for k,v in reg.items() if k not in selected):raise ValueError('انتقال باید تمام وابستگان را شامل شود؛ هویت محل مرجع نباید پنهانی تغییر کند')
    for k in keys:
        r=reg[k];revision(expected_revisions[k],r['revision']);d=deepcopy(r['data'])
        if mode=='move' and r['status']=='committed':raise ValueError('انتقال ردیف قطعی نیازمند اصلاحیه مستقل است')
        if mode=='copy' and set(d['references'].values())-selected:raise ValueError('کپی باید همه منابع فرمول را شامل شود')
        if (d.get('block',''),d['floor'],d.get('location',''))==(dest['block'],dest['floor'],dest['location']):raise ValueError('مقصد با محل فعلی یکسان است؛ برداشت دوباره مجاز نیست')
        d.update(block=dest['block'],floor=dest['floor'],location=dest['location'])
        if mode=='copy':
            d['source_id']='manual-formula:'+uuid4().hex;d['references']={n:mapping[t] for n,t in d['references'].items()}
            for item in d['deductions']:
                sid=(deduction_sources or {}).get(k,{}).get(item['id'])
                if not sid or sid==item.get('source_id',item['id']):raise ValueError('کپی کسر به هویت هندسی جدید و صریح نیاز دارد')
                item['variable']=item.get('variable',item['id']);item['id']=text(sid,'منبع جدید کسر');item['source_id']=item['id']
        proposed[mapping[k]]=d
    save_many(service,pid,proposed,expected_revisions=expected_revisions if mode=='move' else {k:0 for k in proposed},expected_dependencies=expected_revisions,reason=reason)
    return mapping
