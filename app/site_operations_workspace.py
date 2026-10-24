"""Persian project-bound site forms over the guarded application commands."""
from datetime import date
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QCheckBox,QPushButton,QLabel,QTabWidget,QScrollArea,QTableWidget,QTableWidgetItem,QFileDialog,QPlainTextEdit)
from app.project_controls_workspace import JalaliField,iso
from core.reports.exporters import report_date

NAMES={'policy':'ثبت نسخه مجوزهای مالک','resource_create':'تعریف اکیپ یا تجهیزات','resource_review':'بازبینی منبع','resource_approve':'تأیید منبع','availability':'ثبت حضور و دسترسی','resource_event':'ثبت توقف یا رفع توقف','assign':'ایجاد تخصیص','assignment_review':'بازبینی تخصیص','assignment_approve':'تأیید تخصیص','assignment_cancel':'لغو مستند تخصیص','requirements':'نیاز منابع فعالیت','material_rule_create':'تعریف قاعده مصرف مصالح','material_rule_review':'بازبینی قاعده مصرف','material_rule_approve':'تأیید قاعده مصرف','material_need':'نیاز مصالح از BOQ','inventory_opening':'موجودی افتتاحیه','inventory_receipt':'تحویل واقعی','inventory_consume':'مصرف واقعی','inventory_reserve':'رزرو مصالح','inventory_return':'مرجوعی مصالح','inventory_correct':'برگشت سند انبار','inventory_close':'تأیید کامل بودن اسناد انبار','purchase_draft':'پیش‌نویس درخواست خرید','purchase_review':'بازبینی درخواست خرید','purchase_approve':'تأیید درخواست خرید','daily_create':'ایجاد گزارش روزانه','daily_review':'بازبینی گزارش روزانه','daily_approve':'تأیید گزارش روزانه','daily_issue':'صدور گزارش روزانه','daily_amend':'اصلاحیه گزارش روزانه','daily_transfer':'انتقال به پیش‌نویس پیشرفت','obstacle_create':'ثبت مانع','obstacle_resolve':'رفع مستند مانع','meeting_create':'ثبت صورت‌جلسه','meeting_review':'بازبینی صورت‌جلسه','meeting_approve':'تأیید صورت‌جلسه','meeting_issue':'صدور صورت‌جلسه','meeting_amend':'اصلاحیه صورت‌جلسه','action_resolve':'ثبت اقدام انجام‌شده','correspondence_create':'ثبت مکاتبه یا RFI','correspondence_review':'بازبینی مکاتبه','correspondence_approve':'تأیید مکاتبه','correspondence_issue':'صدور داخلی مکاتبه','correspondence_amend':'اصلاحیه مکاتبه','package_create':'تشکیل بسته اسناد W4','package_review':'بازبینی بسته اسناد','package_approve':'تأیید بسته اسناد','package_issue':'صدور بسته اسناد'}
LABELS={'id':'شناسه سند / نسخه قبلی اصلاحیه','name':'نام','kind':'نوع','capacity':'ظرفیت صریح','unit':'واحد','discipline_id':'شناسه رشته','subcontractor':'پیمانکار جزء / مسئول تجهیز','resource_id':'شناسه منبع','start':'تاریخ شروع','end':'تاریخ پایان','state':'وضعیت','activity_id':'شناسه فعالیت','allocation':'ظرفیت تخصیص','resources':'منابع؛ هر سطر شناسه:مقدار','materials':'شناسه نیاز مصالح؛ با ویرگول','material_code':'کد مصالح','specification':'مشخصات فنی','base_unit':'واحد BOQ','material_unit':'واحد مصالح','ratio':'ضریب مصرف مستند','waste_percent':'درصد پرت مصوب؛ صفر نیز صریح','source_version':'نسخه منبع','rule_id':'شناسه قاعده مصرف','source_ids':'تمام منابع ردیف BOQ؛ با ویرگول','item_code':'کد عملیات BOQ','floor_ids':'شناسه طبقات؛ با ویرگول','zone_ids':'شناسه زون‌ها؛ با ویرگول','period_start':'شروع دوره','period_end':'پایان دوره','approved_by':'تأییدکننده مستقل مقدار BOQ','quantity':'مقدار صریح','date':'تاریخ','reference_id':'شناسه سند مبنا','direction':'جهت مرجوعی','requirement_id':'شناسه نیاز مصالح','owner':'مسئول / مالک','supplier':'تأمین‌کننده انتخاب‌شده؛ اختیاری','price':'نرخ مستند؛ اختیاری','currency':'واحد پول؛ IRR / IRT صریح','summary':'خلاصه عملیات','location':'محل عملیات','crew_ids':'شناسه اکیپ‌ها؛ با ویرگول','equipment_ids':'شناسه تجهیزات؛ با ویرگول','material_ids':'شناسه اسناد انبار؛ با ویرگول','human_count':'تعداد نیروی ثبت‌شده','technical_notes':'توضیحات فنی','attachments':'پیوست؛ هر سطر مسیر|SHA-256|مرجع','cumulative_quantity':'مقدار تجمعی صریح','title':'عنوان','participants':'شرکت‌کنندگان؛ با ویرگول','decisions':'تصمیمات','actions':'اقدامات؛ هر سطر عنوان|مسئول|موعد|فعالیت','recipient':'گیرنده / مسئول پاسخ','template':'شناسه قالب','template_version':'نسخه قالب','sources':'منابع بسته؛ هر سطر مجموعه|شناسه|SHA-256|نسخه','due_date':'موعد','resolution':'اقدام اصلاحی','action_id':'شناسه اقدام','confirmed':'تأیید صریح داده و مدرک','establish_owner':'ثبت اولیه مالک مستند'}
DATES={'start','end','date','period_start','period_end','due_date'}
LISTS={'materials','source_ids','floor_ids','zone_ids','crew_ids','equipment_ids','material_ids','participants'}
LABELS.update(previous_cumulative_quantity='مقدار تجمعی مشاهده پیشین',previous_progress_id='شناسه مشاهده پیشین تأییدشده',initial_observation='نخستین مشاهده با مبنای صریح صفر',supersedes='شناسه مشاهده اصلاح‌شونده')

