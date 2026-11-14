"""Project-control adapters for the existing Persian report exporters."""
from datetime import date
from pathlib import Path
from core.reports.project_report import build_report
from core.reports.exporters import report_date,FA_UNITS
from core.projects.scheduling import current as current_schedule
from core.projects.schedule_status import forecast as schedule_forecast
from core.projects.physical_progress import calculate, curve

LABELS={'wbs':'ساختار شکست کار','activities':'فهرست فعالیت‌ها','schedule':'زمان‌بندی و فعالیت‌های بحرانی','progress':'پیشرفت وزنی و انحراف','curve':'منحنی S برنامه‌ای و واقعی'}

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
        current=current_schedule(p)
        driving=current['driving']
        add('شبکه','دامنه محاسبه','تقویم مشترک پروژه' if current['cpm_scope']=='SHARED_PROJECT_WORKDAYS' else 'تقویم مؤثر هر فعالیت')
        add('شبکه','زنجیره‌های محرک پایان',str(driving['path_count'])+('+' if driving['path_count_capped'] else ''))
        if driving['paths_truncated']:
            add('شبکه','فهرست نمونه','فهرست زنجیره‌ها محدود است. روابط حاکم در جدول ثبت شده‌اند.')
        for chain in driving['paths']:
            add('شبکه','زنجیره محرک',' → '.join(chain))
        for rel in driving['edges']:
            add(rel['succ'],'رابطه حاکم بر پایان',f"{rel['pred']} / {rel['type']} / {rel['lag']}")
        if p.get('schedule_status_records'):
            try:
                forecast=schedule_forecast(p)
            except ValueError:
                add('پیش‌بینی','وضعیت','رکورد تاریخ وضعیت نیازمند بازبینی است')
            else:
                for key,label in [('version','نسخه مشاهده'),('data_date','تاریخ وضعیت'),
                                  ('finish_boundary','پایان پیش‌بینی پیشنهادی'),('baseline_finish','پایان مبنا'),
                                  ('baseline_delta_days','اختلاف روز تقویمی با مبنا'),
                                  ('baseline_sha256','هش مبنای مقایسه'),('status_sha256','هش رکورد')]:
                    add('پیش‌بینی',label,forecast[key])
                for row in forecast['activities'].values():
                    if row['state']=='NOT_STARTED':continue
                    for key,label in [('actual_start','شروع مشاهده‌شده'),('actual_finish','پایان مشاهده‌شده'),
                                      ('resume','ادامه پیشنهادی'),('remaining_duration','مدت کاری باقی‌مانده')]:
                        add(row['id'],label,row[key])
                for rel in forecast['out_of_sequence']:
                    add(rel['succ'],'خارج از توالی',f"{rel['pred']} / {rel['type']} / {rel['lag']} | "
                        f"مشاهده: {rel['reported_event']} | قید رابطه: {rel['required_event']}")
        for id,r in current['activities'].items():
            for label,value in [('شروع',report_date(date.fromisoformat(r['start']))),('پایان',report_date(date.fromisoformat(r['finish']))),('مدت روز کاری',r['duration']),('شروع زودترین',r['es']),('پایان زودترین انحصاری',r['ef']),('شروع دیرترین',r['ls']),('پایان دیرترین انحصاری',r['lf']),('شناوری کل',r['total_float']),('شناوری آزاد',r['free_float']),('بحرانی','بله' if r['critical'] else 'خیر')]:add(id,label,value)
        for r in current['relationships']:add(r['succ'],'پیش‌نیاز',f"{r['pred']} / {r['type']} / {r['lag']} روز کاری")
        from core.reports.project_control_figures import gantt_figures
        figures=gantt_figures(p,current,Path(path).with_suffix(''))
    elif kind=='progress':
        if not as_of:raise ValueError('تاریخ گزارش صریح لازم است')
        r=calculate(p,as_of=as_of)
        for key,label in [('actual','پیشرفت واقعی'),('planned','پیشرفت مبنا'),('planned_current','پیشرفت برنامه جاری'),('variance_current','انحراف از برنامه جاری'),('variance','انحراف'),('weight_id','نسخه وزن'),('baseline_id','نسخه مبنا')]:add('کل پروژه',label,r[key])
        for a in r['activities']:
            for key,label in [('title','فعالیت'),('unit','واحد'),('total','مقدار مصوب'),('executed','اجراشده'),('remaining','باقی‌مانده'),('actual','واقعی درصد'),('planned','برنامه مبنا درصد'),('planned_current','برنامه جاری درصد'),('variance','انحراف درصد'),('weight','وزن خام'),('normalized_weight','وزن نرمال درصد'),('source_document','سند کارکرد')]:add(a['id'],label,FA_UNITS.get(a[key],a[key]) if key=='unit' else a[key])
        for group,label in [('floors','طبقه'),('zones','زون'),('disciplines','رشته'),('wbs','WBS')]:
            for id,x in r['groups'][group].items():
                for k,name in [('actual','واقعی'),('planned','برنامه‌ای'),('variance','انحراف'),('weight_sum','جمع وزن')]:add(label+' '+id,name,x.get(k))
    else:
        points=curve(p,'daily')
        for r in points:
            for key,label in [('actual','واقعی درصد'),('planned','برنامه مبنا درصد'),('planned_current','برنامه جاری درصد'),('variance','انحراف درصد'),('report_id','شناسه گزارش'),('baseline_id','نسخه مبنا'),('weight_id','نسخه وزن'),('sha256','هش گزارش')]:add(report_date(date.fromisoformat(r['date'])),label,r[key])
        from core.reports.project_control_figures import curve_figure
        figures=curve_figure(points,Path(path).with_suffix(''))
    baselines=p.get('schedule_baselines',[])
    metadata={'_phase4_presentation':True,'project_id':pid,'عنوان بخش':LABELS[kind],'نسخه پروژه':p['_meta']['version'],'نسخه مبنا':baselines[-1]['id'] if baselines else 'ثبت نشده',
              'تاریخ گزارش شمسی':report_date(date.fromisoformat(as_of)) if as_of else report_date(),
              'قرارداد مدت':'روز کاری؛ پایان انحصاری در محاسبه؛ آخرین روز اشغال در نمایش','_figures':figures}
    return build_report(p['name']+' — '+LABELS[kind],rows,metadata=metadata).export(path,fmt)
