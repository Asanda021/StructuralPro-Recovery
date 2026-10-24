"""Operational RTL project controls over the canonical guarded application API."""
from datetime import date
from decimal import Decimal
from PySide6.QtCore import Qt,QCalendar,QDate,Signal,QLocale
from PySide6.QtGui import QBrush,QColor,QPen,QPainterPath,QPainter
from PySide6.QtWidgets import (QDialog,QWidget,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QLabel,
 QComboBox,QTabWidget,QTreeWidget,QTreeWidgetItem,QTableWidget,QTableWidgetItem,QSplitter,QGraphicsView,
 QGraphicsScene,QGraphicsItem,QScrollArea,QFileDialog,QCalendarWidget,QDialogButtonBox)
from core.reports.exporters import report_date,FA_UNITS


def iso(raw):
    raw=raw.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).strip()
    y,m,d=map(int,raw.replace('-','/').split('/'))
    if y<1700:
        cal=QCalendar(QCalendar.Jalali)
        if not cal.isDateValid(y,m,d):raise ValueError('تاریخ شمسی معتبر نیست')
        return cal.dateFromParts(y,m,d).toString('yyyy-MM-dd')
    return date(y,m,d).isoformat()


class JalaliField(QLineEdit):
    def mouseDoubleClickEvent(self,event):
        dlg=QDialog(self);v=QVBoxLayout(dlg);c=QCalendarWidget();c.setCalendar(QCalendar(QCalendar.Jalali));c.setLocale(QLocale('fa_IR'))
        if self.text():
            try:c.setSelectedDate(QDate.fromString(iso(self.text()),'yyyy-MM-dd'))
            except ValueError:pass
        v.addWidget(c);buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);v.addWidget(buttons)
        buttons.accepted.connect(dlg.accept);buttons.rejected.connect(dlg.reject)
        if dlg.exec():self.setText(report_date(date.fromisoformat(c.selectedDate().toString('yyyy-MM-dd'))))
        super().mouseDoubleClickEvent(event)