def schema(op):
    if op=='policy':return ['owner','establish_owner']+['permission_'+k for k in ['create','review','approve','issue','adjust','finance']]
    if op=='resource_create':return ['id','name','kind','capacity','unit','discipline_id','subcontractor']
    if op=='availability':return ['id','resource_id','start','end','state','capacity','confirmed','supersedes']
    if op=='resource_event':return ['id','resource_id','start','end','state','reference_id']
    if op=='assign':return ['id','activity_id','resource_id','start','end','allocation']
    if op=='requirements':return ['id','activity_id','resources','materials']
    if op=='material_rule_create':return ['id','material_code','specification','base_unit','material_unit','ratio','waste_percent','source_version']
    if op=='material_need':return ['id','rule_id','source_ids','item_code','activity_id','floor_ids','zone_ids','period_start','period_end','approved_by','source_version']
    if op=='inventory_close':return ['id','material_code','unit','period_start','period_end','confirmed']
    if op.startswith('inventory_'):return ['id','material_code','unit','quantity','date','requirement_id','reference_id','direction','confirmed']
    if op=='purchase_draft':return ['id','requirement_id','owner','supplier','price','currency']
    if op.startswith('daily_') and op.endswith(('create','amend')):return ['id','activity_id','date','summary','location','crew_ids','equipment_ids','material_ids','human_count','quantity','unit','technical_notes','attachments']
    if op=='daily_transfer':return ['id','cumulative_quantity','previous_cumulative_quantity','previous_progress_id','initial_observation','supersedes']
    if op=='purchase_commit':return ['id','date','confirmed']
    if op=='obstacle_create':return ['id','activity_id','date','title','owner','location','due_date','attachments']
    if op=='obstacle_resolve':return ['id','date','resolution']
    if op.startswith('meeting_') and op.endswith(('create','amend')):return ['id','date','title','participants','decisions','actions','attachments']
    if op=='action_resolve':return ['id','date','resolution']
    if op.startswith('correspondence_') and op.endswith(('create','amend')):return ['id','activity_id','kind','date','title','recipient','technical_notes','due_date','attachments']
    if op=='package_create':return ['id','date','title','template','template_version','sources']
    return ['id']

