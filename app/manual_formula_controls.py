"""Formula controls inside the existing manual dialog; no separate application."""
from uuid import uuid4
from datetime import datetime
from PySide6.QtCore import Qt,QDate,QCalendar,QLocale,QTimer,QItemSelectionModel
from PySide6.QtWidgets import QWidget,QVBoxLayout,QFormLayout,QLineEdit,QTextEdit,QComboBox,QPushButton,QTableWidget,QTableWidgetItem,QGridLayout,QLabel,QAbstractItemView,QMessageBox,QTabWidget,QCompleter,QScrollArea,QFileDialog
from core.takeoff.manual_formula_register import catalog

UNITS={'m':'متر','m2':'متر مربع','m3':'متر مکعب','kg':'کیلوگرم','ton':'تن','عدد':'عدد','cm':'سانتی‌متر','mm':'میلی‌متر','cm2':'سانتی‌متر مربع','mm2':'میلی‌متر مربع','cm3':'سانتی‌متر مکعب','mm3':'میلی‌متر مکعب','1':'بدون بُعد / ضریب','s':'ثانیه','min':'دقیقه','h':'ساعت','m/s':'متر بر ثانیه','kg/m':'کیلوگرم بر متر','kg/m3':'کیلوگرم بر متر مکعب'}
STATES={'draft':'بررسی‌نشده','reviewed':'بازبینی‌شده','committed':'قطعی'}

