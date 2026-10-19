"""Persian read-only pre-integration inspector, not a financial entry form."""
import hashlib
import json
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLineEdit,QPlainTextEdit,
 QLabel,QTableWidget,QTableWidgetItem,QHBoxLayout,QPushButton,QFileDialog)
from core.takeoff.structural_handoff_work import parse_request


def open_structural_handoff_audit(service,*,parent=None,project_id=''):
 dialog=QDialog(parent);dialog.setObjectName('StructuralHandoffAudit')
 dialog.setWindowTitle('پیش‌ممیزی قراردادهای فاز یک — ثبت مالی مسدود')
 dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1150,760)
 outer=QVBoxLayout(dialog);form=QFormLayout();project=QLineEdit(project_id)
 source=QLineEdit();source.setReadOnly(True);sha=QLineEdit();sha.setReadOnly(True)
 for label,widget in [('پروژه موجود',project),('سند ورودی',source),('هش سند ورودی',sha)]:form.addRow(label,widget)
 outer.addLayout(form)
 note=QLabel('این ابزار پیش‌ارزیابی است. هش، اصالت مهندسی را اثبات نمی‌کند. مالکیت مشترک، بازبینی رسمی، اصلاحیه و ثبت مالی هنوز مسدودند.');note.setWordWrap(True);outer.addWidget(note)
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
 for key,title in [('load','بازکردن سند ورودی'),('preview','پیش‌ارزیابی روی پروژه'),('clear','پاک‌کردن نمایش'),('close','بستن')]:
  buttons[key]=QPushButton(title);actions.addWidget(buttons[key])
 outer.addLayout(actions)
 c=dict(buttons,project=project,source_path=source,source_sha256=sha,payload=payload,rows=rows,message=message,result=None,details=details);dialog.handoff_controls=c
 def invalidate():
  c['result']=None;rows.setRowCount(0);details.clear()
 def clear():
  invalidate();payload.clear();source.clear();sha.clear();message.setText('نمایش پاک شد؛ داده پروژه تغییر نکرد.')
 def load():
  filename,_=QFileDialog.getOpenFileName(dialog,'بازکردن سند ورودی مستند','','JSON (*.json)')
  if not filename:return
  invalidate();source.clear();sha.clear()
  try:
   path=Path(filename)
   if path.stat().st_size>16*1024*1024:raise ValueError('سند ورودی بیش از حد بزرگ است')
   raw=path.read_bytes();text=raw.decode('utf-8-sig');parse_request(text)
   payload.setPlainText(text);source.setText(str(path.resolve()));sha.setText(hashlib.sha256(raw).hexdigest());message.setText('سند بارگذاری شد؛ هنوز پیش‌ارزیابی نشده است.')
  except (OSError,ValueError,UnicodeError) as exc:payload.clear();message.setText('خطا: '+str(exc))
 def preview():
  invalidate()
  try:
   result=service.preview_structural_handoff(project.text().strip(),parse_request(payload.toPlainText()),source_path=source.text(),source_sha256=sha.text())
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
 payload.textChanged.connect(invalidate);project.textChanged.connect(invalidate)
 buttons['load'].clicked.connect(load);buttons['preview'].clicked.connect(preview);buttons['clear'].clicked.connect(clear);buttons['close'].clicked.connect(dialog.reject)
 dialog.exec();return dialog