class SiteOperationsWorkspace(QDialog):
    def __init__(self,service,pid,parent=None):
        super().__init__(parent);self.service=service;self.pid=pid;self.fields={};self.operation_fields={};self.version=0
        self.setAttribute(Qt.WA_DeleteOnClose);self.setLayoutDirection(Qt.RightToLeft);self.setWindowTitle('عملیات کارگاه، منابع و اسناد');self.resize(1250,880)
        from app.theme import APP_STYLESHEET
        if parent is None:self.setStyleSheet(APP_STYLESHEET)
        outer=QVBoxLayout(self);outer.addWidget(QLabel('اظهار مسئولان محلی است؛ احراز هویت یا امضای رسمی نیست. پیش‌نویس خرید اثر مالی ندارد. صدور مکاتبه به معنی ارسال خارجی نیست.'))
        form=QFormLayout()
        for key,label in [('actor','مسئول عملیات'),('reason','دلیل مستند'),('proof','مسیر مدرک'),('sha','SHA-256 مدرک'),('reference','شماره یا مرجع سند'),('as_of','تاریخ مبنای نمایش')]:
            f=JalaliField() if key=='as_of' else QLineEdit();self.fields[key]=f;f.setObjectName('site_'+key);form.addRow(label,f)
        self.fields['as_of'].setText(report_date());outer.addLayout(form)
        self.tabs=QTabWidget();outer.addWidget(self.tabs,1)
        editor=QWidget();v=QVBoxLayout(editor);self.operation=QComboBox();self.operation.setObjectName('SiteOperation')
        for key,label in NAMES.items():self.operation.addItem(label,key)
        v.addWidget(self.operation);self.form_widget=QWidget();self.form=QFormLayout(self.form_widget);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(self.form_widget);v.addWidget(scroll,1)
        self.button(v,'ثبت عملیات در پروژه','SiteOperationSave',self.save)
        self.tabs.addTab(editor,'ثبت و گردش تأیید')
        sources=QWidget();sv=QVBoxLayout(sources);sv.addWidget(QLabel('فقط منابع معتبر همین پروژه؛ دوبارکلیک یک ردیف آن را به فرم بسته W4 اضافه می‌کند.'))
        self.button(sv,'بازخوانی منابع معتبر بسته','SiteSourcesRefresh',self.show_sources)
        self.sources_table=QTableWidget(0,4);self.sources_table.setHorizontalHeaderLabels(['مجموعه منبع','شناسه','SHA-256','نسخه']);self.sources_table.setEditTriggers(QTableWidget.NoEditTriggers);self.sources_table.cellDoubleClicked.connect(self.add_source);sv.addWidget(self.sources_table);self.tabs.addTab(sources,'منابع معتبر بسته W4')
        view=QWidget();dv=QVBoxLayout(view);self.horizon=QComboBox();self.horizon.addItem('هفت روز',7);self.horizon.addItem('چهارده روز',14);self.horizon.addItem('بازه سفارشی',None);dv.addWidget(self.horizon)
        self.custom_end=JalaliField();self.custom_end.setPlaceholderText('پایان بازه سفارشی؛ تاریخ شمسی');dv.addWidget(self.custom_end)
        self.button(dv,'بازخوانی داشبورد و ریزمنابع','SiteDashboardRefresh',self.show_dashboard)
        self.search=QLineEdit();self.search.setPlaceholderText('جست‌وجو در شاخص و سند');dv.addWidget(self.search)
        self.dashboard=QTableWidget(0,2);self.dashboard.setHorizontalHeaderLabels(['شاخص / شناسه منبع','مقدار و وضعیت']);self.dashboard.setEditTriggers(QTableWidget.NoEditTriggers);dv.addWidget(self.dashboard,1);self.search.textChanged.connect(self.filter)
        self.tabs.addTab(view,'داشبورد عملیاتی و ریزاسناد')
        report=QWidget();rv=QVBoxLayout(report);self.report_kind=QComboBox()
        from core.reports.site_operations import LABELS as REPORTS
        for key,label in REPORTS.items():self.report_kind.addItem(label,key)
        self.report_format=QComboBox();self.report_format.addItems(['pdf','xlsx','docx','csv']);rv.addWidget(self.report_kind);rv.addWidget(self.report_format);self.button(rv,'تولید خروجی قابل بازخوانی','SiteReportExport',self.export);rv.addStretch();self.tabs.addTab(report,'گزارش‌های فارسی')
        self.status=QLabel();self.status.setWordWrap(True);outer.addWidget(self.status)
        self.operation.addItem('تبدیل مجاز به پیش‌نویس تعهد مالی','purchase_commit');self.operation.addItem('لغو مستند درخواست خرید','purchase_cancel')
        self.operation.currentIndexChanged.connect(self.build_form);self.build_form();self.refresh()
    def button(self,layout,title,name,fn):
        b=QPushButton(title);b.setObjectName(name);b.clicked.connect(lambda:self.run(fn));layout.addWidget(b)
    def refresh(self):self.version=self.service.open_project(self.pid)['_meta']['version']
    def run(self,fn):
        try:message=fn();self.refresh();self.status.setText(message or 'عملیات ثبت و بازخوانی شد')
        except Exception as exc:self.status.setText('خطا: '+str(exc))
    def choose(self,op):self.operation.setCurrentIndex(self.operation.findData(op))
    def build_form(self):
        while self.form.rowCount():self.form.removeRow(0)
        self.operation_fields={};op=self.operation.currentData()
        for key in schema(op):
            if key in {'confirmed','establish_owner','initial_observation'}:f=QCheckBox('داده و مدرک را صریحاً تأیید می‌کنم')
            elif key in {'resources','actions','sources','attachments'}:f=QPlainTextEdit();f.setMaximumHeight(95)
            elif key=='kind':
                f=QComboBox()
                choices=[('اکیپ','crew'),('تجهیزات','equipment')] if op=='resource_create' else [('درخواست اطلاعات','rfi'),('تأیید مصالح','material_approval'),('بررسی نقشه','drawing_review'),('دستور کار','instruction'),('نامه','letter')]
                for label,value in choices:f.addItem(label,value)
            elif key=='state':
                f=QComboBox()
                for label,value in ([('حاضر / در دسترس','present'),('غایب','absent'),('نامشخص','unknown')] if op=='availability' else [('توقف','stopped'),('عدم حضور','absent'),('رفع توقف','released')]):f.addItem(label,value)
            elif key=='direction':
                f=QComboBox();f.addItem('برگشت به انبار','stock_in');f.addItem('مرجوع به تأمین‌کننده','stock_out')
            else:f=JalaliField() if key in DATES else QLineEdit()
            f.setObjectName('site_op_'+key);self.operation_fields[key]=f;self.form.addRow(LABELS.get(key,('مسئولان مجاز '+key[11:]+'؛ با ویرگول') if key.startswith('permission_') else key),f)
    def value(self,key):
        f=self.operation_fields[key]
        if isinstance(f,QCheckBox):return f.isChecked()
        if isinstance(f,QComboBox):return f.currentData()
        return f.toPlainText().strip() if isinstance(f,QPlainTextEdit) else f.text().strip()
    def source(self):return {'path':self.fields['proof'].text().strip(),'sha256':self.fields['sha'].text().strip(),'reference':self.fields['reference'].text().strip()}
    def save(self):
        from core.projects.controls import boq_basis,digest
        op=self.operation.currentData();data={};proof=self.source()
        for key in self.operation_fields:
            value=self.value(key)
            if key in DATES:value=iso(value) if value else None
            elif key in LISTS:value=[x.strip() for x in value.split(',') if x.strip()]
            elif key=='resources':value=[{'resource_id':x.split(':')[0].strip(),'quantity':x.split(':')[1].strip()} for x in value.splitlines() if x.strip()]
            elif key=='attachments':value=[dict(zip(('path','sha256','reference'),x.split('|'))) for x in value.splitlines() if x.strip()]
            elif key=='actions':value=[dict(zip(('title','owner','due_date','activity_id'),x.split('|')),source=proof) for x in value.splitlines() if x.strip()];value=[{**x,'due_date':iso(x['due_date'])} for x in value]
            elif key=='sources':value=[dict(zip(('collection','id','sha256','version'),x.split('|'))) for x in value.splitlines() if x.strip()];value=[{**x,'version':int(x['version'])} for x in value]
            if value=='':value=None
            data[key]=value
        data.update(source=proof,reference=self.fields['reference'].text().strip())
        if op=='policy':data['permissions']={key:[x.strip() for x in data.pop('permission_'+key).split(',') if x.strip()] for key in ['create','review','approve','issue','adjust','finance']}
        if op=='material_need':
            p=self.service.open_project(self.pid);rows=[x for x in p.get('boq',[]) if x.get('item_code')==data['item_code'] and set(x.get('source_ids') or [x.get('source_id')])==set(data['source_ids'])]
            if len(rows)!=1:raise ValueError('ردیف BOQ یکتا نیست')
            data['quantity_approval']={'approved_by':data.pop('approved_by'),'source_version':data.pop('source_version'),'basis_digest':boq_basis(p,rows[0]),'source':proof}
        if op=='purchase_draft':data.update(as_of=iso(self.fields['as_of'].text()),price_source=proof if data.get('price') is not None else None)
        if op=='daily_transfer':data['quantity_semantics']='cumulative'
        result=self.service.site_command(self.pid,op,actor=self.fields['actor'].text().strip(),reason=self.fields['reason'].text().strip(),expected_version=self.version,**data)
        return 'عملیات ثبت و بازخوانی شد؛ شناسه: '+str(result.get('id',result.get('version','')))
    def show_dashboard(self):
        from core.reports.site_operations import WORDS
        data=self.service.site_dashboard(self.pid,as_of=iso(self.fields['as_of'].text()),days=self.horizon.currentData(),end=iso(self.custom_end.text()) if self.horizon.currentData() is None else None);rows=[]
        def flatten(x,key):
            if isinstance(x,dict):
                for k,v in x.items():
                    if k=='snapshot_base64':continue
                    flatten(v,key+' / '+WORDS.get(k,k))
            elif isinstance(x,list):
                if not x:rows.append((key,'رکوردی ثبت نشده است'))
                for i,v in enumerate(x):flatten(v,key+' / '+str(v.get('id',i+1) if isinstance(v,dict) else i+1))
            else:rows.append((key,'نامشخص' if x is None else WORDS.get(str(x),str(x))))
        flatten(data,'پروژه '+self.pid);self.dashboard.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,v in enumerate(row):self.dashboard.setItem(i,j,QTableWidgetItem(v))
        self.dashboard.resizeColumnsToContents();return 'داشبورد از منابع پروژه بازخوانی شد'
    def filter(self,value):
        for i in range(self.dashboard.rowCount()):self.dashboard.setRowHidden(i,not any(value in self.dashboard.item(i,j).text() for j in range(2)))
    def show_sources(self):
        rows=self.service.site_package_candidates(self.pid);self.sources_table.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,key in enumerate(('collection','id','sha256','version')):self.sources_table.setItem(i,j,QTableWidgetItem(str(row[key])))
        self.sources_table.resizeColumnsToContents();return 'منابع معتبر بازخوانی شد'
    def add_source(self,row,column):
        values=[self.sources_table.item(row,j).text() for j in range(4)]
        self.choose('package_create');self.operation_fields['sources'].appendPlainText('|'.join(values));self.tabs.setCurrentIndex(0)
    def export(self):
        fmt=self.report_format.currentText();path,_=QFileDialog.getSaveFileName(self,'ذخیره گزارش','site-report.'+fmt,'*.'+fmt)
        if not path:return 'ذخیره لغو شد'
        self.service.site_report(self.pid,self.report_kind.currentData(),fmt,path,as_of=iso(self.fields['as_of'].text()),days=self.horizon.currentData(),end=iso(self.custom_end.text()) if self.horizon.currentData() is None else None);return 'گزارش تولید شد: '+path
