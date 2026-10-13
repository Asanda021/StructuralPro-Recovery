"""Formula controls inside the existing manual dialog; no separate application."""
from uuid import uuid4
from datetime import datetime
from PySide6.QtCore import Qt,QDate,QCalendar,QLocale,QTimer,QItemSelectionModel
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLineEdit,QTextEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QGridLayout,QLabel,QAbstractItemView,QMessageBox,QTabWidget,QCompleter,QScrollArea,QFileDialog
from core.takeoff.manual_formula_register import catalog

UNITS={'m':'متر','m2':'متر مربع','m3':'متر مکعب','kg':'کیلوگرم','ton':'تن','عدد':'عدد','cm':'سانتی‌متر','mm':'میلی‌متر','cm2':'سانتی‌متر مربع','mm2':'میلی‌متر مربع','cm3':'سانتی‌متر مکعب','mm3':'میلی‌متر مکعب'}
STATES={'draft':'بررسی‌نشده','reviewed':'بازبینی‌شده','committed':'قطعی'}

class VisibleRowsTable(QTableWidget):
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_A and event.modifiers() & Qt.ControlModifier:
            self.selectionModel().clearSelection()
            for row in range(self.rowCount()):
                if not self.isRowHidden(row):self.selectionModel().select(self.model().index(row,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
            event.accept();return
        super().keyPressEvent(event)


def pairs(widget):
    result={}
    for line in widget.toPlainText().splitlines():
        if not line.strip():continue
        if line.count('=')!=1:raise ValueError('هر پارامتر باید به صورت نام=مقدار باشد')
        key,val=(s.strip() for s in line.split('='))
        if key in result:raise ValueError('نام پارامتر تکراری است')
        result[key]=val
    return result

def attach(d,root):
    old=QWidget(d);old.setLayout(root);outer=QVBoxLayout(d);context=QFormLayout();outer.addLayout(context)
    for _ in range(2):
        row=d.manual_context_form.takeRow(0);context.addRow(row.labelItem.widget(),row.fieldItem.widget())
    tabs=QTabWidget(d);tabs.addTab(old,'ورودی تخصصی موجود');page=QWidget();tabs.addTab(page,'فرمول دستی مستند و کتابخانه');outer.addWidget(tabs);d.manual_tabs=tabs
    layout=QVBoxLayout(page);form_widget=QWidget();form=QFormLayout(form_widget);scroll=QScrollArea();d.formula_scroll=scroll;scroll.setWidgetResizable(True);scroll.setWidget(form_widget);scroll.setMinimumHeight(180);scroll.setMaximumHeight(360);layout.addWidget(scroll)
    d.formula_family=QComboBox();d.formula_family.addItem('انتخاب خانواده — بدون فرض محاسباتی',None)
    for r in catalog():d.formula_family.addItem(r['title'],r['code'])
    d.formula_family.setEditable(True);d.formula_family.setInsertPolicy(QComboBox.NoInsert);d.formula_family.completer().setFilterMode(Qt.MatchContains)
    d.formula_id=QLineEdit();d.formula_source=QLineEdit();d.formula_member=QLineEdit();d.formula_title=QLineEdit();d.formula_expression=QLineEdit();d.formula_basis=QLineEdit();d.formula_reason=QLineEdit();d.formula_reviewer=QLineEdit();d.formula_review_note=QLineEdit()
    d.formula_variables=QTextEdit();d.formula_variables.setMaximumHeight(70);d.formula_variables.setPlaceholderText('نام=مقدار، هر پارامتر در یک خط؛ مثال طول=10')
    d.formula_references=QTextEdit();d.formula_references.setMaximumHeight(55);d.formula_references.setPlaceholderText('نام مرجع=شناسه ردیف؛ مثال پایه=A')
    d.formula_unit=QComboBox();d.formula_unit.addItem('واحد را صریح انتخاب کنید',None)
    for k,v in UNITS.items():d.formula_unit.addItem(v,k)
    d.formula_components=QLabel();d.formula_components.setWordWrap(True)
    def family_changed(*_):
        key=d.formula_family.currentData();r=next((r for r in catalog() if r['code']==key),None)
        d.formula_components.setText('ریزآیتم‌های این گروه؛ ورودی و واحد باید مستند باشند: '+('، '.join(r['components']) if r else 'خانواده انتخاب نشده'))
    d.formula_family.currentIndexChanged.connect(family_changed)
    for label,widget in [('خانواده قابل جست‌وجو',d.formula_family),('ریزآیتم‌های مرتبط',d.formula_components),('شناسه ردیف',d.formula_id),('منبع یکتای اندازه‌گیری',d.formula_source),('شناسه عضو',d.formula_member),('شرح عملیات',d.formula_title),('واحد نتیجه',d.formula_unit),('فرمول صریح',d.formula_expression),('پارامترها',d.formula_variables),('وابستگی ردیف‌ها',d.formula_references),('مبنای فرمول و واحد هر ورودی',d.formula_basis),('علت ثبت یا اصلاح',d.formula_reason),('نام بازبین',d.formula_reviewer),('یادداشت کنترل فرمول و واحد',d.formula_review_note)]:form.addRow(label,widget)
    buttons=QGridLayout();layout.addLayout(buttons)
    d.formula_save_button=QPushButton('ذخیره پیش‌نویس / نسخه جدید');d.formula_load_button=QPushButton('بازگشایی ردیف انتخابی');d.formula_review_button=QPushButton('ثبت بازبینی صریح');d.formula_commit_button=QPushButton('انتقال بازبینی‌شده به BOQ');d.formula_new_button=QPushButton('ردیف تازه');d.formula_history_button=QPushButton('تاریخچه و علت تغییر')
    for i,b in enumerate([d.formula_new_button,d.formula_save_button,d.formula_load_button,d.formula_review_button,d.formula_commit_button,d.formula_history_button]):buttons.addWidget(b,i//3,i%3)
    d.formula_bulk_name=QLineEdit();d.formula_bulk_name.setPlaceholderText('نام پارامتر موجود');d.formula_bulk_value=QLineEdit();d.formula_bulk_value.setPlaceholderText('مقدار صریح جدید');d.formula_copy_floor=QLineEdit();d.formula_copy_floor.setPlaceholderText('طبقه مقصد متفاوت')
    d.formula_bulk_button=QPushButton('ویرایش گروهی پارامتر');d.formula_floor_copy_button=QPushButton('کپی گروهی به طبقه');d.formula_xlsx_button=QPushButton('گزارش کامل Excel');d.formula_pdf_button=QPushButton('گزارش کامل PDF')
    for i,b in enumerate([d.formula_bulk_name,d.formula_bulk_value,d.formula_bulk_button,d.formula_copy_floor,d.formula_floor_copy_button,d.formula_xlsx_button,d.formula_pdf_button]):buttons.addWidget(b,2+i//3,i%3)
    d.formula_group=QComboBox()
    for label,col in [('ترتیب شناسه',0),('گروه طبقه',1),('گروه عضو',12),('گروه کاری',2),('گروه واحد',5)]:d.formula_group.addItem(label,col)
    layout.addWidget(d.formula_group)
    root.removeWidget(d.search_field);d.formula_search=d.search_field;outer.addWidget(d.formula_search)
    root.removeWidget(d.table);d.formula_table=d.table;d.formula_table.setMinimumHeight(160);outer.addWidget(d.formula_table,2)
    root.removeWidget(d.status);outer.addWidget(d.status)
    d.formula_totals=QLabel();layout.addWidget(d.formula_totals);d.manual_date=QLabel();layout.addWidget(d.manual_date)
    def date():
        now=datetime.now().astimezone();d.manual_date.setText('تاریخ واقعی سیستم: '+QLocale(QLocale.Persian,QLocale.Iran).toString(QDate(now.year,now.month,now.day),QLocale.FormatType.ShortFormat,QCalendar(QCalendar.Jalali))+' — '+str(now.tzinfo))
    d.manual_date_timer=QTimer(d);d.manual_date_timer.timeout.connect(date);d.manual_date_timer.start(60000);date()
    d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[]
    def guarded(fn):
        def run(*_):
            try:fn();refresh()
            except Exception as e:d.status.setText('فرمول ثبت نشد: '+str(e))
        return run
    def rows():return d.service.load_manual_formulas(d.project_id.text().strip())
    def selected():
        selected_rows=d.formula_table.selectionModel().selectedRows()
        r=selected_rows[0].row() if selected_rows else d.formula_table.currentRow()
        if r<0 or not d.formula_table.item(r,0):raise ValueError('ردیف را انتخاب کنید')
        if d.formula_table.item(r,0).data(Qt.UserRole)!='formula':raise ValueError('برای این فرمان ردیف فرمول را انتخاب کنید')
        key=d.formula_table.item(r,0).text();return key,rows()[key]
    def refresh():
        from decimal import Decimal
        register=rows();d.formula_table.setSortingEnabled(False);d.formula_table.setRowCount(0)
        from app.manual_takeoff import _SAVED_ITEM_LABELS,_PARAM_LABELS
        legacy_totals={}
        for r in d.workbench.records if d.workbench else ():
            values=[r.record_id,r.floor_id,_SAVED_ITEM_LABELS.get(r.code,r.code),r.element_label,str(r.quantity),r.unit,'ذخیره شد' if r.record_id in d._saved_ids else 'آماده ذخیره',r.formula,str(dict(r.params)),r.source,str(r.revision),r.project_id,r.element_label,'']
            n=d.formula_table.rowCount();d.formula_table.insertRow(n)
            for c,v in enumerate(values):d.formula_table.setItem(n,c,QTableWidgetItem(v))
            d.formula_table.item(n,0).setData(Qt.UserRole,'legacy')
            visible=all(t in ' '.join(values).casefold() for t in d.formula_search.text().casefold().split());d.formula_table.setRowHidden(n,not visible)
            if visible:legacy_totals[r.unit]=legacy_totals.get(r.unit,Decimal(0))+Decimal(str(r.quantity))
        d.unit_totals.setText('جمع مستقل واحدها: '+' | '.join(f'{u}: {v:f}' for u,v in sorted(legacy_totals.items())))
        titles={r['code']:r['title'] for r in catalog()};totals={};tokens=d.formula_search.text().casefold().split()
        for key,row in sorted(register.items()):
            data=row['data'];values=[key,data['floor'],titles[data['family']],data['title'],str(row['quantity']),UNITS[data['unit']],STATES[row['status']],data['expression'],', '.join(k+'='+str(v) for k,v in data['variables'].items()),data['source_id'],str(row['revision']),d.project_id.text().strip(),data['member'],', '.join(data['references'].values())]
            n=d.formula_table.rowCount();d.formula_table.insertRow(n)
            for i,v in enumerate(values):d.formula_table.setItem(n,i,QTableWidgetItem(v))
            d.formula_table.item(n,0).setData(Qt.UserRole,'formula')
            visible=all(t in ' '.join(values).casefold() for t in tokens);d.formula_table.setRowHidden(n,not visible)
            if visible:totals[data['unit']]=totals.get(data['unit'],Decimal(0))+Decimal(str(row['quantity']))
        d.formula_table.setSortingEnabled(True);d.formula_table.sortItems(d.formula_group.currentData(),Qt.AscendingOrder);d.formula_totals.setText('جمع واحدهای مستقل: '+' | '.join(UNITS[u]+'='+str(v) for u,v in totals.items()))
    d.refresh_formula_rows=refresh;d.formula_group.currentIndexChanged.connect(guarded(lambda:None));d.formula_search.textChanged.connect(guarded(lambda:None))
    def new():
        d.formula_id.setText('MF-'+uuid4().hex);d.formula_source.setText('manual-formula:'+uuid4().hex);d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[]
    def payload():
        return {'family':d.formula_family.currentData(),'title':d.formula_title.text(),'floor':d.floor_id.text(),'member':d.formula_member.text(),'unit':d.formula_unit.currentData(),'expression':d.formula_expression.text(),'variables':pairs(d.formula_variables),'references':pairs(d.formula_references),'source_id':d.formula_source.text(),'basis':d.formula_basis.text(),'deductions':d._formula_deductions}
    def save():
        key=d.formula_id.text().strip()
        if d._formula_selected and key!=d._formula_selected:raise ValueError('شناسه ردیف در ویرایش قابل تغییر نیست')
        data={'family':d.formula_family.currentData(),'title':d.formula_title.text(),'floor':d.floor_id.text(),'member':d.formula_member.text(),'unit':d.formula_unit.currentData(),'expression':d.formula_expression.text(),'variables':pairs(d.formula_variables),'references':pairs(d.formula_references),'source_id':d.formula_source.text(),'basis':d.formula_basis.text(),'deductions':d._formula_deductions}
        r=d.service.save_manual_formula(d.project_id.text().strip(),key,data,expected_revision=d._formula_revision,reason=d.formula_reason.text());d._formula_revision=r['revision'];d._formula_selected=key;d.status.setText('پیش‌نویس نسخه‌دار ذخیره شد؛ برای BOQ بازبینی لازم است')
    def load():
        key,row=selected();data=row['data'];d._formula_revision=row['revision'];d._formula_selected=key;d._formula_deductions=row['data']['deductions']
        for field,name in [(d.formula_id,None),(d.formula_source,'source_id'),(d.formula_title,'title'),(d.formula_member,'member'),(d.formula_expression,'expression'),(d.formula_basis,'basis'),(d.floor_id,'floor')]:field.setText(key if name is None else data[name])
        d.formula_family.setCurrentIndex(d.formula_family.findData(data['family']));d.formula_unit.setCurrentIndex(d.formula_unit.findData(data['unit']))
        d.formula_variables.setPlainText('\n'.join(k+'='+str(v) for k,v in data['variables'].items()));d.formula_references.setPlainText('\n'.join(k+'='+v for k,v in data['references'].items()))
        d.formula_reason.clear();d.status.setText('نسخه ذخیره‌شده بازگشایی و دوباره محاسبه شد')
    def review():
        key,row=selected();d.service.review_manual_formula(d.project_id.text().strip(),key,expected_revision=row['revision'],reviewer=d.formula_reviewer.text(),note=d.formula_review_note.text())
    def commit():
        key,row=selected();d.service.commit_manual_formula(d.project_id.text().strip(),key,expected_revision=row['revision']);d.refresh_saved_rows()
    def history():
        key,row=selected();project=d.service.open_project(d.project_id.text().strip());h=[v for v in project.get('manual_formula_history',[]) if v['row_id']==key];QMessageBox.information(d,'تاریخچه نسخه‌ها','\n'.join('نسخه '+str(v['revision'])+'؛ علت: '+v['reason']+'؛ '+v['at'] for v in h))
    def selected_many():
        indices=[i for i in d.formula_table.selectionModel().selectedRows() if not d.formula_table.isRowHidden(i.row())]
        if not indices:raise ValueError('ردیف‌های موردنظر را انتخاب کنید')
        if any(d.formula_table.item(i.row(),0).data(Qt.UserRole)!='formula' for i in indices):raise ValueError('ویرایش گروهی فرمول نباید با ورودی تخصصی مخلوط شود')
        keys=[d.formula_table.item(i.row(),0).text() for i in indices];register=rows();return keys,{k:register[k]['revision'] for k in keys}
    def bulk():
        keys,versions=selected_many();d.service.bulk_edit_manual_formulas(d.project_id.text().strip(),keys,changes={'variables':{d.formula_bulk_name.text().strip():d.formula_bulk_value.text().strip()}},expected_revisions=versions,reason=d.formula_reason.text())
    def copy_floor():
        keys,versions=selected_many();d.service.copy_manual_formulas(d.project_id.text().strip(),keys,floor=d.formula_copy_floor.text(),expected_revisions=versions,reason=d.formula_reason.text())
    def export(fmt):
        path,_=QFileDialog.getSaveFileName(d,'گزارش مستند متره','',fmt.upper()+' (*.'+fmt+')')
        if path:d.service.export_manual_formula_report(d.project_id.text().strip(),path,format=fmt);d.status.setText('گزارش مستند ذخیره شد: '+path)
    d.formula_bulk_button.clicked.connect(guarded(bulk));d.formula_floor_copy_button.clicked.connect(guarded(copy_floor));d.formula_xlsx_button.clicked.connect(guarded(lambda:export('xlsx')));d.formula_pdf_button.clicked.connect(guarded(lambda:export('pdf')))
    for b,fn in [(d.formula_new_button,new),(d.formula_save_button,save),(d.formula_load_button,load),(d.formula_review_button,review),(d.formula_commit_button,commit),(d.formula_history_button,history)]:b.clicked.connect(guarded(fn))
    d.formula_creator=QLineEdit();d.formula_amend_id=QLineEdit();d.deduction_source=QLineEdit();d.deduction_variable=QLineEdit();d.deduction_quantity=QLineEdit();d.deduction_basis=QLineEdit();d.deduction_unit=QComboBox()
    d.deduction_unit.addItem('واحد کسر را انتخاب کنید',None)
    for key,title in UNITS.items():d.deduction_unit.addItem(title,key)
    d.deduction_summary=QLabel();d.deduction_summary.setWordWrap(True)
    for label,widget in [('سازنده اصلاحیه',d.formula_creator),('شناسه اصلاحیه',d.formula_amend_id),('منبع هندسی یکتای کسر',d.deduction_source),('پارامتر کسر در فرمول',d.deduction_variable),('مقدار صریح کسر',d.deduction_quantity),('واحد کسر',d.deduction_unit),('مبنای هندسی کسر',d.deduction_basis),('پیش از کسر / خالص',d.deduction_summary)]:form.addRow(label,widget)
    command_widget=QWidget();commands=QGridLayout(command_widget);form.addRow('گردش کنترل‌شده',command_widget)
    names=[('formula_amend_button','ساخت اصلاحیه قطعی'),('formula_amend_review_button','بازبینی مستقل اصلاحیه'),('formula_amend_apply_button','اعمال اصلاحیه مجاز به BOQ'),('deduction_save_button','افزودن / اصلاح کسر'),('deduction_delete_button','حذف کنترل‌شده کسر'),('formula_delete_button','حذف پیش‌نویس انتخابی'),('formula_undo_button','واگرد دفتر فرمول'),('formula_redo_button','تکرار دفتر فرمول')]
    for i,(attr,title) in enumerate(names):button=QPushButton(title);setattr(d,attr,button);commands.addWidget(button,i//2,i%2)
    def amend():
        key,row=selected();a=d.service.create_manual_formula_amendment(d.project_id.text().strip(),key,payload(),expected_revision=d._formula_revision,created_by=d.formula_creator.text(),reason=d.formula_reason.text());d.formula_amend_id.setText(a['id']);d.status.setText('اصلاحیه ثبت شد؛ اصل ردیف و BOQ تغییر نکرد')
    def amend_review():
        d.service.review_manual_formula_amendment(d.project_id.text().strip(),d.formula_amend_id.text().strip(),expected_revision=1,reviewer=d.formula_reviewer.text(),note=d.formula_review_note.text())
    def amend_apply():
        d.service.apply_manual_formula_amendment(d.project_id.text().strip(),d.formula_amend_id.text().strip(),expected_revision=1);d.status.setText('نمای مؤثر BOQ اصلاح شد؛ اصل متره محفوظ است')
    def deduction(remove=False):
        key,row=selected();item={'id':d.deduction_source.text().strip(),'source_id':d.deduction_source.text().strip(),'variable':d.deduction_variable.text().strip(),'quantity':d.deduction_quantity.text().strip(),'unit':d.deduction_unit.currentData(),'basis':d.deduction_basis.text().strip()}
        if row['status']=='committed':
            from core.takeoff.manual_formula_deductions import change_data
            proposal=change_data(row['data'],remove_id=item['id']) if remove else change_data(row['data'],item)
            a=d.service.create_manual_formula_amendment(d.project_id.text().strip(),key,proposal,expected_revision=row['revision'],created_by=d.formula_creator.text(),reason=d.formula_reason.text());d.formula_amend_id.setText(a['id']);d.status.setText('اصلاح کسر قطعی به‌صورت اصلاحیه ثبت شد؛ BOQ هنوز ثابت است')
        else:
            if remove:d.service.remove_manual_formula_deduction(d.project_id.text().strip(),key,item['id'],expected_revision=row['revision'],reason=d.formula_reason.text())
            else:d.service.set_manual_formula_deduction(d.project_id.text().strip(),key,item,expected_revision=row['revision'],reason=d.formula_reason.text())
        summary=d.service.manual_formula_deduction_summary(d.project_id.text().strip(),key);d.deduction_summary.setText('پیش از کسر: '+str(summary['gross'])+'؛ خالص: '+str(summary['net'])+'؛ کسر: '+str(summary['deducted']))
    def delete():
        keys,versions=selected_many();d.service.delete_manual_formulas(d.project_id.text().strip(),keys,expected_revisions=versions,reason=d.formula_reason.text())
    for button,fn in [(d.formula_amend_button,amend),(d.formula_amend_review_button,amend_review),(d.formula_amend_apply_button,amend_apply),(d.deduction_save_button,lambda:deduction()),(d.deduction_delete_button,lambda:deduction(True)),(d.formula_delete_button,delete),(d.formula_undo_button,lambda:d.service.undo_manual_formulas(d.project_id.text().strip())),(d.formula_redo_button,lambda:d.service.redo_manual_formulas(d.project_id.text().strip()))]:button.clicked.connect(guarded(fn))
    d._formula_project=d.project_id.text().strip()
    def project_changed():
        current=d.project_id.text().strip()
        if current!=d._formula_project:
            d._formula_project=current;d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[];guarded(lambda:None)()
    d.project_id.editingFinished.connect(project_changed)
    if d.project_id.text().strip():guarded(lambda:None)()
