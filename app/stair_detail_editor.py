"""Real typed Persian RTL stair editor on the existing AEC service and journal."""
from copy import deepcopy
from pathlib import Path
from hashlib import sha256
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QTabWidget,QWidget,QScrollArea,QTableWidget,QTableWidgetItem,QLabel,QFileDialog,QMessageBox
from app.shear_wall_detail_editor import ExactCellDelegate,ValueCombo
from core.takeoff.stair_detail import new_detail,POLICY,BAR_LABELS,preview
from core.takeoff.stair_detail_fields import FIELDS,LABELS,CHOICES,TITLES
from core.takeoff.stair_specialist import SCHEMA,UNITS
from core.takeoff.structural_handoff_work import parse_request

def open_stair_editor(service,*,parent=None,project_id='',floor_id=''):
 dialog=QDialog(parent);dialog.setWindowTitle('متره تخصصی پله بتنی و پاگرد');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1260,850)
 outer=QVBoxLayout(dialog);tabs=QTabWidget();outer.addWidget(tabs,1);message=QLabel();message.setWordWrap(True);outer.addWidget(message);c={'tabs':tabs,'message':message,'tables':{},'columns':{},'metadata':{},'scope':{},'state':{'data':None,'revision':0}}
 def page(title):
  scroll=QScrollArea();scroll.setWidgetResizable(True);widget=QWidget();layout=QVBoxLayout(widget);scroll.setWidget(widget);tabs.addTab(scroll,title);return layout
 def run(action):
  try:action()
  except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:message.setText('خطا: '+str(exc))
 def button(layout,key,title,action):
  w=QPushButton(title);layout.addWidget(w);w.clicked.connect(lambda:run(action));c[key]=w
 def text(form,key,label,value=''):
  w=QLineEdit(value);form.addRow(label,w);c[key]=w
 identity=page('هویت، مدارک و بازبینی');form=QFormLayout();identity.addLayout(form)
 for k,label,value in [('project','پروژه',project_id),('floor','طبقه',floor_id),('id','شناسه پله',''),('building','ساختمان',''),('axis','محور',''),('physical_stair_id','هویت فیزیکی مستقل',''),('source','شناسه منبع',''),('author','تهیه‌کننده',''),('measurement','مرجع برداشت',''),('plan','پلان',''),('detail','دیتایل',''),('preflight_reviewer','بازبین پیش‌نمایش',''),('preflight_reference','مرجع بررسی مالکیت',''),('reviewer','بازبین مستقل نهایی',''),('note','یادداشت بازبینی','')]:text(form,k,label,value)
 for prefix,title in [('input','دیتایل'),('ownership','مالکیت')]:
  for field,label in [('path','فایل'),('sha256','هش'),('reference','مرجع')]:text(form,prefix+'_'+field,label+' '+title)
 geometry=page('تراز و دامنه مستند');gf=QFormLayout();geometry.addLayout(gf)
 for key in ('source_ref','approved_by','story_start_z_m','story_end_z_m','story_height_m','story_ref'):
  w=QLineEdit();gf.addRow(LABELS[key],w);c['metadata'][key]=w
 for key,label in [('steps','کف‌پله'),('landings','پاگرد'),('connections','اتصال'),('reinforcement','آرماتور'),('formwork','قالب')]:
  w=ValueCombo([('fully_documented','دامنه کامل مستند')]);gf.addRow(label,w);c['scope'][key]=w
 w=QLineEdit();gf.addRow('مرجع دامنه کامل',w);c['scope']['scope_ref']=w
 note=QLabel('فقط عملیات دارای مالکیت مستقل و مدرک معتبر قابل پرداخت‌اند؛ سایر عملیات بدون مقدار صفر در وضعیت مسدود می‌مانند. سند مالکیت، محدوده جهانی کامل مجموعه و هویت فردی میلگردها را مشخص می‌کند.');note.setWordWrap(True);geometry.addWidget(note)
 def put(t,i,j,key,value):
  if key in CHOICES or key=='group':
   w=ValueCombo(CHOICES[key] if key in CHOICES else list(BAR_LABELS.items()));w.setText(value);t.setCellWidget(i,j,w)
  else:t.setItem(i,j,QTableWidgetItem(value))
 for key,fields in FIELDS.items():
  layout=page(TITLES[key]);t=QTableWidget(0,len(fields));t.setHorizontalHeaderLabels([LABELS[f] for f in fields]);t.setItemDelegate(ExactCellDelegate(fields,t));layout.addWidget(t);c['tables'][key]=t;c['columns'][key]=fields;bar=QHBoxLayout();layout.addLayout(bar)
  def add(k=key):
   t=c['tables'][k];i=t.rowCount();t.insertRow(i)
   for j,f in enumerate(FIELDS[k]):put(t,i,j,f,'')
   t.setCurrentCell(i,0);t.selectRow(i)
  def remove(k=key):
   t=c['tables'][k]
   for i in sorted({v.row() for v in t.selectedIndexes()},reverse=True):t.removeRow(i)
  button(bar,key+'_add','افزودن ردیف خالی',add);button(bar,key+'_remove','حذف ردیف انتخاب‌شده',remove)
 correction=page('اصلاحیه و تاریخچه');af=QFormLayout();correction.addLayout(af)
 for key,label in [('creator','درخواست‌کننده'),('reason','علت اصلاحیه یا کپی/حذف'),('evidence_path','مدرک اصلاحیه'),('evidence_ref','مرجع مدرک اصلاحیه'),('amend_id','شناسه اصلاحیه'),('new_id','شناسه پله مقصد کپی'),('new_source','منبع جدید کپی')]:text(af,key,label)
 history=QTableWidget(0,3);history.setHorizontalHeaderLabels(['شناسه','وضعیت','اختلاف ریزمقادیر']);correction.addWidget(history);c['history']=history
 summary=page('ریزمتره دارای مالکیت');grid=QTableWidget(0,5);grid.setHorizontalHeaderLabels(['شرح','مقدار دقیق','واحد','فرمول','منبع']);grid.setItemDelegate(ExactCellDelegate(('description','quantity','unit','formula','source_id'),grid));summary.addWidget(grid);c['summary']=grid
 def fill(d,revision=0):
  c['state']={'data':deepcopy(d),'revision':revision};dt=d['stair_detail'];e=dt.get('input',{})
  for key,field in [('floor','floor_id'),('id','system_id'),('building','building_id'),('axis','axis')]:c[key].setText(d.get(field,''))
  c['physical_stair_id'].setText(dt.get('physical_stair_id',''))
  for key,field in [('source','source_id'),('author','approved_by'),('measurement','measurement_ref'),('plan','plan_ref'),('detail','detail_ref')]:c[key].setText(d.get('source',{}).get(field,''))
  for key,field in [('preflight_reviewer','reviewer'),('preflight_reference','ownership_reference_claim')]:c[key].setText(dt.get('preflight',{}).get(field,''))
  for prefix in ('input','ownership'):
   for field in ('path','sha256','reference'):c[prefix+'_'+field].setText(dt.get(prefix+'_document',{}).get(field,''))
  for key,w in c['metadata'].items():w.setText(str(e.get('metadata',{}).get(key,'')))
  for key,w in c['scope'].items():w.setText(e.get('scope',{}).get(key,''))
  for key,t in c['tables'].items():
   vals=e.get(key,[]);t.setRowCount(len(vals))
   for i,p in enumerate(vals):
    for j,f in enumerate(FIELDS[key]):put(t,i,j,f,str(p.get(f,'')))
   t.resizeColumnsToContents()
 def capture():
  d=deepcopy(c['state']['data'] or new_detail(c['floor'].text(),c['id'].text()));d.update(floor_id=c['floor'].text(),system_id=c['id'].text(),building_id=c['building'].text(),axis=c['axis'].text());d['source']={'mode':'manual',**{f:c[k].text() for k,f in [('source','source_id'),('author','approved_by'),('measurement','measurement_ref'),('plan','plan_ref'),('detail','detail_ref')]}};dt=d['stair_detail'];e=deepcopy(dt.get('input',{}));e.setdefault('schema',SCHEMA);e.setdefault('units',deepcopy(UNITS));e['metadata']={**e.get('metadata',{}),'project_id':c['project'].text(),'floor_id':d['floor_id'],'stair_id':d['system_id'],**{k:w.text() for k,w in c['metadata'].items()}};e['scope']={**e.get('scope',{}),**{k:w.text() for k,w in c['scope'].items()}}
  for key,t in c['tables'].items():e[key]=[{f:(t.cellWidget(i,j).text() if t.cellWidget(i,j) else t.item(i,j).text() if t.item(i,j) else '') for j,f in enumerate(FIELDS[key])} for i in range(t.rowCount())]
  dt.update(input=e,physical_stair_id=c['physical_stair_id'].text(),preflight={'reviewer':c['preflight_reviewer'].text(),'ownership_reference_claim':c['preflight_reference'].text()})
  for prefix in ('input','ownership'):dt[prefix+'_document']={f:c[prefix+'_'+f].text() for f in ('path','sha256','reference')}
  before=deepcopy(d);before.pop('roof_review',None);old=deepcopy(c['state']['data'])
  if old:old.pop('roof_review',None)
  if before!=old:d.pop('roof_review',None)
  return d
 def new():fill(new_detail(c['floor'].text(),c['id'].text()),0);grid.setRowCount(0)
 def load():
  r=service.get_aec_system(c['project'].text(),'stair',c['floor'].text(),c['id'].text())
  if not r:raise ValueError('پله یافت نشد')
  if r['data'].get('measurement_policy')!=POLICY:raise ValueError('تبدیل خاموش رکورد عمومی ممنوع است')
  fill(r['data'],r['revision']);message.setText('نسخه جاری از SQLite باز شد.')
 def load_input():
  path,_=QFileDialog.getOpenFileName(dialog,'دیتایل مستند پله','','JSON (*.json)')
  if not path:return
  p=Path(path)
  if p.stat().st_size>16*1024*1024:raise ValueError('مدرک بیش از حد بزرگ است')
  raw=p.read_bytes();e=parse_request(raw.decode('utf-8-sig'))
  from decimal import localcontext,Inexact,Rounded
  from core.takeoff.stair_specialist import preview as engine_preview
  with localcontext() as context:
   context.traps[Inexact]=False;context.traps[Rounded]=False;engine_preview(e)
  m=e['metadata'];d=deepcopy(c['state']['data'] or new_detail(c['floor'].text(),c['id'].text()));d.update(floor_id=m['floor_id'],system_id=m['stair_id']);d['stair_detail']['input']=e;d['stair_detail']['input_document']={'path':str(p.resolve()),'sha256':sha256(raw).hexdigest(),'reference':m['source_ref']}
  fill(d,c['state']['revision'])
 def load_owner():
  path,_=QFileDialog.getOpenFileName(dialog,'سند مالکیت مستقل','','JSON (*.json)')
  if path:
   p=Path(path)
   if p.stat().st_size>16*1024*1024:raise ValueError('مدرک بیش از حد بزرگ است')
   raw=p.read_bytes();o=parse_request(raw.decode('utf-8-sig'));c['ownership_path'].setText(str(p.resolve()));c['ownership_sha256'].setText(sha256(raw).hexdigest());c['ownership_reference'].setText(o['reference']);c['physical_stair_id'].setText(o['physical_stair_id']);c['preflight_reviewer'].setText(o['reviewer']);c['preflight_reference'].setText(o['reference'])
 def write_input():
  path,_=QFileDialog.getSaveFileName(dialog,'مدرک جدید دیتایل','','JSON (*.json)')
  if path:
   raw=json.dumps(capture()['stair_detail']['input'],ensure_ascii=False,indent=2).encode()
   with Path(path).open('xb') as f:f.write(raw)
   c['input_path'].setText(str(Path(path).resolve()));c['input_sha256'].setText(sha256(raw).hexdigest());message.setText('مدرک جدید ذخیره شد؛ سند مالکیت باید به همین هش و نسخه بازبینی شود.')
 def show_preview():
  r=preview(capture(),service.takeoff);grid.setRowCount(len(r['rows']))
  for i,v in enumerate(r['rows']):
   for j,k in enumerate(('description','quantity','unit','formula','source_id')):grid.setItem(i,j,QTableWidgetItem(str(v[k])))
  grid.resizeColumnsToContents();message.setText(('محاسبه معتبر؛ ثبت نهایی وابسته به گیت پروژه و بازبینی است. ردیف‌های فاقد مالکیت: '+str(len(r.get('excluded_operations',[])))) if r['ready'] else 'ثبت مسدود: '+'؛ '.join(r['blockers']))
 def save():
  r=service.save_aec_system_draft(c['project'].text(),capture(),expected_revision=c['state']['revision']);fill(r['data'],r['revision']);message.setText('پیش‌نویس در SQLite ذخیره شد.')
 def review():
  if capture()!=c['state']['data']:raise ValueError('تغییرات را پیش از بازبینی ذخیره کنید')
  r=service.review_roof_system(c['project'].text(),'stair',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision'],reviewer=c['reviewer'].text(),note=c['note'].text());fill(r['data'],r['revision']);message.setText('بازبینی مستقل ثبت شد.')
 def commit():
  if capture()!=c['state']['data']:raise ValueError('تغییرات ذخیره‌نشده وجود دارد')
  service.commit_aec_system(c['project'].text(),'stair',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision']);load();message.setText('ثبت قطعی در BOQ انجام شد.')
 def copy():
  r=service.aec_workflow().copy_roof(c['project'].text(),'stair',c['floor'].text(),c['id'].text(),new_system_id=c['new_id'].text(),new_source_id=c['new_source'].text(),reason=c['reason'].text());fill(r['data'],r['revision']);message.setText('کپی با هویت جدید؛ مدارک و هویت فیزیکی باید دوباره تکمیل شوند.')
 def delete():
  if QMessageBox.question(dialog,'حذف کنترل‌شده','پیش‌نویس با حفظ تاریخچه حذف شود؟')==QMessageBox.Yes:
   service.aec_workflow().delete_roof(c['project'].text(),'stair',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision'],reason=c['reason'].text());new();message.setText('پیش‌نویس حذف و تاریخچه حفظ شد.')
 def create_amendment():
  p=Path(c['evidence_path'].text());evidence={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':c['evidence_ref'].text()};a=service.create_roof_amendment(c['project'].text(),'stair',c['floor'].text(),c['id'].text(),capture(),expected_revision=c['state']['revision'],created_by=c['creator'].text(),reason=c['reason'].text(),evidence=evidence);c['amend_id'].setText(a['id']);refresh_history()
 def refresh_history():
  from core.takeoff.reviewed_aec import _id
  p=service.open_project(c['project'].text());key=_id('stair',c['floor'].text(),c['id'].text());values=[]
  for a in p.get('beam_amendments',{}).values():
   if a.get('beam_key')==key:values.append((a['id'],{'draft':'درخواست','reviewed':'بازبینی','applied':'اعمال‌شده'}[a['status']],json.dumps(a['delta'],ensure_ascii=False)))
  for a in p.get('aec_system_history',[]):
   if key in (a.get('source_key'),a.get('target_key')):values.append((a['action']+' '+a.get('at',''),{'copy':'کپی','delete_draft':'حذف پیش‌نویس'}.get(a['action'],a['action']),a['reason']))
  history.setRowCount(len(values))
  for i,row in enumerate(values):
   for j,value in enumerate(row):history.setItem(i,j,QTableWidgetItem(value))
 def review_amendment():service.review_beam_amendment(c['project'].text(),c['amend_id'].text(),expected_revision=1,reviewer=c['reviewer'].text(),note=c['note'].text());refresh_history()
 def apply_amendment():service.apply_beam_amendment(c['project'].text(),c['amend_id'].text(),expected_revision=1);load();refresh_history()
 for entries in [[('new','جدید',new),('input_file','خواندن دیتایل',load_input),('owner_file','خواندن مالکیت',load_owner),('write_input','فایل جدید دیتایل',write_input),('preview','پیش‌نمایش',show_preview),('save','ذخیره',save),('load','بازگشایی',load)],[('review','بازبینی',review),('commit','ثبت قطعی',commit),('copy','کپی',copy),('delete','حذف پیش‌نویس',delete),('create_amendment','درخواست اصلاحیه',create_amendment),('review_amendment','بازبینی اصلاحیه',review_amendment),('apply_amendment','اعمال اصلاحیه',apply_amendment),('history_refresh','بازخوانی تاریخچه',refresh_history)]]:
  row=QHBoxLayout();outer.addLayout(row)
  for key,title,fn in entries:button(row,key,title,fn)
 def report(fmt):
  if capture()!=c['state']['data']:raise ValueError('تغییرات را پیش از گزارش ذخیره یا از نسخه جاری بازگشایی کنید')
  path,_=QFileDialog.getSaveFileName(dialog,'گزارش رسمی نسخه جاری','',fmt.upper()+' (*.'+fmt+')')
  if path:
   service.export_stair_detail_report(c['project'].text(),c['floor'].text(),c['id'].text(),path,format=fmt);message.setText('گزارش نسخه جاری ذخیره شد؛ مجوز پرداخت مستقل نیست.')
 row=QHBoxLayout();outer.addLayout(row)
 for fmt,title in [('pdf','گزارش پی‌دی‌اف'),('xlsx','گزارش اکسل'),('docx','گزارش ورد'),('csv','گزارش سی‌اس‌وی')]:button(row,'report_'+fmt,title,lambda fmt=fmt:report(fmt))
 row=QHBoxLayout();outer.addLayout(row);button(row,'close','بستن',dialog.reject);dialog.stair_controls=c;new();dialog.exec();return dialog
