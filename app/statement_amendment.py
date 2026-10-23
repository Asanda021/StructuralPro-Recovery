"""Persian statement amendment form backed only by the commercial service.

No implicit policy, authority, detail, monetary precision or approval is added.
The operator must explicitly refresh after concurrent changes before retrying.
"""
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,
    QLineEdit,QTextEdit,QPushButton,QComboBox,QFileDialog)

class StatementAmendmentDialog(QDialog):
    def __init__(self, service, project_id, parent=None):
        super().__init__(parent)
        self.service=service;self.project_id=project_id;self.snapshot=None
        self.setWindowTitle('اصلاحیه مستقل صورت‌وضعیت');self.setLayoutDirection(Qt.RightToLeft);self.resize(950,730)
        layout=QVBoxLayout(self);self.policy=QLabel();self.policy.setWordWrap(True);layout.addWidget(self.policy)
        form=QFormLayout();layout.addLayout(form)
        self.actor=QLineEdit();self.actor.setObjectName('AmendmentActor')
        self.period=QLineEdit();self.period.setObjectName('AmendmentPeriod')
        self.selected=QComboBox();self.selected.setObjectName('AmendmentDocument')
        self.reason=QLineEdit();self.reason.setObjectName('AmendmentReason')
        self.docs=QTextEdit();self.docs.setObjectName('AmendmentEvidence');self.docs.setMaximumHeight(85)
        self.lines=QTextEdit();self.lines.setObjectName('AmendmentLines');self.lines.setMaximumHeight(125)
        self.lines.setPlaceholderText('ردیف‌های JSON: price_code, source_id, corrected_period_quantity, reason, detail_source_ref؛ بدون نرخ یا واحد حدسی')
        for label,widget in [('مسئول دارای مجوز مالک',self.actor),('شماره صورت‌وضعیت صادرشده',self.period),
                             ('سند موجود',self.selected),('علت / علت رد',self.reason),
                             ('مدارک JSON: ref, path, sha256',self.docs),('مقدار اصلاحی مستند (JSON)',self.lines)]:form.addRow(label,widget)
        self.corrected_rates={}
        for key,label in [('retention_rate','سپرده'),('advance_recovery_rate','استهلاک'),('tax_rate','مالیات'),('insurance_rate','بیمه'),('other_deduction_rate','سایر کسورات')]:
            entry=QLineEdit();entry.setObjectName('AmendmentCorrection_'+key);entry.setPlaceholderText('اختیاری؛ برای اصلاح نرخ، هر پنج نرخ صریح لازم است')
            self.corrected_rates[key]=entry;form.addRow('نرخ اصلاحی '+label,entry)
        commands=QHBoxLayout();layout.addLayout(commands);self.buttons={}
        for op,title in [('refresh','بازخوانی صریح'),('create','پیش‌نویس جدید'),('edit','ویرایش پیش‌نویس'),
                         ('review','بازبینی'),('approve','تأیید مستقل'),('post','ثبت نهایی'),('reject','رد')]:
            b=QPushButton(title);b.setObjectName('Amendment_'+op);commands.addWidget(b);self.buttons[op]=b
            b.clicked.connect(lambda checked=False,op=op:self.run(op))
        exports=QHBoxLayout();layout.addLayout(exports)
        for fmt in ('pdf','xlsx','csv'):
            b=QPushButton('گزارش اصل / اصلاحیه / خالص '+fmt.upper());b.setObjectName('AmendmentExport_'+fmt)
            b.clicked.connect(lambda checked=False,fmt=fmt:self.choose_export(fmt));exports.addWidget(b)
        self.output=QTextEdit();self.output.setReadOnly(True);self.output.setObjectName('AmendmentOutput');layout.addWidget(self.output,1)
        self.selected.currentIndexChanged.connect(self.show_document)
        self.refresh()

    def refresh(self):
        self.snapshot=self.service.open_project(self.project_id)
        policy=self.snapshot.get('statement_amendment_policy')
        self.policy.setText('سیاست و مجوز ثبت‌شده مالک: '+json.dumps(policy and {'owner_id':policy['owner_id'],'money':policy['money'],'authorities':policy['authorities']},ensure_ascii=False))
        current=self.selected.currentData();self.selected.blockSignals(True);self.selected.clear()
        for d in self.snapshot.get('statement_amendments',[]):self.selected.addItem(f"{d['sequence']} — {d['status']} — نسخه {d['revision']}",d['amendment_id'])
        i=self.selected.findData(current)
        if i>=0:self.selected.setCurrentIndex(i)
        self.selected.blockSignals(False)
        self.show_document()
        if not policy:self.output.setPlainText('BLOCKED: سیاست مالی و مجوز مستند مالک تنظیم نشده است؛ فرم هیچ مجوزی ایجاد نمی‌کند.')

    def document(self):
        return next((d for d in self.snapshot.get('statement_amendments',[]) if d['amendment_id']==self.selected.currentData()),None)

    def show_document(self):
        d=self.document()
        if not d:return
        self.period.setText(str(d['issued_period_no']));self.reason.setText(d['reason'])
        self.docs.setPlainText(json.dumps([{k:x[k] for k in ('ref','path','sha256')} for x in d['source_documents']],ensure_ascii=False,indent=2))
        self.lines.setPlainText(json.dumps([{k:x[k] for k in ('price_code','source_id','corrected_period_quantity','reason','detail_source_ref')} for x in d['lines']],ensure_ascii=False,indent=2))
        for key,entry in self.corrected_rates.items():entry.setText((d.get('effective_rates_after') or {}).get(key,'') if self.snapshot.get('statement_workflow_terms') else '')
        self.output.setPlainText(json.dumps({'document':d,'summary':self.service.statement_amendment_summary(self.project_id,d['issued_period_no'])},ensure_ascii=False,indent=2))

    def run(self,op):
        try:
            if op=='refresh':self.refresh();return
            actor=self.actor.text().strip();version=self.snapshot['_meta']['version'];d=self.document()
            base={'expected_project_version':version}
            if op in ('create','edit'):
                data={'reason':self.reason.text(),'source_documents':json.loads(self.docs.toPlainText()),'lines':json.loads(self.lines.toPlainText()),**base}
                rates={key:entry.text().strip() for key,entry in self.corrected_rates.items()}
                if any(rates.values()):data['corrected_rates']=rates
                if op=='create':result=self.service.create_statement_amendment(self.project_id,int(self.period.text()),created_by=actor,**data)
                else:
                    if not d:raise ValueError('اصلاحیه را انتخاب کنید')
                    result=self.service.edit_statement_amendment(self.project_id,d['amendment_id'],edited_by=actor,expected_revision=d['revision'],**data)
            else:
                if not d:raise ValueError('اصلاحیه را انتخاب کنید')
                base['expected_revision']=d['revision'];base['id']=d['amendment_id']
                if op=='approve':base['expected_content_digest']=d['content_digest']
                if op=='reject':base['reason']=self.reason.text()
                doc_id=base.pop('id');actor_key={'review':'reviewed_by','approve':'approved_by','post':'posted_by','reject':'rejected_by'}[op]
                result=getattr(self.service,op+'_statement_amendment')(self.project_id,doc_id,**{actor_key:actor},**base)
            self.refresh();i=self.selected.findData(result['amendment_id']);self.selected.setCurrentIndex(i);self.show_document()
        except Exception as e:self.output.setPlainText('خطای اصلاحیه: '+str(e))

    def export(self,path,fmt):
        from core.reports import exporters
        if not self.document():raise ValueError('اصلاحیه را انتخاب کنید')
        report=self.service.statement_amendment_summary(self.project_id,self.document()['issued_period_no'])
        labels={'gross_current':'کارکرد ناخالص','retention':'تضمین','advance_recovery':'بازگشت پیش‌پرداخت',
                'taxable_current':'مبنای مشمول','tax':'مالیات','insurance':'بیمه','payable_current':'قابل پرداخت'}
        rows=[{'code':k,'description':label,'original':report['original'][k],'delta':report['amendment_deltas'][k],'net':report['net'][k]} for k,label in labels.items()]
        columns=[('code','شناسه'),('description','شرح'),('original','اصل صورت‌وضعیت'),('delta','اصلاحیه ثبت‌شده'),('net','خالص نهایی')]
        return getattr(exporters,'export_'+fmt)(rows,path,columns=columns,**({'title':'اصل، اصلاحیه و خالص صورت‌وضعیت'} if fmt=='pdf' else {}))

    def choose_export(self,fmt):
        try:
            path,_=QFileDialog.getSaveFileName(self,'گزارش اصلاحیه','',f'{fmt.upper()} (*.{fmt})')
            if path:self.export(path,fmt);self.output.append('گزارش ذخیره شد: '+path)
        except Exception as e:self.output.setPlainText('خطای گزارش: '+str(e))