class GanttView(QGraphicsView):
    activitySelected=Signal(str)
    def __init__(self,parent=None):
        super().__init__(parent);self.setScene(QGraphicsScene(self));self.bars={};self.scale_x=24;self.data=None;self.base=None;self.progress={}
        self.setRenderHint(QPainter.Antialiasing);self.scene().selectionChanged.connect(self.selection)
        self.setMinimumHeight(300);self.setObjectName('ProjectGantt')
    def selection(self):
        selected=self.scene().selectedItems()
        if selected and selected[0].data(0):self.activitySelected.emit(selected[0].data(0))
    def zoom(self,scale):self.scale_x=scale;self.render(self.data,self.base,self.progress)
    def render(self,data,base=None,progress=None):
        self.data=data;self.base=base;self.progress=progress or {};scene=self.scene();scene.clear();self.bars={}
        if not data:scene.addText('برنامه قابل محاسبه ثبت نشده است');return
        start=date.fromisoformat(data['start']);x0=210;rowh=34;coords={}
        def x(raw):return x0+(date.fromisoformat(raw)-start).days*self.scale_x
        end=max(x(r['finish_boundary']) for r in data['activities'].values())
        step=1 if self.scale_x>=20 else 14 if self.scale_x>=5 else 60
        days=(date.fromisoformat(data['finish_boundary'])-start).days
        for d in range(0,days+1,max(step,(days//150)+1)):
            from datetime import timedelta
            px=x0+d*self.scale_x;scene.addLine(px,28,px,45+len(data['order'])*rowh,QPen(QColor('#d9e3ee')))
            stamp=report_date(start+timedelta(days=d));caption=stamp[-2:] if self.scale_x>=20 else stamp[5:] if self.scale_x>=5 else stamp[:7]
            label=scene.addText(caption);label.setPos(px,24)
        title=scene.addText(report_date(start)+' تا '+report_date(date.fromisoformat(data['finish_boundary'])));title.setPos(5,0)
        for i,id in enumerate(data['order']):
            r=data['activities'][id];y=62+i*rowh;s=x(r['start']);e=x(r['finish_boundary']);coords[id]=(s,e,y)
            title=scene.addText(r.get('wbs_id','')+' / '+r.get('title',id));title.setPos(5,y-6)
            if base and id in base['activities']:
                b=base['activities'][id];scene.addRect(x(b['start']),y+20,max(3,x(b['finish_boundary'])-x(b['start'])),4,QPen(Qt.NoPen),QBrush(QColor('#8391a4')))
            color=QColor('#ce4c61' if r['critical'] else '#3687b8')
            if r['milestone']:
                path=QPainterPath();path.moveTo(s,y);path.lineTo(s+8,y+8);path.lineTo(s,y+16);path.lineTo(s-8,y+8);path.closeSubpath();bar=scene.addPath(path,QPen(color),QBrush(color))
            else:bar=scene.addRect(s,y,max(4,e-s),16,QPen(color),QBrush(color))
            bar.setData(0,id);bar.setFlag(QGraphicsItem.ItemIsSelectable);bar.setToolTip(id+'\n'+report_date(date.fromisoformat(r['start']))+' → '+report_date(date.fromisoformat(r['finish']))+'\nشناوری: '+str(r['total_float']))
            self.bars[id]=bar
            actual=(self.progress.get(id) or {}).get('actual')
            if actual is not None and not r['milestone']:scene.addRect(s,y+10,max(0,(e-s)*float(Decimal(actual)/100)),6,QPen(Qt.NoPen),QBrush(QColor('#31b79b')))
        for rel in data['relationships']:
            a,b=coords[rel['pred']],coords[rel['succ']];sx=a[1] if rel['type'][0]=='F' else a[0];ex=b[1] if rel['type'][1]=='F' else b[0]
            path=QPainterPath();path.moveTo(sx,a[2]+8);path.lineTo(sx+10,a[2]+8);path.lineTo(sx+10,b[2]+8);path.lineTo(ex,b[2]+8)
            scene.addPath(path,QPen(QColor('#7587a0')))
        scene.setSceneRect(0,0,max(700,end+100),100+len(data['order'])*rowh)


class SCurveView(QGraphicsView):
    def __init__(self,parent=None):super().__init__(parent);self.setScene(QGraphicsScene(self));self.setMinimumHeight(240)
    def render(self,points):
        s=self.scene();s.clear()
        if not points:s.addText('گزارش دوره‌ای تأییدشده ثبت نشده است');return
        s.addLine(50,20,50,220);s.addLine(50,220,650,220)
        for i,p in enumerate(points):
            x=70+(550*i/max(1,len(points)-1))
            for key,color in [('planned','#3687b8'),('planned_current','#d18a26'),('actual','#31a486')]:
                if p.get(key) is None:continue
                y=220-float(Decimal(p[key]))*1.8;item=s.addEllipse(x-4,y-4,8,8,QPen(QColor(color)),QBrush(QColor(color)))
                item.setToolTip(f"{p['report_id']} / {p['date']} / {p[key]} / {p['sha256']}")
                label=s.addText(p[key]);label.setPos(x+5,y-12);label.setDefaultTextColor(QColor(color))
            label=s.addText(report_date(date.fromisoformat(p['date'])));label.setPos(x-25,225)
        s.addText('آبی: مبنا | نارنجی: برنامه جاری | سبز: واقعی — فقط نقاط ثبت‌شده؛ بدون ساخت داده بین دوره‌ها').setPos(40,255);s.setSceneRect(0,0,750,290)


class ProjectControlsWorkspace(QDialog):
    def __init__(self,service,project_id,parent=None):
        super().__init__(parent);self.service=service;self.pid=project_id;self.fields={};self.selected_id=None;self.version=0
        self.setAttribute(Qt.WA_DeleteOnClose);self.setLayoutDirection(Qt.RightToLeft);self.setWindowTitle('مدیریت پروژه — WBS، زمان‌بندی و پیشرفت');self.resize(1300,900)
        if parent is None:
            from app.theme import APP_STYLESHEET
            self.setStyleSheet(APP_STYLESHEET)
        v=QVBoxLayout(self);v.addWidget(QLabel('شناسه‌های مسئولان اظهار محلی هستند؛ احراز هویت اشخاص نیست. مدت و وقفه: روز کاری؛ تاریخ گزارش: ابتدای روز. انتخاب تقویم شمسی با دوبارکلیک روی تاریخ.'))
        common=QFormLayout()
        for key,label in [('actor','مسئول عملیات'),('reason','دلیل تغییر'),('proof','مسیر مدرک'),('sha','SHA-256 مدرک'),('reference','مرجع سند')]:self.field(common,key,label)
        v.addLayout(common)
        self.tabs=QTabWidget();v.addWidget(self.tabs,1)
        self.structure_tab();self.schedule_tab();self.progress_tab();self.report_tab()
        self.status=QLabel();self.status.setWordWrap(True);v.addWidget(self.status);self.refresh()
    def field(self,form,key,label,date_field=False):
        f=JalaliField() if date_field else QLineEdit();f.setObjectName(key);self.fields[key]=f;form.addRow(label,f);return f
    def button(self,layout,title,name,fn):
        b=QPushButton(title);b.setObjectName(name);b.clicked.connect(lambda:self.run(fn));layout.addWidget(b);return b
    def table(self,labels):
        t=QTableWidget(0,len(labels));t.setHorizontalHeaderLabels(labels);t.setSelectionBehavior(QTableWidget.SelectRows);t.setEditTriggers(QTableWidget.NoEditTriggers);return t
    def tab(self,title):
        w=QWidget();v=QVBoxLayout(w);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(w);self.tabs.addTab(scroll,title);return v
    def text(self,key):return self.fields[key].text().strip()
    def source(self):return {'path':self.text('proof'),'sha256':self.text('sha'),'reference':self.text('reference')}
    def execute(self,op,**data):return self.service.project_control_command(self.pid,op,actor=self.text('actor'),reason=self.text('reason'),expected_version=self.version,**data)
    def run(self,fn):
        try:
            fn();self.refresh();self.status.setText('عملیات با موفقیت ثبت و بازخوانی شد')
        except Exception as e:self.status.setText('خطا: '+str(e))
    def structure_tab(self):
        v=self.tab('ساختار و WBS');form=QFormLayout();self.kind=QComboBox()
        for label,key in [('بلوک','building'),('طبقه','floor'),('زون','zone'),('رشته','discipline'),('WBS','wbs')]:self.kind.addItem(label,key)
        form.addRow('نوع ساختار',self.kind)
        for key,label in [('structure_id','شناسه پایدار'),('structure_title','عنوان'),('structure_parent','والد WBS / بلوک طبقه'),('structure_code','کد WBS'),('structure_floors','شناسه طبقات زون؛ با ویرگول'),('floor_level','تراز عددی طبقه'),('floor_height','ارتفاع صریح طبقه')]:self.field(form,key,label)
        self.floor_kind=QComboBox()
        for label,key in [('انتخاب نوع طبقه',None),('زیرزمین','basement'),('همکف','ground'),('مثبت','positive'),('بام','roof')]:self.floor_kind.addItem(label,key)
        form.addRow('نوع طبقه',self.floor_kind);v.addLayout(form);self.button(v,'ثبت / ویرایش ساختار','StructureSave',self.save_structure)
        split=QSplitter();self.tree=QTreeWidget();self.tree.setHeaderLabels(['ساختار شکست کار']);self.activity_table=self.table(['شناسه','عنوان','WBS','طبقات','واحد','مبنای مقدار'])
        split.addWidget(self.tree);split.addWidget(self.activity_table);v.addWidget(split,1)
        self.tree.itemClicked.connect(self.tree_selected);self.activity_table.itemSelectionChanged.connect(self.table_selected)
        search=QFormLayout();self.field(search,'search','جست‌وجوی فعالیت');v.addLayout(search);self.fields['search'].textChanged.connect(self.filter)
        scroll=QScrollArea();scroll.setWidgetResizable(True);editor=QWidget();af=QFormLayout(editor)
        for key,label in [('activity_id','شناسه فعالیت'),('activity_title','عنوان فعالیت'),('activity_code','کد یکتا'),('activity_parent','شناسه فعالیت والد؛ اختیاری'),('activity_wbs','شناسه WBS'),('activity_floors','طبقات؛ با ویرگول'),('activity_zones','زون‌ها؛ با ویرگول'),('activity_members','اعضا؛ با ویرگول'),('activity_discipline','شناسه رشته'),('activity_unit','واحد'),('activity_responsible','مسئول فعالیت'),('activity_total','مقدار مبنای صریح'),('activity_approver','تأییدکننده مبنا'),('activity_sources','تمام شناسه‌های منابع ردیف BOQ'),('activity_item_code','کد عملیات BOQ؛ برای تمایز کمیت‌ها')]:self.field(af,key,label)
        self.measurement_kind=QComboBox()
        for label,key in [('بدون مبنای مقدار','none'),('ردیف معتبر BOQ','boq'),('مقدار صریح مستند','explicit')]:self.measurement_kind.addItem(label,key)
        af.addRow('نوع مبنا',self.measurement_kind);self.activity_status=QComboBox()
        for label,key in [('آغاز نشده','todo'),('در حال اجرا','in_progress'),('متوقف','blocked'),('پایان‌یافته','done'),('لغوشده','cancelled')]:self.activity_status.addItem(label,key)
        af.addRow('وضعیت',self.activity_status);scroll.setWidget(editor);v.addWidget(scroll,1)
        bar=QHBoxLayout();self.button(bar,'ثبت / ویرایش فعالیت','ActivitySave',self.save_activity);self.button(bar,'جابه‌جایی در WBS','ActivityMove',lambda:self.execute('move_activity',id=self.text('activity_id'),wbs_id=self.text('activity_wbs')));v.addLayout(bar)
    def list(self,key):return [x.strip() for x in self.text(key).split(',') if x.strip()]
    def save_structure(self):
        op=self.kind.currentData();d={'id':self.text('structure_id'),'title':self.text('structure_title')}
        if op=='floor':d.update(building_id=self.text('structure_parent'),kind=self.floor_kind.currentData(),level=self.text('floor_level'),height=self.text('floor_height'))
        elif op=='wbs':d.update(parent_id=self.text('structure_parent') or None,code=self.text('structure_code'))
        elif op=='zone':d['floor_ids']=self.list('structure_floors')
        self.execute(op,**d)
    def save_activity(self):
        kind=self.measurement_kind.currentData();m={'kind':kind}
        if kind=='boq':m.update(source_ids=self.list('activity_sources'),item_code=self.text('activity_item_code') or None)
        elif kind=='explicit':m.update(total=self.text('activity_total'),source=self.source(),approved_by=self.text('activity_approver'))
        self.execute('activity',id=self.text('activity_id'),parent_activity_id=self.text('activity_parent') or None,title=self.text('activity_title'),code=self.text('activity_code'),wbs_id=self.text('activity_wbs'),
            floor_ids=self.list('activity_floors'),zone_ids=self.list('activity_zones'),member_ids=self.list('activity_members'),discipline_id=self.text('activity_discipline'),unit=self.text('activity_unit'),responsible=self.text('activity_responsible'),status=self.activity_status.currentData(),measurement=m)
    def schedule_tab(self):
        outer=self.tab('تقویم، زمان‌بندی و گانت');controls=QWidget();v=QVBoxLayout(controls);form=QFormLayout()
        self.field(form,'calendar_start','شروع پروژه — شمسی',True);self.field(form,'weekdays','روزهای کاری: دوشنبه=0 … یکشنبه=6');self.field(form,'holidays','تعطیلات شمسی؛ با ویرگول');v.addLayout(form)
        self.button(v,'ثبت تقویم صریح','ScheduleCalendarSave',lambda:self.execute('schedule_calendar',start=iso(self.text('calendar_start')),calendar={'weekdays':[int(x) for x in self.list('weekdays')],'holidays':[iso(x) for x in self.list('holidays')]}))
        form=QFormLayout();self.field(form,'duration','مدت فعالیت انتخاب‌شده؛ روز کاری');self.field(form,'not_before','زودتر از این تاریخ آغاز نشود؛ اختیاری',True)
        self.field(form,'relationships','روابط: شناسه:FS:وقفه, شناسه:SS:وقفه');v.addLayout(form)
        self.button(v,'ثبت مدت و روابط فعالیت','ScheduleActivitySave',self.save_schedule)
        form=QFormLayout();self.field(form,'baseline_reference','مرجع یکتای Baseline');self.field(form,'baseline_approver','تأییدکننده مبنا');v.addLayout(form)
        self.button(v,'تثبیت نسخه جدید مبنا','ScheduleBaselineSave',lambda:self.execute('schedule_baseline',reference=self.text('baseline_reference'),approved_by=self.text('baseline_approver')))
        chart=QWidget();chart_layout=QVBoxLayout(chart);bar=QHBoxLayout()
        self.gantt=GanttView();self.gantt.activitySelected.connect(self.select_activity)
        for title,name,scale in [('روز','Day',24),('هفته','Week',6),('ماه','Month',2)]:self.button(bar,title,'GanttZoom'+name,lambda scale=scale:self.gantt.zoom(scale))
        chart_layout.addLayout(bar);chart_layout.addWidget(self.gantt,1);self.schedule_info=QLabel();self.schedule_info.setWordWrap(True);chart_layout.addWidget(self.schedule_info)
        scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(controls);scroll.setMinimumWidth(320)
        split=QSplitter(Qt.Horizontal);split.addWidget(scroll);split.addWidget(chart);split.setSizes([340,900]);outer.addWidget(split,1)
    def save_schedule(self):
        if not self.selected_id:raise ValueError('ابتدا فعالیت را انتخاب کنید')
        rels=[]
        for raw in self.list('relationships'):
            pred,typ,lag=raw.split(':');rels.append({'pred':pred.strip(),'succ':self.selected_id,'type':typ.strip().upper(),'lag':lag.strip()})
        self.execute('schedule_activity',id=self.selected_id,duration=self.text('duration'),not_before=iso(self.text('not_before')) if self.text('not_before') else None,relationships=rels)
    def progress_tab(self):
        v=self.tab('کارکرد و پیشرفت وزنی');form=QFormLayout()
        self.field(form,'report_date','تاریخ شمسی گزارش',True);self.field(form,'executed','مقدار تجمعی مشاهده‌شده فعالیت انتخاب‌شده');self.field(form,'supersedes','شناسه سند قبلی برای اصلاحیه؛ اختیاری');self.field(form,'progress_id','شناسه سند کارکرد');self.field(form,'weight_id','شناسه نسخه وزن');self.field(form,'decimal_places','تعداد اعشار درصد؛ صریح')
        self.rounding=QComboBox();self.rounding.addItem('انتخاب سیاست درصد',None);self.rounding.addItem('نیم به زوج','ROUND_HALF_EVEN');self.rounding.addItem('نیم رو به بالا','ROUND_HALF_UP');form.addRow('گردکردن درصد',self.rounding)
        v.addLayout(form);self.weight_versions=QComboBox();self.weight_versions.setObjectName('WeightVersions');v.addWidget(self.weight_versions)
        self.weight_versions.currentIndexChanged.connect(self.load_weights)
        bar=QHBoxLayout()
        self.button(bar,'ثبت مشاهده / اصلاحیه','ProgressCreate',self.create_progress)
        for title,op in [('بازبینی','progress_review'),('تأیید مستقل','progress_approve')]:self.button(bar,title,'Progress'+op.split('_')[1].title(),lambda op=op:self.execute(op,id=self.text('progress_id')))
        v.addLayout(bar);self.observations=self.table(['سند','فعالیت','تاریخ','مقدار','وضعیت','اصلاح سند']);v.addWidget(self.observations)
        self.observations.itemSelectionChanged.connect(lambda:self.pick_doc(self.observations,'progress_id'))
        self.weight_table=QTableWidget(0,4);self.weight_table.setHorizontalHeaderLabels(['فعالیت','وزن خام','روش توزیع پیشرفت برنامه‌ای','سهم طبقات: F1:0.5,F2:0.5']);v.addWidget(self.weight_table)
        bar=QHBoxLayout();self.button(bar,'ثبت نسخه وزن مستند','WeightCreate',self.create_weights)
        for title,op in [('بازبینی وزن','weight_review'),('تأیید مستقل وزن','weight_approve')]:self.button(bar,title,'Weight'+op.split('_')[1].title(),lambda op=op:self.execute(op,id=self.text('weight_id')))
        self.button(bar,'ثبت گزارش دوره‌ای','ProgressReportSave',lambda:self.execute('progress_report',date=iso(self.text('report_date')),reference=self.text('reference')));v.addLayout(bar)
        self.progress_table=self.table(['فعالیت','کل','اجراشده','باقی‌مانده','واقعی٪','برنامه‌ای٪','انحراف']);v.addWidget(self.progress_table)
        self.curve_frequency=QComboBox();self.curve_frequency.setObjectName('CurveFrequency')
        for label,key in [('روزانه','daily'),('هفتگی','weekly'),('ماهانه','monthly')]:self.curve_frequency.addItem(label,key)
        v.addWidget(self.curve_frequency);self.curve_frequency.currentIndexChanged.connect(lambda:self.run(self.refresh))
        self.curve=SCurveView();v.addWidget(self.curve)
        self.button(v,'محاسبه در تاریخ انتخابی','ProgressCalculate',self.show_progress)
    def load_weights(self):
        id=self.weight_versions.currentData()
        d=next((x for x in self.project.get('progress_weight_sets',[]) if x['id']==id),None)
        if not d:return
        self.fields['weight_id'].setText(id)
        for i in range(self.weight_table.rowCount()):
            item=self.weight_table.item(i,0)
            if not item:continue
            key=item.text()
            choice=self.weight_table.cellWidget(i,2)
            if choice:choice.setCurrentIndex(choice.findData(d['distributions'].get(key)))
            for j,value in [(1,d['weights'].get(key,'')),(3,','.join(k+':'+str(v) for k,v in d.get('floor_shares',{}).get(key,{}).items()))]:self.weight_table.setItem(i,j,QTableWidgetItem(value))
        self.details.setText('نسخه وزن '+id+' | وضعیت '+{'draft':'پیش‌نویس','reviewed':'بازبینی‌شده','approved':'تأییدشده'}.get(d['status'],d['status'])+' | منبع: '+str(d['source'])+' | دلیل: '+d['reason'])

    def create_progress(self):
        d=self.execute('progress_create',activity_id=self.selected_id,cumulative_quantity=self.text('executed'),date=iso(self.text('report_date')),reference=self.text('reference'),source=self.source(),supersedes=self.text('supersedes') or None)
        self.fields['progress_id'].setText(d['id'])
    def create_weights(self):
        weights={};distributions={};shares={}
        for i in range(self.weight_table.rowCount()):
            values=[self.weight_table.item(i,j).text() if self.weight_table.item(i,j) else '' for j in range(4)];id=values[0];weights[id]=values[1];choice=self.weight_table.cellWidget(i,2);distributions[id]=choice.currentData() if choice else None
            if values[3]:shares[id]=dict(x.strip().split(':') for x in values[3].split(','))
        d=self.execute('weight_create',reference=self.text('reference'),source=self.source(),weights=weights,distributions=distributions,floor_shares=shares,method='manual_approved',decimal_places=self.text('decimal_places'),rounding=self.rounding.currentData());self.fields['weight_id'].setText(d['id'])
    def pick_doc(self,table,field):
        row=table.currentRow()
        if row>=0 and table.item(row,0):self.fields[field].setText(table.item(row,0).text())
    def report_tab(self):
        v=self.tab('گزارش و ریزمنابع');self.details=QLabel();self.details.setWordWrap(True);v.addWidget(self.details)
        self.location_choice=QComboBox();v.addWidget(self.location_choice);self.button(v,'نمایش و هایلایت موقعیت معتبر','ActivityHighlight',self.open_location)
        self.report_kind=QComboBox()
        for label,key in [('WBS','wbs'),('فعالیت‌ها','activities'),('زمان‌بندی و مسیر بحرانی','schedule'),('پیشرفت و انحراف','progress'),('منحنی S','curve')]:self.report_kind.addItem(label,key)
        v.addWidget(self.report_kind);self.report_format=QComboBox()
        for fmt in ['pdf','xlsx','docx','csv']:self.report_format.addItem(fmt.upper(),fmt)
        v.addWidget(self.report_format);self.button(v,'تولید گزارش فارسی','ProjectControlsExport',self.export)
        self.button(v,'بازخوانی پروژه','ProjectControlsRefresh',self.refresh)
    def open_location(self):
        key=self.location_choice.currentData()
        locations=self.service.activity_locations(self.pid,self.selected_id)
        target=next((x for x in locations if x['key']==key),None)
        if target is None:raise ValueError('موقعیت هندسی معتبر برای فعالیت انتخاب نشده است')
        from app.graphical_takeoff import GraphicalTakeoffDialog
        window=GraphicalTakeoffDialog(app_service=self.service,project_id=self.pid,parent=self)
        try:
            window.open_drawing(target['path'])
            if target['kind']=='drawing':
                from core.drawings.takeoff_session import DrawingTakeoffSession
                record=target['session'];restored=DrawingTakeoffSession.from_dict(record['session'])
                window.session=restored;window.canvas.session=restored;window.persisted_session_id=record['id'];window.persisted_session_revision=record['revision']
                window.load_page(restored.find(target['item_id']).page);window.refresh()
                for i in range(window.table.rowCount()):
                    if window.table.item(i,0).text()==target['item_id']:window.table.setCurrentCell(i,0)
                window.highlight_selected_measurement()
            else:window.highlight_ifc_member(target['global_id'])
            window.show();self.drawing_window=window
        except Exception:
            window.close();raise

    def export(self):
        fmt=self.report_format.currentData();path,_=QFileDialog.getSaveFileName(self,'ذخیره گزارش','',f'*.{fmt}')
        if path:self.service.project_controls_report(self.pid,self.report_kind.currentData(),fmt,path,as_of=iso(self.text('report_date')) if self.text('report_date') else None)
    def fill(self,t,rows):
        t.blockSignals(True);t.setRowCount(len(rows))
        for i,row in enumerate(rows):
            for j,value in enumerate(row):t.setItem(i,j,QTableWidgetItem(str(value) if value is not None else 'غیرقابل محاسبه'))
        t.resizeColumnsToContents();t.blockSignals(False)
    def refresh(self):
        p=self.service.open_project(self.pid);self.version=p['_meta']['version'];self.project=p
        self.tree.clear();nodes={}
        for b in p.get('buildings',[]):
            root=QTreeWidgetItem(self.tree,[b.get('title',b['id'])]);root.setData(0,Qt.UserRole,('building',b['id']))
            for f in p.get('floors',[]):
                if f.get('building_id')==b['id']:
                    item=QTreeWidgetItem(root,[f['name']]);item.setData(0,Qt.UserRole,('floor',f['id']))
        pending=list(p.get('project_wbs',[]))
        while pending:
            for r in list(pending):
                if r['parent_id'] is None or r['parent_id'] in nodes:
                    item=QTreeWidgetItem(nodes.get(r['parent_id'],self.tree),[r['code']+' '+r['title']]);item.setData(0,Qt.UserRole,('wbs',r['id']));nodes[r['id']]=item;pending.remove(r)
        self.tree.expandAll()
        activities=p.get('project_schedule_tasks',[]);self.fill(self.activity_table,[[a['id'],a['title'],a.get('wbs_id'),','.join(a.get('floor_ids',[])),FA_UNITS.get(a.get('unit'),a.get('unit')),a.get('measurement',{}).get('total','بدون مقدار')] for a in activities]);self.filter()
        if self.weight_table.rowCount()!=len(activities):
            self.weight_table.setRowCount(len(activities))
            for i,a in enumerate(activities):
                item=QTableWidgetItem(a['id']);item.setFlags(item.flags() & ~Qt.ItemIsEditable);self.weight_table.setItem(i,0,item)
                choice=QComboBox();choice.addItem('انتخاب روش صریح',None);choice.addItem('خطی برحسب روز کاری','linear_workdays');choice.addItem('نقطه عطف در پایان','milestone_finish');self.weight_table.setCellWidget(i,2,choice)
        self.weight_versions.blockSignals(True);self.weight_versions.clear();self.weight_versions.addItem('انتخاب نسخه وزن',None)
        for d in p.get('progress_weight_sets',[]):self.weight_versions.addItem(d['id']+' / '+{'draft':'پیش‌نویس','reviewed':'بازبینی‌شده','approved':'تأییدشده'}[d['status']],d['id'])
        self.weight_versions.setCurrentIndex(max(0,self.weight_versions.findData(self.text('weight_id'))));self.weight_versions.blockSignals(False);self.load_weights()
        self.fill(self.observations,[[d['id'],d['activity_id'],report_date(date.fromisoformat(d['date'])),d['quantity'],{'draft':'پیش‌نویس','reviewed':'بازبینی‌شده','approved':'تأییدشده'}[d['status']],d.get('supersedes')] for d in p.get('progress_documents',[])])
        try:
            schedule=self.service.project_schedule(self.pid);base=(p.get('schedule_baselines') or [None])[-1]
            self.gantt.render(schedule,base['result'] if base else None)
            self.schedule_info.setText('مسیر بحرانی: '+', '.join(schedule['critical_ids'])+' | مدت کاری: '+str(schedule['duration']))
        except ValueError as e:self.gantt.render(None);self.schedule_info.setText(str(e))
        self.curve.render(self.service.project_progress_curve(self.pid,frequency=self.curve_frequency.currentData()))
        if self.selected_id:self.select_activity(self.selected_id)
    def filter(self):
        value=self.text('search').casefold()
        for i in range(self.activity_table.rowCount()):self.activity_table.setRowHidden(i,value not in ' '.join(self.activity_table.item(i,j).text() for j in range(self.activity_table.columnCount())).casefold())
    def tree_selected(self,item):
        kind,id=item.data(0,Qt.UserRole)
        key={'building':'buildings','floor':'floors','wbs':'project_wbs'}.get(kind)
        record=next((x for x in self.project.get(key,[]) if x['id']==id),None) if key else None
        if record:
            self.kind.setCurrentIndex(self.kind.findData(kind))
            for field,value in [('structure_id',id),('structure_title',record.get('title',record.get('name',''))),('structure_parent',record.get('parent_id',record.get('building_id','')) or ''),('structure_code',record.get('code','')),('floor_level',record.get('level','')),('floor_height',record.get('height',''))]:self.fields[field].setText(str(value))
            if kind=='floor':self.floor_kind.setCurrentIndex(self.floor_kind.findData(record.get('kind')))
        for i,a in enumerate(self.project.get('project_schedule_tasks',[])):
            match=(a.get('wbs_id')==id if kind=='wbs' else id in a.get('floor_ids',[]) if kind=='floor' else any(f.get('building_id')==id and f['id'] in a.get('floor_ids',[]) for f in self.project.get('floors',[])))
            self.activity_table.setRowHidden(i,not match)
    def table_selected(self):
        row=self.activity_table.currentRow()
        if row>=0:self.select_activity(self.activity_table.item(row,0).text())
    def select_activity(self,id):
        a=next((x for x in self.project.get('project_schedule_tasks',[]) if x['id']==id),None)
        if not a:return
        self.selected_id=id
        scene=self.gantt.scene();scene.blockSignals(True)
        try:
            scene.clearSelection()
            if id in self.gantt.bars:self.gantt.bars[id].setSelected(True);self.gantt.ensureVisible(self.gantt.bars[id])
        finally:scene.blockSignals(False)
        a={**{'code':'','wbs_id':'','floor_ids':[],'zone_ids':[],'member_ids':[],'discipline_id':'','unit':'','responsible':'','status':'todo','measurement':{'kind':'none'}},**a}
        for key,value in [('id',id),('parent',a.get('parent_activity_id') or ''),('title',a['title']),('code',a['code']),('wbs',a['wbs_id']),('floors',','.join(a['floor_ids'])),('zones',','.join(a['zone_ids'])),('members',','.join(a['member_ids'])),('discipline',a['discipline_id']),('unit',a['unit']),('responsible',a['responsible']),('total',a['measurement'].get('total','')),('approver',a['measurement'].get('approved_by','')),('sources',','.join(a['measurement'].get('source_ids',[]))),('item_code',a['measurement'].get('item_code',''))]:self.fields['activity_'+key].setText(str(value))
        self.measurement_kind.setCurrentIndex(self.measurement_kind.findData(a['measurement']['kind']));self.activity_status.setCurrentIndex(self.activity_status.findData(a['status']))
        sc=a.get('schedule',{});self.fields['duration'].setText(str(sc.get('duration','')));self.fields['not_before'].setText(report_date(date.fromisoformat(sc['not_before'])) if sc.get('not_before') else '')
        self.fields['relationships'].setText(','.join(f"{r['pred']}:{r['type']}:{r['lag']}" for r in sc.get('relationships',[])))
        self.details.setText('فعالیت: '+a['title']+' | طبقات: '+','.join(a['floor_ids'])+' | اعضا: '+','.join(a['member_ids'])+' | مبنا: '+str(a['measurement']))
        self.location_choice.clear()
        try:
            locations=self.service.activity_locations(self.pid,id)
            for location in locations:self.location_choice.addItem(location['label'],location['key'])
            if not locations:self.location_choice.addItem('هندسه معتبر مرتبط ثبت نشده است',None)
        except (ValueError,RuntimeError) as e:self.location_choice.addItem(str(e),None)
        self.activity_table.blockSignals(True)
        for i in range(self.activity_table.rowCount()):
            if self.activity_table.item(i,0).text()==id:self.activity_table.setCurrentCell(i,0)
        self.activity_table.blockSignals(False)
    def show_progress(self):
        r=self.service.project_progress(self.pid,as_of=iso(self.text('report_date')))
        self.fill(self.progress_table,[[a['id'],a['total'],a['executed'],a['remaining'],a['actual'],a['planned'],a['variance']] for a in r['activities']])
        self.details.setText('پیشرفت کل: '+str(r['actual'])+' | مبنا: '+str(r['planned'])+' | برنامه جاری: '+str(r['planned_current'])+' | انحراف: '+str(r['variance'])+' | '+', '.join(r['issues']))
        if self.gantt.data:self.gantt.render(self.gantt.data,self.gantt.base,{a['id']:a for a in r['activities']})