class VisibleRowsTable(QTableWidget):
    def set_sort_kinds(self,kinds):
        self._sort_kinds=dict(kinds)
        sorting=self.isSortingEnabled();self.setSortingEnabled(False)
        for r in range(self.rowCount()):
            for c in range(self.columnCount()):
                item=self.item(r,c)
                if item is not None:
                    from app.manual_table_sort import TypedItem
                    if isinstance(item,TypedItem):item.kind=self._sort_kinds.get(c,'natural')
                    else:self.setItem(r,c,item)
        self.setSortingEnabled(sorting)
    def setItem(self,row,col,item):
        from app.manual_table_sort import TypedItem
        if not isinstance(item,TypedItem):item=TypedItem(item,self,getattr(self,'_sort_kinds',{}).get(col,'natural'),row)
        else:item.kind=getattr(self,'_sort_kinds',{}).get(col,'natural')
        super().setItem(row,col,item)
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
        from core.takeoff.manual_form_fields import canonical
        key=canonical(key)
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
    d.formula_bulk_unit=QComboBox();d.formula_bulk_unit.addItem('واحد فعلی حفظ شود',None)
    for key,label in UNITS.items():d.formula_bulk_unit.addItem(label,key)
    d.formula_bulk_button=QPushButton('ویرایش گروهی پارامتر');d.formula_floor_copy_button=QPushButton('کپی گروهی به طبقه');d.formula_xlsx_button=QPushButton('گزارش کامل Excel');d.formula_pdf_button=QPushButton('گزارش کامل PDF')
    for i,b in enumerate([d.formula_bulk_name,d.formula_bulk_value,d.formula_bulk_unit,d.formula_bulk_button,d.formula_copy_floor,d.formula_floor_copy_button,d.formula_xlsx_button,d.formula_pdf_button]):buttons.addWidget(b,2+i//3,i%3)
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
    d._unit_choices={};d.dynamic_units={}
    d.formula_unit_mode=QComboBox();d.formula_unit_mode.addItem('قرارداد تاریخی — نیازمند تعیین واحد و بازبینی ابعادی',False);d.formula_unit_mode.addItem('کنترل ابعادی ساختاریافته — همه واحدها صریح',True);d.formula_unit_mode.setCurrentIndex(1);form.addRow('قرارداد واحد نسخه‌دار',d.formula_unit_mode)
    d.unit_migration_warning=QLabel('مسیر تاریخی فاقد کنترل ابعادی خودکار است؛ برای ثبت واحدها، قرارداد ساختاریافته را انتخاب کنید.');d.unit_migration_warning.setWordWrap(True);form.addRow(d.unit_migration_warning)
    d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[];d._formula_site={}
    def guarded(fn):
        def run(*_):
            try:fn();refresh()
            except Exception as e:
                from core.takeoff.manual_form_fields import persian_error
                d.status.setText('فرمول ثبت نشد: '+persian_error(e))
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
        selection={(d.table.item(i.row(),0).data(Qt.UserRole),d.table.item(i.row(),0).text()) for i in d.table.selectionModel().selectedRows() if d.table.item(i.row(),0)}
        sort_col=d.table.horizontalHeader().sortIndicatorSection();sort_order=d.table.horizontalHeader().sortIndicatorOrder()
        register=rows();d.formula_table.setSortingEnabled(False);d.formula_table.setRowCount(0)
        from app.manual_takeoff import _SAVED_ITEM_LABELS,_PARAM_LABELS
        legacy_totals={}
        for r in d.workbench.records if d.workbench else ():
            values=[r.record_id,r.floor_id,_SAVED_ITEM_LABELS.get(r.code,r.code),r.element_label,str(r.quantity),UNITS.get(r.unit,r.unit),'ذخیره شد' if r.record_id in d._saved_ids else 'آماده ذخیره',__import__('core.takeoff.manual_form_fields',fromlist=['expression']).expression(r.formula,display=True),', '.join(_PARAM_LABELS.get(k,'پارامتر مستند')+'='+str(v) for k,v in r.params.items()),r.source,str(r.revision),r.project_id,r.element_label,'',str(r.params.get('count','')),'',str(r.params.get('block','')),str(r.params.get('location',''))]
            n=d.formula_table.rowCount();d.formula_table.insertRow(n)
            for c,v in enumerate(values):d.formula_table.setItem(n,c,QTableWidgetItem(v))
            d.formula_table.item(n,0).setData(Qt.UserRole,'legacy')
            visible=all(t in ' '.join(values).casefold() for t in d.formula_search.text().casefold().split());d.formula_table.setRowHidden(n,not visible)
            if visible:legacy_totals[r.unit]=legacy_totals.get(r.unit,Decimal(0))+Decimal(str(r.quantity))
        d.unit_totals.setText('جمع مستقل واحدها: '+' | '.join(f'{u}: {v:f}' for u,v in sorted(legacy_totals.items())))
        titles={r['code']:r['title'] for r in catalog()};totals={};tokens=d.formula_search.text().casefold().split()
        for key,row in sorted(register.items()):
            data=row['data'];values=[key,data['floor'],titles[data['family']],data['title'],str(row['quantity']),UNITS[data['unit']],STATES[row['status']],__import__('core.takeoff.manual_form_fields',fromlist=['expression']).expression(data['expression'],display=True),', '.join(__import__('core.takeoff.manual_form_fields',fromlist=['LABELS']).LABELS.get(k,(k,''))[0]+'='+str(v)+(' '+UNITS[data['variable_units'][k]] if 'variable_units' in data else ' (واحد نامشخص؛ بازبینی لازم)') for k,v in data['variables'].items()),data['source_id'],str(row['revision']),d.project_id.text().strip(),data['member'],', '.join(data['references'].values()),str(data['variables'].get('count',data['variables'].get('تعداد',''))),row.get('updated_at',''),data.get('block',''),data.get('location','')]
            n=d.formula_table.rowCount();d.formula_table.insertRow(n)
            for i,v in enumerate(values):d.formula_table.setItem(n,i,QTableWidgetItem(v))
            d.formula_table.item(n,0).setData(Qt.UserRole,'formula')
            if row.get('updated_at'):
                date_value=datetime.fromisoformat(row['updated_at']).astimezone();cell=d.table.item(n,15);cell.setData(Qt.UserRole+1,row['updated_at']);cell.setText(QLocale(QLocale.Persian,QLocale.Iran).toString(QDate(date_value.year,date_value.month,date_value.day),QLocale.ShortFormat,QCalendar(QCalendar.Jalali))+' '+date_value.strftime('%H:%M:%S'))
            visible=all(t in ' '.join(values).casefold() for t in tokens);d.formula_table.setRowHidden(n,not visible)
            if visible:totals[data['unit']]=totals.get(data['unit'],Decimal(0))+Decimal(str(row['quantity']))
        d.formula_table.setSortingEnabled(True)
        for i in range(d.table.rowCount()):
            cell=d.table.item(i,0)
            if cell and (cell.data(Qt.UserRole),cell.text()) in selection:d.table.selectionModel().select(d.table.model().index(i,0),QItemSelectionModel.Select|QItemSelectionModel.Rows)
        d.formula_table.sortItems(sort_col if sort_col>=0 else 0,sort_order);d.formula_totals.setText('جمع واحدهای مستقل: '+' | '.join(UNITS[u]+'='+str(v) for u,v in totals.items()))
    d.refresh_formula_rows=refresh
    d.formula_unit_mode.currentIndexChanged.connect(lambda *_:d.unit_migration_warning.setText('کنترل ابعادی فعال؛ تمام واحدها ضروری‌اند و واحد نامشخص حدس زده نمی‌شود.' if d.formula_unit_mode.currentData() else 'قرارداد تاریخی فاقد کنترل ابعادی خودکار؛ نیازمند مهاجرت صریح و بازبینی است.'))
    def grouping(*_):
        d.table.sortItems(d.formula_group.currentData(),Qt.AscendingOrder);guarded(lambda:None)()
    d.formula_group.currentIndexChanged.connect(grouping);d.formula_search.textChanged.connect(guarded(lambda:None))
    def new():
        d._unit_choices={};d.formula_unit_mode.setCurrentIndex(1)
        for combo in d.dynamic_units.values():combo.setCurrentIndex(0)
        d.formula_id.setText('MF-'+uuid4().hex);d.formula_source.setText('manual-formula:'+uuid4().hex);d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[];d._formula_site={}
    def unit_fields():
        values=pairs(d.formula_variables)
        if d.formula_unit_mode.currentData() or not d._formula_selected:
            units={key:d._unit_choices.get(key) for key in values}
            if any(value is None for value in units.values()):raise ValueError('واحد ساختاریافته همه پارامترها را صریح انتخاب کنید')
            return {'variable_units':units,'unit_policy':'dimensional_decimal_v1'}
        return {}
    def payload():
        return {'family':d.formula_family.currentData(),'title':d.formula_title.text(),'floor':d.floor_id.text(),'member':d.formula_member.text(),'unit':d.formula_unit.currentData(),'expression':__import__('core.takeoff.manual_form_fields',fromlist=['expression']).expression(d.formula_expression.text()),'variables':pairs(d.formula_variables),'references':pairs(d.formula_references),'source_id':d.formula_source.text(),'basis':d.formula_basis.text(),'deductions':[dict(v,variable=__import__('core.takeoff.manual_form_fields',fromlist=['canonical']).canonical(v.get('variable',v['id'])),source_id=v.get('source_id',v['id'])) for v in d._formula_deductions],**d._formula_site,**unit_fields()}
    def save():
        key=d.formula_id.text().strip()
        if d._formula_selected and key!=d._formula_selected:raise ValueError('شناسه ردیف در ویرایش قابل تغییر نیست')
        data={'family':d.formula_family.currentData(),'title':d.formula_title.text(),'floor':d.floor_id.text(),'member':d.formula_member.text(),'unit':d.formula_unit.currentData(),'expression':__import__('core.takeoff.manual_form_fields',fromlist=['expression']).expression(d.formula_expression.text()),'variables':pairs(d.formula_variables),'references':pairs(d.formula_references),'source_id':d.formula_source.text(),'basis':d.formula_basis.text(),'deductions':[dict(v,variable=__import__('core.takeoff.manual_form_fields',fromlist=['canonical']).canonical(v.get('variable',v['id'])),source_id=v.get('source_id',v['id'])) for v in d._formula_deductions],**d._formula_site,**unit_fields()}
        r=d.service.save_manual_formula(d.project_id.text().strip(),key,data,expected_revision=d._formula_revision,reason=d.formula_reason.text());d._formula_revision=r['revision'];d._formula_selected=key;d.status.setText('پیش‌نویس نسخه‌دار ذخیره شد؛ برای BOQ بازبینی لازم است')
    def load():
        key,row=selected();data=row['data'];d._formula_revision=row['revision'];d._formula_selected=key;d._formula_deductions=row['data']['deductions'];d._formula_site={k:data[k] for k in ('block','location') if k in data}
        for field,name in [(d.formula_id,None),(d.formula_source,'source_id'),(d.formula_title,'title'),(d.formula_member,'member'),(d.formula_expression,'expression'),(d.formula_basis,'basis'),(d.floor_id,'floor')]:field.setText(key if name is None else __import__('core.takeoff.manual_form_fields',fromlist=['expression']).expression(data[name],display=True) if name=='expression' else data[name])
        d.formula_family.setCurrentIndex(d.formula_family.findData(data['family']));d.formula_unit.setCurrentIndex(d.formula_unit.findData(data['unit']))
        d._unit_choices={__import__('core.takeoff.manual_form_fields',fromlist=['canonical']).canonical(k):v for k,v in data.get('variable_units',{}).items()};d.formula_unit_mode.setCurrentIndex(1 if 'variable_units' in data else 0)
        d.formula_variables.setPlainText('\n'.join(__import__('core.takeoff.manual_form_fields',fromlist=['LABELS']).LABELS.get(k,(k,''))[0]+'='+str(v) for k,v in data['variables'].items()));d.formula_references.setPlainText('\n'.join(k+'='+v for k,v in data['references'].items()))
        for name,combo in d.dynamic_units.items():
            combo.blockSignals(True);combo.setCurrentIndex(max(0,combo.findData(d._unit_choices.get(name))));combo.blockSignals(False)
        d.formula_reason.clear();d.status.setText('نسخه ذخیره‌شده بازگشایی و دوباره محاسبه شد')
    def review():
        key,row=selected()
        if 'variable_units' not in row['data']:raise ValueError('ردیف تاریخی ابتدا نیازمند تعیین صریح واحدهای ساختاریافته و ثبت نسخه جدید است')
        d.service.review_manual_formula(d.project_id.text().strip(),key,expected_revision=row['revision'],reviewer=d.formula_reviewer.text(),note=d.formula_review_note.text())
    def commit():
        key,row=selected()
        if 'variable_units' not in row['data']:raise ValueError('انتقال تازه نیازمند قرارداد واحد ساختاریافته است؛ مقدار قطعی قدیمی تغییر نمی‌کند')
        d.service.commit_manual_formula(d.project_id.text().strip(),key,expected_revision=row['revision']);d.refresh_saved_rows()
    def history():
        key,row=selected();project=d.service.open_project(d.project_id.text().strip());h=[v for v in project.get('manual_formula_history',[]) if v['row_id']==key];QMessageBox.information(d,'تاریخچه نسخه‌ها','\n'.join('نسخه '+str(v['revision'])+'؛ علت: '+v['reason']+'؛ '+v['at'] for v in h))
    def selected_many():
        indices=[i for i in d.formula_table.selectionModel().selectedRows() if not d.formula_table.isRowHidden(i.row())]
        if not indices:raise ValueError('ردیف‌های موردنظر را انتخاب کنید')
        if any(d.formula_table.item(i.row(),0).data(Qt.UserRole)!='formula' for i in indices):raise ValueError('ویرایش گروهی فرمول نباید با ورودی تخصصی مخلوط شود')
        keys=[d.formula_table.item(i.row(),0).text() for i in indices];register=rows();return keys,{k:register[k]['revision'] for k in keys}
    def bulk():
        keys,versions=selected_many();name=__import__('core.takeoff.manual_form_fields',fromlist=['canonical']).canonical(d.formula_bulk_name.text().strip());changes={'variables':{name:d.formula_bulk_value.text().strip()}}
        if d.formula_bulk_unit.currentData() is not None:changes['variable_units']={name:d.formula_bulk_unit.currentData()}
        d.service.bulk_edit_manual_formulas(d.project_id.text().strip(),keys,changes=changes,expected_revisions=versions,reason=d.formula_reason.text())
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
    from core.takeoff.manual_form_fields import family_fields,LABELS,expression as formula_expression,canonical
    d.formula_subitem=QComboBox();d.formula_subitem.setEditable(True);d.formula_subitem.setInsertPolicy(QComboBox.NoInsert);d.formula_subitem.completer().setFilterMode(Qt.MatchContains);form.addRow('زیرآیتم قابل جست‌وجو',d.formula_subitem)
    d.dynamic_group=QLabel();form.addRow('گروه ورودی؛ هیچ مقدار پیش‌فرض ندارد',d.dynamic_group)
    dynamic_widget=QWidget();dynamic_form=QFormLayout(dynamic_widget);form.addRow('ورودی‌های مرتبط',dynamic_widget);d.dynamic_parameters={};d.dynamic_missing=QLabel();form.addRow('ورودی‌های الزامی فرمول',d.dynamic_missing)
    def dynamic():
        import ast
        group,fields=family_fields(d.formula_family.currentData());d.dynamic_group.setText(group)
        try:required={n.id for n in ast.walk(ast.parse(formula_expression(d.formula_expression.text()),mode='eval')) if isinstance(n,ast.Name)}-set(pairs(d.formula_references))
        except Exception:required=set()
        try:values=pairs(d.formula_variables)
        except ValueError:values={}
        desired=list(dict.fromkeys(list(fields)+sorted(required)))
        if list(d.dynamic_parameters)==desired:
            for name,field in d.dynamic_parameters.items():
                field.setText(str(values.get(name,'')))
            missing=required-set(values);d.dynamic_missing.setText('اطلاعات ناقص: '+', '.join(LABELS.get(k,(k,''))[0] for k in sorted(missing)) if missing else 'همه پارامترها وارد شده‌اند؛ اعتبارسنجی هنگام ذخیره انجام می‌شود')
            return
        while dynamic_form.rowCount():dynamic_form.removeRow(0)
        d.dynamic_parameters={};d.dynamic_units={}
        for name in desired:
            label,unit=LABELS.get(name,(name,'واحد را در مبنا مشخص کنید'));field=QLineEdit(str(values.get(name,'')));field.setPlaceholderText('ورودی صریح؛ '+unit);field.setToolTip(label+'؛ '+unit+'؛ مقدار یا ضریب حدسی وارد نشود');d.dynamic_parameters[name]=field
            combo=QComboBox();combo.addItem('واحد صریح را انتخاب کنید',None)
            for code,title in UNITS.items():combo.addItem(title,code)
            combo.setCurrentIndex(max(0,combo.findData(d._unit_choices.get(name))));d.dynamic_units[name]=combo
            container=QWidget();line=__import__('PySide6.QtWidgets',fromlist=['QHBoxLayout']).QHBoxLayout(container);line.setContentsMargins(0,0,0,0);line.addWidget(field);line.addWidget(combo)
            dynamic_form.addRow(label+(' *' if name in required else ' (اختیاری)'),container)
            def set_unit(index,k=name,c=combo):
                d._unit_choices[k]=c.currentData()
                if c.currentData() is not None:d.formula_unit_mode.setCurrentIndex(1)
            combo.currentIndexChanged.connect(set_unit)
            def update(value,k=name):
                try:v=pairs(d.formula_variables)
                except ValueError:return
                if value.strip():v[k]=value.strip()
                else:v.pop(k,None)
                d.formula_variables.setPlainText('\n'.join(LABELS.get(n,(n,''))[0]+'='+str(x) for n,x in v.items()))
            field.textEdited.connect(update)
        missing=required-set(values);d.dynamic_missing.setText('اطلاعات ناقص: '+', '.join(LABELS.get(k,(k,''))[0] for k in sorted(missing)) if missing else 'همه پارامترهای فرمول دارای ورودی‌اند؛ اعتبارسنجی هنگام ذخیره انجام می‌شود')
    def subitems(*_):
        d.formula_subitem.clear();d.formula_subitem.addItem('زیرآیتم را انتخاب کنید')
        row=next((r for r in catalog() if r['code']==d.formula_family.currentData()),None)
        if row:d.formula_subitem.addItems(row['components'])
        dynamic()
    d.formula_family.currentIndexChanged.connect(subitems);d.formula_expression.editingFinished.connect(dynamic);d.formula_variables.textChanged.connect(dynamic)
    d.formula_subitem.activated.connect(lambda *_:d.formula_title.setText(d.formula_subitem.currentText()));subitems()
    d.copy_deduction_sources=QTextEdit();d.copy_deduction_sources.setMaximumHeight(70);d.copy_deduction_sources.setPlaceholderText('هر سطر: شناسه ردیف | منبع کسر قبلی | منبع هندسی جدید صریح');form.addRow('منابع هندسی تازه برای کپی کسورات',d.copy_deduction_sources)
    d.destination_project=QComboBox()
    for p in d.service.store.list():d.destination_project.addItem(p['name'],p['id'])
    d.destination_project.setCurrentIndex(d.destination_project.findData(d.project_id.text().strip()));d.destination_block=QLineEdit();d.destination_floor=QLineEdit();d.destination_location=QLineEdit()
    for label,w in [('پروژه مقصد',d.destination_project),('بلوک مقصد',d.destination_block),('طبقه مقصد',d.destination_floor),('محل یا آکس مقصد',d.destination_location)]:form.addRow(label,w)
    d.formula_move_button=QPushButton('انتقال نسخه‌دار به محل مقصد');d.formula_location_copy_button=QPushButton('کپی مستقل به محل مقصد');form.addRow(d.formula_move_button,d.formula_location_copy_button)
    def relocate(mode):
        indices=[i for i in d.table.selectionModel().selectedRows() if not d.table.isRowHidden(i.row())]
        providers={d.table.item(i.row(),0).data(Qt.UserRole) for i in indices}
        destination={'project_id':d.destination_project.currentData(),'block':d.destination_block.text(),'floor':d.destination_floor.text(),'location':d.destination_location.text()}
        if providers=={'legacy'}:
            if destination['project_id']!=d.project_id.text().strip():raise ValueError('انتقال بین پروژه‌ها نیازمند گردش مستقل است')
            keys=[d.table.item(i.row(),0).text() for i in indices]
            if any(k in d._saved_ids for k in keys):raise ValueError('ردیف ذخیره‌شده تخصصی به اصلاحیه مستقل نیاز دارد')
            if d.workbench is None or d.workbench.project_id!=destination['project_id']:raise ValueError('پروژه پیش‌نمایش نامطابق است')
            from core.takeoff.manual_formula_register import text
            reason=text(d.formula_reason.text(),'علت انتقال')
            d.workbench.relocate_records(keys,floor=destination['floor'],block=destination['block'],location=destination['location'],mode=mode);d._audit('location_'+mode,{'record_ids':keys,'destination':destination,'reason':reason});d.status.setText('پیش‌نمایش تخصصی منتقل شد؛ ذخیره پروژه هنوز لازم است');return
        keys,versions=selected_many();sources={}
        for line in d.copy_deduction_sources.toPlainText().splitlines():
            if not line.strip():continue
            parts=[p.strip() for p in line.split('|')]
            if len(parts)!=3 or not all(parts):raise ValueError('منابع کسر باید شامل ردیف، منبع قبلی و منبع جدید باشند')
            key,old,new=parts
            if old in sources.get(key,{}):raise ValueError('منبع کسر در ورودی کپی تکراری است')
            sources.setdefault(key,{})[old]=new
        d.service.relocate_manual_formulas(d.project_id.text().strip(),keys,destination=destination,mode=mode,expected_revisions=versions,reason=d.formula_reason.text(),deduction_sources=sources);d.status.setText('عملیات محل اجرا ثبت شد؛ شناسه‌ها و نسخه‌ها کنترل شدند')
    d.formula_move_button.clicked.connect(guarded(lambda:relocate('move')));d.formula_location_copy_button.clicked.connect(guarded(lambda:relocate('copy')))
    d._formula_project=d.project_id.text().strip()
    def project_changed():
        current=d.project_id.text().strip()
        if current!=d._formula_project:
            d._formula_project=current;d._formula_revision=0;d._formula_selected=None;d._formula_deductions=[];d._formula_site={};guarded(lambda:None)()
    d.project_id.editingFinished.connect(project_changed)
    if d.project_id.text().strip():guarded(lambda:None)()
