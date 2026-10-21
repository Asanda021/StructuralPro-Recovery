"""Persian read-only pre-integration inspector, not a financial entry form."""
import hashlib
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,
 QLabel,QTableWidget,QTableWidgetItem,QHBoxLayout,QPushButton,QFileDialog,QMessageBox)
from core.takeoff.structural_handoff_work import parse_request, STEEL_SUPPORT_POLICY, SIX_GEOMETRY_POLICY
from core.takeoff.building_six_family_ownership_chat import POLICY as OWNERSHIP_POLICY


class StructuralHandoffAuditDialog(QDialog):
 def reject(self):
  if self.isVisible() and getattr(self,'unsaved_bindings',lambda:False)():
   answer=QMessageBox.question(self,'تغییرات ذخیره‌نشده','پیش‌نویس و مسیر مدارک ذخیره نشده‌اند. بدون ذخیره خارج شوید؟',QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
   if answer!=QMessageBox.Yes:return
  super().reject()


def open_structural_handoff_audit(service,*,parent=None,project_id='',required_policy=None):
 dialog=StructuralHandoffAuditDialog(parent);dialog.setObjectName('StructuralHandoffAudit')
 dialog.setWindowTitle('پیش‌ممیزی قراردادهای فاز یک — ثبت مالی مسدود')
 dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1150,760)
 outer=QVBoxLayout(dialog);form=QFormLayout();project=QLineEdit(project_id)
 source=QLineEdit();source.setReadOnly(True);sha=QLineEdit();sha.setReadOnly(True)
 for label,widget in [('پروژه موجود',project),('سند ورودی',source),('هش سند ورودی',sha)]:form.addRow(label,widget)
 audit_id=QLineEdit();audit_id.setPlaceholderText('شناسه یکتای ممیزی؛ بدون مقدار پیش‌فرض')
 form.addRow('شناسه ممیزی نسخه‌دار',audit_id)
 evidence_files=QPlainTextEdit();evidence_files.setMaximumHeight(65);evidence_files.setLayoutDirection(Qt.LeftToRight)
 evidence_files.setPlaceholderText('نگاشت JSON صریح از SHA-256 به مسیر فایل مدرک؛ بدون مدرک فرضی')
 form.addRow('مسیر بایت مدارک مستقل',evidence_files)
 outer.addLayout(form)
 note=QLabel('این ابزار پیش‌ارزیابی است. هش، اصالت مهندسی را اثبات نمی‌کند. ذخیره پیش‌نویس و نتیجه، تأیید طراحی نیست؛ ثبت مالی مسدود می‌ماند.');note.setWordWrap(True);outer.addWidget(note)
 payload=QPlainTextEdit();payload.setReadOnly(True);payload.setLayoutDirection(Qt.LeftToRight);payload.setPlaceholderText('سند JSON مستند را باز کنید؛ داده عددی پیش‌فرض وجود ندارد.');outer.addWidget(payload,1)
 rows=QTableWidget(0,5);rows.setHorizontalHeaderLabels(['شرح کاندید','مقدار دقیق','واحد','شناسه منبع','فرمول'])
 rows.setEditTriggers(QTableWidget.NoEditTriggers)
 from app.shear_wall_detail_editor import ExactCellDelegate
 rows.setItemDelegate(ExactCellDelegate(('description','quantity','unit','source_id','formula'),rows));outer.addWidget(rows,2)
 details=QPlainTextEdit();details.setReadOnly(True);details.setLayoutDirection(Qt.LeftToRight)
 outer.addWidget(QLabel('شواهد دقیق قرارداد؛ فقط‌خواندنی، بدون مجوز ثبت مالی'))
 outer.addWidget(details,1)
 message=QLabel('هیچ محاسبه‌ای انجام نشده است.');message.setWordWrap(True);outer.addWidget(message)
 actions=QHBoxLayout();buttons={}
 for key,title in [('load','بازکردن سند ورودی'),('preview','پیش‌ارزیابی روی پروژه'),('save_draft','ذخیره پیش‌نویس'),('run_saved','اجرای ممیزی ذخیره‌شده'),('reopen','بازگشایی ممیزی'),('clear','پاک‌کردن نمایش'),('close','بستن')]:
  buttons[key]=QPushButton(title);actions.addWidget(buttons[key])
 outer.addLayout(actions)
 c=dict(buttons,audit_id=audit_id,evidence_files=evidence_files,revision=0,dirty=True,project=project,source_path=source,source_sha256=sha,payload=payload,rows=rows,message=message,result=None,details=details);dialog.handoff_controls=c
 dialog.unsaved_bindings=lambda: c['dirty'] and buttons['save_draft'].isEnabled()
 def policy_check(request):
  if not isinstance(request,dict):
   raise ValueError('سند ورودی باید یک قرارداد JSON با کلیدهای مشخص باشد')
  if required_policy is not None and request.get('policy')!=required_policy:
   raise ValueError('این فرم فقط قرارداد تخصصی انتخاب‌شده را می‌پذیرد؛ پله فولادی با پله بتنی یکسان نیست')
  return request
 def mapping():
  value=parse_request(evidence_files.toPlainText() or '{}')
  if not isinstance(value,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in value.items()):
   raise ValueError('نگاشت صریح هش به مسیر فایل معتبر لازم است')
  return value
 def update_actions():
  try: supported=parse_request(payload.toPlainText()).get('policy') in (STEEL_SUPPORT_POLICY,SIX_GEOMETRY_POLICY,OWNERSHIP_POLICY)
  except (ValueError,AttributeError): supported=False
  buttons['save_draft'].setEnabled(bool(supported and audit_id.text().strip() and project.text().strip()))
  buttons['run_saved'].setEnabled(c['revision']>0 and not c['dirty'])
  buttons['reopen'].setEnabled(bool(audit_id.text().strip() and project.text().strip()))
 def invalidate():
  c['result']=None;c['dirty']=True;rows.setRowCount(0);details.clear();update_actions()
 def identity_changed():
  c['revision']=0;invalidate()

 def clear():
  invalidate();payload.clear();source.clear();sha.clear();message.setText('نمایش پاک شد؛ داده پروژه تغییر نکرد.')
 def load():
  filename,_=QFileDialog.getOpenFileName(dialog,'بازکردن سند ورودی مستند','','JSON (*.json)')
  if not filename:return
  invalidate();source.clear();sha.clear()
  try:
   path=Path(filename)
   if path.stat().st_size>16*1024*1024:raise ValueError('سند ورودی بیش از حد بزرگ است')
   raw=path.read_bytes();text=raw.decode('utf-8-sig');policy_check(parse_request(text))
   payload.setPlainText(text);source.setText(str(path.resolve()));sha.setText(hashlib.sha256(raw).hexdigest());message.setText('سند بارگذاری شد؛ هنوز پیش‌ارزیابی نشده است.')
  except (OSError,ValueError,UnicodeError) as exc:payload.clear();message.setText('خطا: '+str(exc))
 def preview():
  invalidate()
  try:
   result=service.preview_structural_handoff(project.text().strip(),policy_check(parse_request(payload.toPlainText())),source_path=source.text(),source_sha256=sha.text(),evidence_files=mapping())
   c['result']=result
   for row in result['rows']:
    index=rows.rowCount();rows.insertRow(index)
    for col,key in enumerate(('description','quantity','unit','source_id','formula')):rows.setItem(index,col,QTableWidgetItem(str(row[key])))
   if 'audit' in result:
    details.setPlainText(json.dumps(result['audit'],ensure_ascii=False,indent=2))
    message.setText('پیش‌ممیزی اجرا شد؛ ثبت مالی مسدود است.\n'+'\n'.join(result['blockers']))
    return
   rows.resizeColumnsToContents();message.setText('ثبت مالی مسدود — '+str(len(result['rows']))+' کاندید؛ '+str(result['rebar_crosswalk_requests']['unverified_candidate_count'])+' ردیف میلگرد و '+str(len(result['concrete_formwork_requests']['requests']))+' ردیف بتن/قالب نیازمند تطبیق مستند.\n'+'\n'.join(result['blockers']))
  except (OSError,ValueError,KeyError,RuntimeError,TypeError) as exc:message.setText('خطا: '+str(exc))
 def show_record(record):
  data=record['data'];policy_check(data['request'])
  payload.blockSignals(True);evidence_files.blockSignals(True)
  payload.setPlainText(json.dumps(data['request'],ensure_ascii=False,indent=2))
  evidence_files.setPlainText(json.dumps(data['evidence_files'],ensure_ascii=False,indent=2))
  payload.blockSignals(False);evidence_files.blockSignals(False)
  source.setText(data['source_path']);sha.setText(data['source_sha256'])
  c['revision']=record['revision'];c['dirty']=False;c['result']=record['result']
  rows.setRowCount(0);details.setPlainText(json.dumps(record['result'] or {},ensure_ascii=False,indent=2))
  labels={'draft':'پیش‌نویس','checked_nonfinancial':'بررسی‌شده؛ غیرمالی','blocked':'مسدود'}
  message.setText('نسخه '+str(record['revision'])+' — '+labels.get(record['status'],'وضعیت نامعتبر')+'؛ ثبت مالی مسدود است.'+(' Snapshot کهنه؛ مدرک جدید لازم است.' if record.get('stale') else ''))
  update_actions()
 def save_draft():
  try:
   record=service.save_structural_handoff_draft(project.text().strip(),audit_id.text().strip(),policy_check(parse_request(payload.toPlainText())),source_path=source.text(),source_sha256=sha.text(),evidence_files=mapping(),expected_revision=c['revision'])
   show_record(record)
  except (OSError,ValueError,KeyError,RuntimeError,TypeError) as exc:message.setText('خطا: '+str(exc))
 def run_saved():
  try:
   if c['dirty']:raise ValueError('تغییرات ذخیره‌نشده‌اند؛ ابتدا پیش‌نویس را ذخیره کنید')
   record=service.run_structural_handoff_audit(project.text().strip(),audit_id.text().strip(),expected_revision=c['revision'])
   show_record(record)
  except (OSError,ValueError,KeyError,RuntimeError,TypeError) as exc:message.setText('خطا: '+str(exc))
 def reopen():
  try:
   record=service.get_structural_handoff_audit(project.text().strip(),audit_id.text().strip())
   if record is None:raise ValueError('ممیزی ذخیره‌شده یافت نشد')
   show_record(record)
  except (OSError,ValueError,KeyError,RuntimeError,TypeError) as exc:message.setText('خطا: '+str(exc))
 payload.textChanged.connect(invalidate);project.textChanged.connect(identity_changed)
 audit_id.textChanged.connect(identity_changed);evidence_files.textChanged.connect(invalidate)
 buttons['save_draft'].clicked.connect(save_draft);buttons['run_saved'].clicked.connect(run_saved);buttons['reopen'].clicked.connect(reopen)
 update_actions()

 buttons['load'].clicked.connect(load);buttons['preview'].clicked.connect(preview);buttons['clear'].clicked.connect(clear);buttons['close'].clicked.connect(dialog.reject)
 dialog.exec();return dialog
