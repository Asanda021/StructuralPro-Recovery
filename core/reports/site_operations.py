"""Small adapters to the existing editable Persian report infrastructure."""
from datetime import date
from core.projects.controls import digest
from core.reports.exporters import report_date
from core.reports.project_report import build_report

LABELS={'lookahead':'برنامه عملیاتی','resources':'اکیپ‌ها و تجهیزات','materials':'نیاز، موجودی و کسری مصالح','purchases':'درخواست خرید پیش‌نویس','daily':'گزارش روزانه کارگاه','obstacles':'موانع و توقفات','meetings':'صورت‌جلسات و اقدامات','correspondence':'مکاتبات و RFI','package':'بسته اسناد دفتر فنی','dashboard':'خلاصه مدیریتی پروژه'}
WORDS={'project_id':'پروژه','id':'شناسه','quantity':'مقدار','unit':'واحد','status':'وضعیت','source':'منبع','sha256':'SHA-256','date':'تاریخ','start':'شروع','end':'پایان','finish':'پایان فعالیت','title':'عنوان','activity_id':'فعالیت','floor_ids':'طبقات','zone_ids':'زون‌ها','responsible':'مسئول','resources':'منابع','shortage':'کسری','on_hand':'موجودی مستند','free_stock':'موجودی آزاد','reserved':'رزرو','consumed':'مصرف','material_code':'کد مصالح','specification':'مشخصات','basis_digest':'هش مبنا','actual':'پیشرفت واقعی','planned':'پیشرفت مبنا','planned_current':'پیشرفت برنامه جاری','variance':'انحراف از مبنا','variance_current':'انحراف از برنامه جاری','source_ids':'شناسه منابع','price':'نرخ مستند','currency':'واحد پول','supplier':'تأمین‌کننده','reason':'دلیل','reasons':'دلایل محدودیت','created_by':'تهیه‌کننده','reviewed_by':'بازبین','approved_by':'تأییدکننده','reference':'شماره سند','version':'نسخه','template_version':'نسخه قالب','ready':'قابل اجرا','dependent':'وابسته به پیش‌نیاز','insufficient_information':'اطلاعات ناکافی','resource_conflict':'تداخل منابع','human_decision':'نیازمند تصمیم انسانی','draft':'پیش‌نویس','reviewed':'بازبینی‌شده','approved':'تأییدشده','issued':'صادرشده'}

def export(service,pid,kind,fmt,path,*,as_of,days=7,end=None,document_id=None):
    if kind not in LABELS:raise ValueError('گزارش کارگاه نامعتبر است')
    p=service.open_project(pid)
    if p is None:raise KeyError(pid)
    from core.projects.site_office import snapshot as office
    if kind=='lookahead':data=service.site_lookahead(pid,start=as_of,days=days,end=end)
    elif kind=='resources':data={k:p.get(k,[]) for k in ('project_resources','resource_assignments','resource_availability','resource_events')}
    elif kind in {'materials','purchases'}:
        data=service.site_materials(pid,as_of=as_of)
        if kind=='purchases':data=data['purchase_drafts']
    elif kind=='dashboard':
        data=service.site_dashboard(pid,as_of=as_of,days=days,end=end)
        data.pop('source_collections',None)
        if data.get('schedule'):data['schedule']={k:data['schedule'][k] for k in ('duration','critical_ids','start','finish_boundary')}
        if data.get('finance'):data['finance'].pop('documents',None)
    else:
        snap=office(p,as_of=as_of);key={'daily':'daily_reports','obstacles':'obstacles','meetings':'meetings','correspondence':'correspondence','package':'packages'}[kind];data=snap[key]
        if document_id is not None:
            data=[x for x in data if x['id']==document_id]
            if not data:raise ValueError('سند انتخاب‌شده موجود نیست')
    rows=[]
    def walk(value,section):
        if isinstance(value,dict):
            for k,v in value.items():
                if k in {'snapshot_base64','stock_state'}:continue
                walk(v,section+' / '+WORDS.get(k,k))
        elif isinstance(value,list):
            if not value:rows.append({'بخش':section,'مقدار و مرجع':'رکوردی ثبت نشده است'})
            for i,v in enumerate(value):walk(v,section+' / '+str(v.get('id',i+1) if isinstance(v,dict) else i+1))
        else:
            shown='نامشخص' if value is None else 'بله' if value is True else 'خیر' if value is False else str(value)
            try:
                if isinstance(value,str) and len(value)==10:shown=report_date(date.fromisoformat(value))
            except ValueError:pass
            rows.append({'بخش':section,'مقدار و مرجع':WORDS.get(shown,shown)})
    walk(data,LABELS[kind])
    metadata={'project_id':pid,'عنوان بخش':LABELS[kind],'تاریخ شمسی':report_date(date.fromisoformat(as_of)),'نسخه پروژه':p['_meta']['version'],'نسخه قالب':'site-operations-1','SHA-256 داده گزارش':digest(data),'محدودیت هویت':'اظهار مستند محلی؛ بدون امضای احراز‌شده'}
    return build_report(p['name']+' — '+LABELS[kind],rows,metadata=metadata).export(path,fmt)
