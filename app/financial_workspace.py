"""Operational project finance; existing guarded services own all writes."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,
    QPushButton,QLabel,QComboBox,QTabWidget,QWidget,QTableWidget,QTableWidgetItem,QFileDialog,QAbstractItemView,QHeaderView)
from core.reports.exporters import report_date

STATES={'DRAFT':'پیش‌نویس','REVIEWED':'بازبینی‌شده','APPROVED':'تأییدشده','ISSUED':'صادرشده','POSTED':'قطعی'}
KINDS={'budget':'بودجه','commitment':'تعهد','cost':'هزینه واقعی','payment':'پرداخت واقعی','receipt':'دریافت واقعی'}


class FinancialWorkspace(QDialog):
    def __init__(self,service,project_id,parent=None):
        super().__init__(parent);self.service=service;self.pid=project_id
        self.setAttribute(Qt.WA_DeleteOnClose)
        if parent is None:
            from app.theme import APP_STYLESHEET
            self.setStyleSheet(APP_STYLESHEET)
        self.setWindowTitle('صورت‌وضعیت و دفتر مالی پروژه');self.resize(1050,780)
        self.setLayoutDirection(Qt.RightToLeft);self.version=service.open_project(project_id)['_meta']['version']
        layout=QVBoxLayout(self)
        note=QLabel('ثبت مسئولیت بر اساس مجوز مستند مالک است؛ احراز هویت اشخاص انجام نمی‌شود. هیچ پرداخت بانکی از این پنجره اجرا نمی‌شود.');note.setWordWrap(True);layout.addWidget(note)
        self.inputs={};common=QFormLayout()
        for key,label in [('Actor','مسئول عملیات'),('Date','تاریخ سند میلادی YYYY-MM-DD؛ نمایش گزارش شمسی'),('Proof','مسیر مدرک'),('SHA','SHA-256 مدرک')]:self.field(common,key,label)
        layout.addLayout(common);tabs=QTabWidget();layout.addWidget(tabs,1)
        statement=QWidget();sv=QVBoxLayout(statement);form=QFormLayout()
        for key,label in [('Contract','شماره قرارداد'),('Advance','پیش‌پرداخت پرداخت‌شده'),('Retention','نرخ سپرده'),('Recovery','نرخ استهلاک'),('Tax','نرخ مالیات'),('Insurance','نرخ بیمه'),('Other','نرخ سایر کسورات')]:self.field(form,key,label)
        self.currency=QComboBox();self.currency.addItem('انتخاب واحد پول',None);self.currency.addItem('ریال','IRR');self.currency.addItem('تومان','IRT');form.addRow('واحد پول صریح',self.currency)
        self.factor=QComboBox();self.factor.addItem('نرخ پایه؛ عدم اعمال ضرایب برآورد','base_rates_only');self.factor.addItem('ضرایب ترتیبی بازبینی‌شده','reviewed_sequential_factors');form.addRow('مبنای قراردادی ضرایب',self.factor)
        sv.addLayout(form);self.button(sv,'تنظیم شرایط قرارداد','StatementConfigure',self.configure)
        form=QFormLayout();self.field(form,'StatementReference','شماره صورت‌وضعیت');self.field(form,'Quantities','کارکرد همه کدها، حتی صفر: کد=مقدار, کد=مقدار');sv.addLayout(form)
        bar=QHBoxLayout()
        for title,name,op in [('پیش‌نویس','StatementCreate','create'),('بازبینی','StatementReview','review'),('تأیید','StatementApprove','approve'),('صدور','StatementIssue','issue')]:self.button(bar,title,name,lambda checked=False,op=op:self.statement(op))
        sv.addLayout(bar);self.statements=self.table(['شماره سند','تاریخ شمسی','وضعیت','ناخالص','خالص']);sv.addWidget(self.statements)
        self.button(sv,'خروجی صورت‌وضعیت انتخاب‌شده','StatementExport',self.export_statement)
        self.button(sv,'اصلاحیه رسمی مستقل','StatementAmendment',self.amendment)
        tabs.addTab(statement,'صورت‌وضعیت')
        ledger=QWidget();lv=QVBoxLayout(ledger);form=QFormLayout()
        self.kind=QComboBox();self.kind.setObjectName('FinanceKind')
        for key,label in KINDS.items():self.kind.addItem(label,key)
        form.addRow('نوع سند',self.kind)
        for key,label in [('Reference','مرجع یکتای سند'),('Amount','مبلغ دقیق'),('Party','طرف حساب'),('Description','شرح / قرارداد'),('Commitment','شناسه تعهد مرتبط'),('Cost','شناسه هزینه مرتبط'),('Period','شماره صورت‌وضعیت دریافت'),('Reason','دلیل برگشت')]:self.field(form,key,label)
        lv.addLayout(form);bar=QHBoxLayout()
        for title,name,op in [('پیش‌نویس','FinanceCreate','create'),('بازبینی','FinanceReview','review'),('تأیید مستقل','FinanceApprove','approve'),('ثبت قطعی','FinancePost','post'),('برگشت مستند','FinanceReverse','reverse')]:self.button(bar,title,name,lambda checked=False,op=op:self.financial(op))
        lv.addLayout(bar);self.records=self.table(['شناسه','مرجع','نوع','وضعیت','مبلغ']);lv.addWidget(self.records);tabs.addTab(ledger,'دفتر مالی')
        dashboard=QWidget();dv=QVBoxLayout(dashboard);self.metrics=self.table(['شاخص','مقدار']);dv.addWidget(self.metrics)
        self.button(dv,'بازخوانی اطلاعات و ریزاسناد','FinanceRefresh',self.refresh)
        self.format=QComboBox()
        for value in ['pdf','xlsx','docx','csv']:self.format.addItem(value.upper(),value)
        dv.addWidget(self.format);self.button(dv,'خروجی دفتر مالی','FinanceExport',self.export);tabs.addTab(dashboard,'کنترل هزینه و گزارش')
        self.status=QLabel('در انتظار ورودی صریح');self.status.setObjectName('FinanceStatus');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.refresh()

    def field(self,form,key,label):
        field=QLineEdit();field.setObjectName('Finance'+key);self.inputs[key]=field;form.addRow(label,field)

    def button(self,layout,title,name,callback):
        b=QPushButton(title);b.setObjectName(name);b.clicked.connect(callback);layout.addWidget(b)

    def table(self,labels):
        t=QTableWidget(0,len(labels));t.setHorizontalHeaderLabels(labels);t.setEditTriggers(QAbstractItemView.NoEditTriggers);t.setSelectionBehavior(QAbstractItemView.SelectRows);return t

    def text(self,key):return self.inputs[key].text().strip()
    def docs(self):return [{'ref':'FINANCIAL-EVIDENCE','path':self.text('Proof'),'sha256':self.text('SHA')}]
    def call(self,fn):
        try:
            fn();self.refresh();self.status.setText('عملیات ثبت شد؛ ریزسند از جدول قابل بررسی است')
        except Exception as exc:self.status.setText('خطا: '+str(exc))

    def configure(self):
        terms={'contract_id':self.text('Contract'),'currency':self.currency.currentData(),'advance_paid':self.text('Advance'),'factor_basis':self.factor.currentData()}
        for field,key in [('Retention','retention_rate'),('Recovery','advance_recovery_rate'),('Tax','tax_rate'),('Insurance','insurance_rate'),('Other','other_deduction_rate')]:terms[key]=self.text(field)
        self.call(lambda:self.service.configure_statement_workflow(self.pid,actor=self.text('Actor'),expected_version=self.version,terms=terms,source_documents=self.docs()))

    def selected(self,table):
        row=table.currentRow()
        if row<0:raise ValueError('ابتدا سند را انتخاب کنید')
        return table.item(row,0).data(Qt.UserRole)

    def statement(self,op):
        def run():
            args={}
            if op=='create':
                values={}
                for token in self.text('Quantities').split(','):
                    parts=token.split('=')
                    if len(parts)!=2 or not parts[0].strip() or parts[0].strip() in values:raise ValueError('کارکرد باید کد=مقدار و بدون تکرار باشد')
                    values[parts[0].strip()]=parts[1].strip()
                args={'reference':self.text('StatementReference'),'date':self.text('Date'),'current_quantities':values}
            else:args['id']=self.selected(self.statements)
            self.service.statement_workflow(self.pid,op,actor=self.text('Actor'),expected_version=self.version,**args)
        self.call(run)

    def financial(self,op):
        def run():
            args={}
            if op=='create':
                args=dict(kind=self.kind.currentData(),reference=self.text('Reference'),amount=self.text('Amount'),currency=self.currency.currentData(),date=self.text('Date'),counterparty=self.text('Party'),description=self.text('Description'),source_documents=self.docs())
                for field,key in [('Commitment','commitment_id'),('Cost','cost_id'),('Period','statement_no')]:
                    if self.text(field):args[key]=int(self.text(field))
            else:
                args['id']=self.selected(self.records)
                if op=='reverse':args.update(reference=self.text('Reference'),date=self.text('Date'),reason=self.text('Reason'),source_documents=self.docs())
            self.service.financial_command(self.pid,op,actor=self.text('Actor'),expected_version=self.version,**args)
        self.call(run)

    def fill(self,table,rows):
        table.setRowCount(len(rows))
        for i,(identity,values) in enumerate(rows):
            for j,value in enumerate(values):
                item=QTableWidgetItem(str(value));item.setData(Qt.UserRole,identity);table.setItem(i,j,item)
        if rows:
            table.setCurrentCell(len(rows)-1,0);table.selectRow(len(rows)-1)
        table.resizeColumnsToContents()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)

    def refresh(self):
        from datetime import date
        p=self.service.open_project(self.pid);self.version=p['_meta']['version']
        terms=(p.get('statement_workflow_terms') or {}).get('terms')
        if terms:
            self.currency.setCurrentIndex(self.currency.findData(terms['currency']))
            for field,key in [('Contract','contract_id'),('Advance','advance_paid'),('Retention','retention_rate'),('Recovery','advance_recovery_rate'),('Tax','tax_rate'),('Insurance','insurance_rate'),('Other','other_deduction_rate')]:
                self.inputs[field].setText(terms[key]);self.inputs[field].setReadOnly(True)
        elif p.get('statement_amendment_policy'):self.currency.setCurrentIndex(self.currency.findData(p['statement_amendment_policy']['money']['currency']))
        self.fill(self.records,[(r['id'],[r['id'],r['reference'],KINDS[r['kind']],STATES[r['status']],r['amount']]) for r in p.get('financial_records',[])])
        self.fill(self.statements,[(d['id'],[d['reference'],report_date(date.fromisoformat(d['date'])),STATES[d['status']],d['period']['gross_current'],d['period']['payable_current']]) for d in p.get('statement_workflow',[])])
        try:
            snap=self.service.verified_financial_snapshot(self.pid)
            labels={'estimate':'برآورد','budget':'بودجه','commitments':'تعهدات','actual_cost':'هزینه واقعی','paid':'پرداخت واقعی','received':'دریافت واقعی','debt':'مانده بدهی','unpaid_commitments':'مانده تعهدات','budget_variance':'بودجه منهای هزینه','statement_net':'خالص صورت‌وضعیت‌ها','receivable':'مطالبات','cash_net':'خالص نقد'}
            self.fill(self.metrics,[(key,[label,snap[key] if snap[key] is not None else snap['missing_message']]) for key,label in labels.items()])
        except ValueError:self.fill(self.metrics,[(None,['وضعیت','اطلاعات کافی ثبت نشده است؛ سیاست مستند مالک لازم است'])])

    def export(self):
        fmt=self.format.currentData();path=QFileDialog.getSaveFileName(self,'ذخیره گزارش','دفتر-مالی.'+fmt,'*.'+fmt)[0]
        if path:self.call(lambda:self.service.verified_financial_report(self.pid,fmt,path))

    def export_statement(self):
        def run():
            identity=self.selected(self.statements)
            p=self.service.open_project(self.pid)
            doc=next(d for d in p['statement_workflow'] if d['id']==identity)
            if doc['status']!='ISSUED':raise ValueError('گزارش رسمی فقط برای سند صادرشده مجاز است')
            fmt=self.format.currentData()
            path=QFileDialog.getSaveFileName(self,'گزارش صورت‌وضعیت','صورت‌وضعیت.'+fmt,'*.'+fmt)[0]
            if path:self.service.verified_statement_report(self.pid,doc['period']['number'],fmt,path)
        self.call(run)

    def amendment(self):
        from app.statement_amendment import StatementAmendmentDialog
        self.call(lambda:StatementAmendmentDialog(self.service,self.pid,self).exec())
