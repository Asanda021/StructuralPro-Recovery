"""Small adapters to the existing editable Persian report infrastructure."""
from datetime import date
from core.projects.controls import digest
from core.reports.exporters import report_date,FA_UNITS
from core.reports.project_report import build_report

LABELS={'lookahead':'برنامه عملیاتی','resources':'اکیپ‌ها و تجهیزات','materials':'نیاز، موجودی و کسری مصالح','purchases':'درخواست خرید پیش‌نویس','daily':'گزارش روزانه کارگاه','obstacles':'موانع و توقفات','meetings':'صورت‌جلسات و اقدامات','correspondence':'مکاتبات و RFI','package':'بسته اسناد دفتر فنی','dashboard':'خلاصه مدیریتی پروژه'}
WORDS={'project_id':'پروژه','id':'شناسه','quantity':'مقدار','unit':'واحد','status':'وضعیت','source':'منبع','sha256':'SHA-256','date':'تاریخ','start':'شروع','end':'پایان','finish':'پایان فعالیت','title':'عنوان','activity_id':'فعالیت','floor_ids':'طبقات','zone_ids':'زون‌ها','responsible':'مسئول','resources':'منابع','shortage':'کسری','on_hand':'موجودی مستند','free_stock':'موجودی آزاد','reserved':'رزرو','consumed':'مصرف','material_code':'کد مصالح','specification':'مشخصات','basis_digest':'هش مبنا','actual':'پیشرفت واقعی','planned':'پیشرفت مبنا','planned_current':'پیشرفت برنامه جاری','variance':'انحراف از مبنا','variance_current':'انحراف از برنامه جاری','source_ids':'شناسه منابع','price':'نرخ مستند','currency':'واحد پول','supplier':'تأمین‌کننده','reason':'دلیل','reasons':'دلایل محدودیت','created_by':'تهیه‌کننده','reviewed_by':'بازبین','approved_by':'تأییدکننده','reference':'شماره سند','version':'نسخه','template_version':'نسخه قالب','ready':'قابل اجرا','dependent':'وابسته به پیش‌نیاز','insufficient_information':'اطلاعات ناکافی','resource_conflict':'تداخل منابع','human_decision':'نیازمند تصمیم انسانی','draft':'پیش‌نویس','reviewed':'بازبینی‌شده','approved':'تأییدشده','issued':'صادرشده'}

WORDS.update(as_of='تاریخ مبنا',revision='بازنگری',missing_message='کفایت اطلاعات',progress='پیشرفت',schedule='برنامه',lookahead='برنامه کوتاه‌مدت',materials='مصالح',office='دفتر کارگاه',finance='مالی',requirements='نیازها',rules='قواعد مصرف',purchase_drafts='درخواست‌های خرید',daily_reports='گزارش‌های روزانه',meetings='صورت‌جلسات',obstacles='موانع',correspondence='مکاتبات',packages='بسته اسناد',overdue_actions='اقدامات معوق',overdue_obstacles='موانع معوق',resources='منابع',source_collections='ریزاسناد پشتیبان',resource_assignments='تخصیص‌ها',resource_events='توقف منابع',project_materials='اسناد انبار',material_requirements='نیاز مصالح',financial_records='اسناد مالی',statement_periods='دوره‌های صورت‌وضعیت',groups='گروه‌ها',activities='فعالیت‌ها',floors='طبقات',zones='زون‌ها',disciplines='رشته‌ها',available_capacity='ظرفیت در دسترس',capacity='ظرفیت',assignments='تخصیص‌ها',errors='خطاهای داده',duration='مدت کاری',critical_ids='فعالیت‌های بحرانی',budget='بودجه',commitments='تعهدات',actual_cost='هزینه واقعی',paid='پرداخت واقعی',debt='بدهی',unpaid_commitments='مانده تعهدات',budget_variance='انحراف بودجه',estimate='برآورد',statement_net='خالص صورت‌وضعیت',source_digest='هش منابع',waiting_phase7='در انتظار قابلیت مربوط',not_sent='ارسال خارجی انجام نشده',current='مبنای جاری معتبر',basis_stale='مبنای قدیمی',source_error='خطای منبع',name='نام',kind='نوع',crew='اکیپ',equipment='تجهیزات',reference_id='سند مبنا',supersedes='اصلاح‌کننده سند',reference='مرجع',version='نسخه',reason='دلیل',reason_source='مدرک دلیل',title='عنوان',work_dates='روزهای کاری',requirement_id='شناسه نیاز',source_ids='شناسه منابع')

