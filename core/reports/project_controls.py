"""Project-control adapters for the existing Persian report exporters."""
from datetime import date
from pathlib import Path
from core.reports.project_report import build_report
from core.reports.exporters import report_date,FA_UNITS

LABELS={'wbs':'ساختار شکست کار','activities':'فهرست فعالیت‌ها','schedule':'زمان‌بندی و مسیر بحرانی','progress':'پیشرفت وزنی و انحراف','curve':'منحنی S برنامه‌ای و واقعی'}

def export(service,pid,kind,fmt,path,*,as_of=None):
    if kind not in LABELS:raise ValueError('نوع گزارش کنترل پروژه ناشناخته است')
    p=service.open_project(pid)
    if p is None:raise KeyError(pid)
    rows=[]
    def add(section,label,value):rows.append({'بخش':section,'عنوان':label,'مقدار و مرجع':value if value is not None else 'غیرقابل محاسبه'})
    figures=[]
    if kind=='wbs':
        for r in p.get('project_wbs',[]):
            for key,value in [('شناسه',r['id']),('عنوان',r['title']),('کد',r['code']),('والد',r.get('parent_id') or 'ریشه')]:add(r['code'],key,value)
    elif kind=='activities':
        for a in p.get('project_schedule_tasks',[]):
            for label,value in [('عنوان',a['title']),('WBS',a.get('wbs_id')),('طبقات',', '.join(a.get('floor_ids',[]))),('زون‌ها',', '.join(a.get('zone_ids',[]))),('رشته',a.get('discipline_id')),('اعضا',', '.join(a.get('member_ids',[]))),('واحد',FA_UNITS.get(a.get('unit'),a.get('unit'))),('مقدار مصوب',a.get('measurement',{}).get('total')),('منبع مقدار',str(a.get('measurement',{})))]:add(a['id'],label,value)
    elif kind=='schedule':
        current=service.project_schedule(pid)
        for id,r in current['activities'].items():
            for label,value in [('شروع',report_date(date.fromisoformat(r['start']))),('پایان',report_date(date.fromisoformat(r['finish']))),('مدت روز کاری',r['duration']),('شروع زودترین',r['es']),('پایان زودترین انحصاری',r['ef']),('شروع دیرترین',r['ls']),('پایان دیرترین انحصاری',r['lf']),('شناوری کل',r['total_float']),('شناوری آزاد',r['free_float']),('بحرانی','بله' if r['critical'] else 'خیر')]:add(id,label,value)
        for r in current['relationships']:add(r['succ'],'پیش‌نیاز',f"{r['pred']} / {r['type']} / {r['lag']} روز کاری")
        from core.reports.project_control_figures import gantt_figures
        figures=gantt_figures(p,current,Path(path).with_suffix(''))
    elif kind=='progress':
        if not as_of:raise ValueError('تاریخ گزارش صریح لازم است')
        r=service.project_progress(pid,as_of=as_of)
        for key,label in [('actual','پیشرفت واقعی'),('planned','پیشرفت مبنا'),('planned_current','پیشرفت برنامه جاری'),('variance_current','انحراف از برنامه جاری'),('variance','انحراف'),('weight_id','نسخه وزن'),('baseline_id','نسخه مبنا')]:add('کل پروژه',label,r[key])
        for a in r['activities']:
            for key,label in [('title','فعالیت'),('unit','واحد'),('total','مقدار مصوب'),('executed','اجراشده'),('remaining','باقی‌مانده'),('actual','واقعی درصد'),('planned','برنامه مبنا درصد'),('planned_current','برنامه جاری درصد'),('variance','انحراف درصد'),('weight','وزن خام'),('normalized_weight','وزن نرمال درصد'),('source_document','سند کارکرد')]:add(a['id'],label,FA_UNITS.get(a[key],a[key]) if key=='unit' else a[key])
        for group,label in [('floors','طبقه'),('zones','زون'),('disciplines','رشته'),('wbs','WBS')]:
            for id,x in r['groups'][group].items():
                for k,name in [('actual','واقعی'),('planned','برنامه‌ای'),('variance','انحراف'),('weight_sum','جمع وزن')]:add(label+' '+id,name,x.get(k))
    else:
        points=service.project_progress_curve(pid)
        for r in points:
            for key,label in [('actual','واقعی درصد'),('planned','برنامه مبنا درصد'),('planned_current','برنامه جاری درصد'),('variance','انحراف درصد'),('report_id','شناسه گزارش'),('baseline_id','نسخه مبنا'),('weight_id','نسخه وزن'),('sha256','هش گزارش')]:add(report_date(date.fromisoformat(r['date'])),label,r[key])
        from core.reports.project_control_figures import curve_figure
        figures=curve_figure(points,Path(path).with_suffix(''))
    baselines=p.get('schedule_baselines',[])
    metadata={'project_id':pid,'عنوان بخش':LABELS[kind],'نسخه پروژه':p['_meta']['version'],'نسخه مبنا':baselines[-1]['id'] if baselines else 'ثبت نشده',
              'تاریخ گزارش شمسی':report_date(date.fromisoformat(as_of)) if as_of else report_date(),
              'قرارداد مدت':'روز کاری؛ پایان انحصاری در محاسبه؛ آخرین روز اشغال در نمایش','_figures':figures}
    return build_report(p['name']+' — '+LABELS[kind],rows,metadata=metadata).export(path,fmt)