def stamp(raw):
    if raw is None:return 'نامشخص'
    try:return report_date(date.fromisoformat(raw))
    except (ValueError,TypeError):return str(raw)

WORDS.update(IRR='ریال',IRT='تومان',awaiting_response='در انتظار پاسخ',responded='پاسخ مستند ثبت‌شده',not_issued='صادر نشده',response_status='وضعیت پاسخ',response_event='سند پاسخ',overdue_correspondence='مکاتبات معوق',daily='گزارش روزانه',meeting='صورت‌جلسه',obstacle='مانع',statement='صورت‌وضعیت',amendment='اصلاحیه',stopped='متوقف',released='رفع توقف',absent='عدم حضور',present='حاضر',unknown='نامشخص',cancelled='لغوشده')
WORDS.update(open='باز',resolved='رفع‌شده',opening='افتتاحیه',receipt='رسید',consume='مصرف',reserve='رزرو',correct='اصلاح',machine='دستگاه',applied='اعمال‌شده')
WORDS.update({'return':'برگشت','True':'بله','False':'خیر'})

def compact_rows(kind,data,p):
    """Engineering summaries plus explicit source references, never a payload dump."""
    rows=[]
    def val(x):return 'نامشخص' if x is None else WORDS.get(str(x),str(x))
    def amount(q,u=''):return val(q)+' '+FA_UNITS.get(u,WORDS.get(u,u))
    def add(section,id,description,values,source):
        rows.append({'بخش':section,'شناسه سند':str(id),'شرح و محل':description,'مقدار و وضعیت':values,'مرجع و نسخه':source})
    def proof(r):
        source=r.get('source') or {}
        return ' | '.join(str(x) for x in (r.get('reference'),source.get('reference'),r.get('version'),source.get('sha256') or r.get('content_digest') or r.get('sha256')) if x is not None)
    def record(key,r):
        id=r.get('id',r.get('number','نامشخص'));title=r.get('title') or r.get('summary') or r.get('description') or key
        status=val(r.get('status'));when=stamp(r.get('date'));location=r.get('location') or ', '.join(r.get('floor_ids',[]))
        values='تاریخ: '+when+' | وضعیت: '+status
        if key=='daily':
            values+=' | مقدار: '+amount(r.get('quantity'),r.get('unit',''))+' | نیروی ثبت‌شده: '+val(r.get('human_count'))
            title+=' | محل: '+location+' | فعالیت: '+str(r.get('activity_id'))+' | اکیپ: '+', '.join(r.get('crew_ids',[]))+' | '+r.get('technical_notes','')
        elif key=='meeting':
            title+=' | حاضران: '+r.get('participants','')+' | تصمیم: '+r.get('decisions','')
        elif key=='correspondence':
            title+=' | مخاطب: '+r.get('recipient','')+' | فعالیت: '+val(r.get('activity_id'))+' | '+r.get('technical_notes','')
            values+=' | ارسال: '+val(r.get('delivery_status'))+' | پیگیری: '+stamp(r.get('due_date'))+' | پاسخ: '+val(r.get('response_status'))
        elif key=='obstacle':
            title+=' | محل: '+location+' | مسئول: '+str(r.get('owner'))+' | فعالیت: '+str(r.get('activity_id'));values+=' | موعد: '+stamp(r.get('due_date'))
        elif key=='statement':
            title='صورت‌وضعیت دوره '+str(r['number'])+' | قرارداد: '+str(r.get('contract_id'))
            values=' | '.join(label+': '+amount(r.get(field),r.get('currency','')) for field,label in [('gross_current','ناخالص'),('retention','سپرده'),('advance_recovery','استهلاک پیش‌پرداخت'),('tax','مالیات'),('insurance','بیمه'),('other_deductions','سایر کسورات'),('payable_current','خالص')])
        elif key=='progress':
            title='گزارش پیشرفت مصوب';values=' | '.join(label+': '+val(r.get(field))+'٪' for field,label in [('actual','واقعی'),('planned','مبنا'),('planned_current','جاری'),('variance','انحراف از مبنا')])
        elif key=='amendment':
            title='اصلاحیه متره | '+r.get('reason','');values='نسخه مبنا: '+val(r.get('base_revision'))+' | وضعیت: '+status+' | دلتاهای ثبت‌شده: '+str(r.get('delta',{}))
        add(WORDS.get(key,key),id,title,values,proof(r) or digest(r))
        if r.get('supersedes'):add('اصلاحیه',id,'نسخه قبلی',str(r['supersedes']),proof(r))
        for attachment in r.get('attachments',[]):add('پیوست',id,attachment['reference'],'فایل موجود با هش ثبت‌شده',attachment['sha256'])
        for a in r.get('action_items',[]):add('پیگیری',a['id'],a['title']+' | مسئول: '+a['owner'],'موعد: '+stamp(a['due_date'])+' | وضعیت: '+val(a['status']),a['activity_id']+' | '+a['source']['sha256'])
        if key=='statement':
            for line in r['lines']:add('ریز صورت‌وضعیت',line.get('line_id',line.get('code','')),str(line.get('code',line.get('price_code',''))),'کارکرد دوره: '+val(line.get('current_quantity'))+' | نرخ: '+val(line.get('unit_price')),', '.join(line.get('source_ids',[])))
        if key=='progress':
            for a in r.get('activities',[]):add('پیشرفت فعالیت',a['id'],a['title'],'مصوب: '+amount(a.get('total'),a.get('unit',''))+' | اجراشده: '+amount(a.get('executed'),a.get('unit',''))+' | واقعی: '+val(a.get('actual'))+'٪',val(a.get('source_document')))
    if kind=='lookahead':
        for a in data['activities']:
            add('برنامه کوتاه‌مدت',a['id'],a['title']+' | مسئول: '+val(a['responsible'])+' | طبقات: '+', '.join(a['floor_ids']),stamp(a['start'])+' تا '+stamp(a['finish'])+' | '+val(a['status'])+' | '+'؛ '.join(a['reasons']),'نیاز منابع: '+val(a['requirement_id'])+' | '+val(data['schedule_digest']))
    elif kind=='resources':
        for r in p.get('project_resources',[]):add('اکیپ و تجهیزات',r['id'],r['name']+' | '+val(r.get('kind')),amount(r.get('capacity'),r.get('unit',''))+' | '+val(r.get('status')),proof(r))
        for r in p.get('resource_assignments',[]):add('تخصیص',r['id'],r['resource_id']+' ← '+r['activity_id']+' | طبقات: '+', '.join(r['floor_ids']),stamp(r['start'])+' تا '+stamp(r['end'])+' | ظرفیت: '+r['allocation']+' | '+val(r['status']),proof(r))
        for r in p.get('resource_events',[]):add('توقف منبع',r['id'],r['resource_id']+' | '+val(r['state']),stamp(r['start'])+' تا '+stamp(r['end']),proof(r))
    elif kind=='materials':
        for r in data['requirements']:
            text=' | '.join(label+': '+amount(r.get(k),r['unit']) for k,label in [('quantity','نیاز'),('on_hand','موجودی مستند'),('consumed','مصرف خالص'),('reserved','رزرو'),('shortage','کسری')])
            add('نیاز و کسری',r['id'],r['specification']+' | '+r['material_code']+' | طبقات: '+', '.join(r['floor_ids']),text,r['rule_id']+' | '+', '.join(r['source_ids'])+' | '+r['basis_digest'])
        for r in p.get('project_materials',[]):
            if r.get('schema')=='site_material_v1':add('گردش انبار',r['id'],r['material_code']+' | '+val(r['kind']),stamp(r['date'])+' | '+amount(r['quantity'],r['unit'])+' | سند مبنا: '+val(r.get('reference_id')),proof(r))
    elif kind=='purchases':
        for r in data:add('پیش‌نویس خرید',r['id'],r['specification']+' | مسئول: '+r['owner']+' | طبقات: '+', '.join(r['floor_ids']),amount(r['quantity'],r['unit'])+' | نرخ: '+amount(r['price'],r.get('currency') or '')+' | '+val(r['status'])+' | بدون اثر مالی خودکار',r['requirement_id']+' | '+r['stock_digest'])
    elif kind=='package':
        for pkg in data:
            add('بسته دفتر فنی',pkg['id'],pkg['title'],stamp(pkg['date'])+' | '+val(pkg['status'])+' | مبنای جاری: '+val(pkg.get('current'))+' | '+val(pkg.get('source_error')),pkg['reference']+' | قالب: '+pkg['template']+'/'+pkg['template_version'])
            add('پیوست آینده',pkg['id'],'نقشه خودکار فاز هفتم','در انتظار قابلیت مربوط',proof(pkg))
            for d in pkg['documents']:
                key={'project_daily_reports':'daily','project_meetings':'meeting','site_correspondence':'correspondence','statement_periods':'statement','progress_reports':'progress','beam_amendments':'amendment','manual_formula_amendments':'amendment','progress_documents':'daily'}[d['collection']]
                record(key,d['record']);add('منشأ سند',d['id'],'نسخه: '+str(d['version']),d['collection'],d['sha256'])
    elif kind=='dashboard':
        for key,label in [('actual','پیشرفت واقعی'),('planned','پیشرفت مبنا'),('planned_current','پیشرفت جاری'),('variance','انحراف از مبنا')]:add('پیشرفت','کل پروژه',label,val((data.get('progress') or {}).get(key))+'٪',data['source_digest'])
        for key in ['estimate','budget','commitments','actual_cost','paid','debt','unpaid_commitments','budget_variance','statement_net']:add('مالی','کل پروژه',WORDS[key],amount((data.get('finance') or {}).get(key),(data.get('finance') or {}).get('currency','')),data['source_digest'])
        for a in (data.get('lookahead') or {}).get('activities',[]):add('برنامه کوتاه‌مدت',a['id'],a['title'],val(a['status'])+' | '+'؛ '.join(a['reasons']),val(a['requirement_id']))
        for group,r in (data.get('progress') or {}).get('groups',{}).get('floors',{}).items():add('طبقه',group,'پیشرفت واقعی و برنامه‌ای',val(r.get('actual'))+'٪ | '+val(r.get('planned'))+'٪',data['source_digest'])
        for r in data['office']['overdue_actions']:add('اقدام معوق',r['id'],r['title']+' | '+r['owner'],stamp(r['due_date']),r['activity_id'])
        for r in (data.get('materials') or {}).get('requirements',[]):add('مصالح',r['id'],r['specification'],'نیاز: '+amount(r['quantity'],r['unit'])+' | کسری: '+amount(r['shortage'],r['unit']),r['basis_digest'])
    else:
        key={'daily':'daily','obstacles':'obstacle','meetings':'meeting','correspondence':'correspondence'}[kind]
        for r in data:record(key,r)
    if not rows:add(LABELS[kind],p['id'],'اطلاعات کافی ثبت نشده است','نامشخص','پروژه جاری')
    return rows

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
    rows=compact_rows(kind,data,p)
    metadata={'project_id':pid,'عنوان بخش':LABELS[kind],'تاریخ شمسی':report_date(date.fromisoformat(as_of)),'نسخه پروژه':p['_meta']['version'],'نسخه قالب':'site-operations-1','SHA-256 داده گزارش':digest(data),'محدودیت هویت':'اظهار مستند محلی؛ بدون امضای احراز‌شده'}
    return build_report(p['name']+' — '+LABELS[kind],rows,metadata=metadata).export(path,fmt)
