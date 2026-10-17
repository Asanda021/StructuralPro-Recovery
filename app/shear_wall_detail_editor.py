"""Typed Persian RTL specialist editor on the existing AEC workflow and journal."""
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QPushButton,QTabWidget,QWidget,QScrollArea,QTableWidget,QTableWidgetItem,QLabel,QFileDialog,QMessageBox,QComboBox,QStyledItemDelegate)
from core.takeoff.shear_wall_detail import new_detail,POLICY,BAR_LABELS,preview
from core.takeoff.shear_wall_specialist_chat import SCHEMA
from core.takeoff.structural_handoff_work import parse_request
LABELS={'id':'شناسه','physical_part_id':'هویت قطعه','x_m':'مختصات طولی (متر)','y_m':'مختصات عرضی (متر)','z_m':'تراز (متر)','length_m':'طول (متر)','height_m':'ارتفاع (متر)','thickness_m':'ضخامت (متر)','width_m':'عرض (متر)','segment_id':'شناسه قطعه مرتبط','source_ref':'مرجع','approved_by':'تأییدکننده','side':'وجه جلو یا پشت','status':'وضعیت مستند','contact_rectangles':'تماس‌ها (JSON)','payment_ref':'مبنای پرداخت','reason':'دلیل عدم کاربرد','physical_face_id':'هویت وجه','kind':'نوع ضلع','start_m':'ابتدای بازه (متر)','end_m':'انتهای بازه (متر)','opening_id':'بازشوی مرتبط','jamb_side':'لبه بازشو','physical_bar_set_id':'هویت سری میلگرد','diameter_mm':'قطر (میلی‌متر)','count':'تعداد','count_scope':'دامنه تعداد','unit_weight_kg_m':'وزن واحد طول','unit_weight_source':'مرجع وزن واحد','cut_length_m':'طول برش مستقل (متر)','cut_parts':'اجزای برش (JSON)'}
FIELDS={'segments':('id','physical_part_id','x_m','y_m','z_m','length_m','height_m','thickness_m','source_ref','approved_by'),'openings':('id','segment_id','x_m','z_m','width_m','height_m','source_ref','approved_by'),'main_faces':('id','segment_id','side','status','contact_rectangles','payment_ref','source_ref','approved_by','reason'),'edge_faces':('id','physical_face_id','segment_id','kind','status','start_m','end_m','source_ref','approved_by','payment_ref','reason','opening_id','jamb_side'),'bars':('id','physical_bar_set_id','diameter_mm','count','count_scope','unit_weight_kg_m','unit_weight_source','source_ref','approved_by','cut_length_m','cut_parts')}
OPTIONAL={'reason','opening_id','jamb_side','cut_length_m','cut_parts'}
JSON_FIELDS={'contact_rectangles','cut_parts'}

class ExactCellDelegate(QStyledItemDelegate):
 """Keep numeric signs/decimal points and technical IDs in LTR runs."""
 def __init__(self,fields,parent=None):super().__init__(parent);self.fields=fields
 def initStyleOption(self,option,index):
  super().initStyleOption(option,index)
  key=self.fields[index.column()]
  if key.endswith(('_m','_mm')) or key in ('count','unit_weight_kg_m','quantity','source_id','formula','source_ref','id','physical_part_id','physical_bar_set_id','physical_face_id'):
   option.direction=Qt.LeftToRight;option.displayAlignment=Qt.AlignLeft|Qt.AlignVCenter
 def createEditor(self,parent,option,index):
  widget=super().createEditor(parent,option,index)
  key=self.fields[index.column()]
  if widget and (key.endswith(('_m','_mm')) or key in ('count','unit_weight_kg_m','quantity','source_id','formula','source_ref','id','physical_part_id','physical_bar_set_id','physical_face_id')):widget.setLayoutDirection(Qt.LeftToRight)
  return widget

class ValueCombo(QComboBox):
 """Display Persian labels while retaining explicit engine enum values."""
 def __init__(self,choices):
  super().__init__();self.addItem('نیازمند انتخاب','')
  for value,label in choices:self.addItem(label,value)
 def text(self):return self.currentData() or ''
 def setText(self,value):self.setCurrentIndex(max(0,self.findData(value)))

FORM_CHOICES={'orientation':[('positive_x','جهت مثبت محور طول'),('negative_x','جهت منفی؛ ثبت فعلاً مسدود')],'length_unit':[('m','متر')],'form_status':[('confirmed','تأییدشده')],'edge_status':[('reviewed_complete','بررسی کامل مستند')]}
TABLE_CHOICES={'side':[('front','وجه جلو'),('back','وجه پشت')],'status':[('formed','قالب اجرا می‌شود'),('not_required','عدم نیاز مستند')],'kind':[('left_end','انتهای چپ'),('right_end','انتهای راست'),('top','ضلع بالا'),('bottom','ضلع پایین'),('opening_jamb','لبه بازشو')],'count_scope':[('total_wall','تعداد کل همین دیوار')],'jamb_side':[('left','چپ'),('right','راست'),('top','بالا'),('bottom','پایین')]}

def put_cell(table,row,col,key,value):
 if key in TABLE_CHOICES:
  widget=ValueCombo(TABLE_CHOICES[key]);widget.setText(value);table.setCellWidget(row,col,widget)
 else:table.setItem(row,col,QTableWidgetItem(value))

def open_shear_wall_editor(service,*,parent=None,project_id='',floor_id=''):
 dialog=QDialog(parent);dialog.setWindowTitle('متره دستی تخصصی دیوار برشی');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1220,850)
 outer=QVBoxLayout(dialog);tabs=QTabWidget();outer.addWidget(tabs,1);c={'tabs':tabs,'tables':{},'columns':{},'groups':{},'state':{'data':None,'revision':0}}
 def page(title):
  area=QScrollArea();area.setWidgetResizable(True);widget=QWidget();layout=QVBoxLayout(widget);area.setWidget(widget);tabs.addTab(area,title);return layout
 def button(layout,key,title,action):
  b=QPushButton(title);layout.addWidget(b);b.clicked.connect(lambda:run(action));c[key]=b;return b
 def run(action):
  try:action()
  except (ValueError,KeyError,TypeError,OSError,RuntimeError) as exc:c['message'].setText('خطا: '+str(exc))
 def text(form,key,label,value=''):
  w=ValueCombo(FORM_CHOICES[key]) if key in FORM_CHOICES else QLineEdit(value);form.addRow(label,w);c[key]=w;return w
 identity=page('هویت، مدارک و بازبینی');form=QFormLayout();identity.addLayout(form)
 for key,label,value in [('project','پروژه',project_id),('floor','طبقه',floor_id),('id','شناسه دیوار',''),('building','ساختمان',''),('axis','محور',''),('source','شناسه منبع',''),('author','تهیه‌کننده',''),('plan','پلان',''),('detail','دیتایل',''),('measurement','مرجع برداشت',''),('reviewer','بازبین مستقل',''),('note','یادداشت بازبینی','')]:text(form,key,label,value)
 for prefix,title in [('input','دیتایل'),('ownership','مالکیت')]:
  for field,caption in [('path','فایل'),('sha256','هش'),('reference','مرجع')]:text(form,prefix+'_'+field,caption+' '+title)
 def table_page(key,title,fields):
  layout=page(title);t=QTableWidget(0,len(fields));t.setHorizontalHeaderLabels([LABELS[k] for k in fields]);t.setItemDelegate(ExactCellDelegate(fields,t));layout.addWidget(t);c['tables'][key]=t;c['columns'][key]=fields
  bar=QHBoxLayout();layout.addLayout(bar)
  def add():
   row=t.rowCount();t.insertRow(row)
   for col,field in enumerate(fields):put_cell(t,row,col,field,'')
   t.setCurrentCell(row,0);t.selectRow(row)
  def remove():
   for row in sorted({v.row() for v in t.selectedIndexes()},reverse=True):t.removeRow(row)
  button(bar,key+'_add','افزودن ردیف خالی',add);button(bar,key+'_remove','حذف ردیف انتخاب‌شده',remove)
  return layout
 for key,title in [('segments','قطعات مستطیلی'),('openings','بازشوها'),('main_faces','وجوه اصلی قالب'),('edge_faces','وجوه جانبی قالب')]:table_page(key,title,FIELDS[key])
 geometry=page('مختصات و دامنه قالب');gf=QFormLayout();geometry.addLayout(gf)
 for key,label in [('physical_wall_id','هویت فیزیکی دیوار'),('coordinate_ref','مرجع مختصات جهانی'),('axis_ref','محور مستند'),('level_ref','تراز مرجع'),('orientation','جهت مستند در مختصات جهانی'),('datum_author','تأییدکننده مختصات'),('engine_ref','مرجع منبع موتور'),('engine_author','تأییدکننده منبع موتور'),('length_unit','واحد ابعاد'),('form_status','وضعیت بررسی قالب'),('form_payment_ref','دامنه پرداخت قالب'),('form_payment_author','تأییدکننده پرداخت'),('form_ref','مرجع قالب'),('form_author','تأییدکننده قالب'),('edge_status','وضعیت بررسی کامل وجوه جانبی'),('edge_ref','مرجع وجوه جانبی'),('edge_author','تأییدکننده وجوه جانبی')]:text(gf,key,label)
 for group,title in BAR_LABELS.items():
  layout=table_page(group,title,FIELDS['bars']);f=QFormLayout();layout.insertLayout(0,f);fields={}
  for field,label in [('status','وضعیت گروه'),('source_ref','مرجع گروه'),('approved_by','تأییدکننده'),('reason','دلیل عدم کاربرد')]:w=ValueCombo([('confirmed','تأییدشده'),('not_applicable','عدم کاربرد مستند')]) if field=='status' else QLineEdit();fields[field]=w;f.addRow(label,w)
  c['groups'][group]=fields
 correction=page('اصلاحیه و تاریخچه');af=QFormLayout();correction.addLayout(af)
 for key,label in [('creator','درخواست‌کننده'),('reason','علت اصلاحیه یا حذف/کپی'),('evidence_path','مدرک اصلاحیه'),('evidence_ref','مرجع مدرک'),('amend_id','شناسه اصلاحیه'),('new_id','شناسه دیوار مقصد کپی'),('new_source','منبع جدید کپی')]:text(af,key,label)
 history=QTableWidget(0,3);history.setHorizontalHeaderLabels(['شناسه','وضعیت','اختلاف ریزمقادیر']);correction.addWidget(history);c['history']=history
 summary=page('ریزمتره');grid=QTableWidget(0,5);grid.setHorizontalHeaderLabels(['شرح','مقدار دقیق','واحد','فرمول','منبع']);grid.setEditTriggers(QTableWidget.NoEditTriggers);grid.setItemDelegate(ExactCellDelegate(('description','quantity','unit','formula','source_id'),grid));summary.addWidget(grid);c['rows']=grid
 message=QLabel('ورودی عددی پیش‌فرض وجود ندارد؛ مالکیت مشترک حل‌نشده قابل پرداخت نیست.');message.setWordWrap(True);message.setMaximumHeight(80);outer.addWidget(message);c['message']=message
 def fill(d,rev):
  c['state'].update(data=deepcopy(d),revision=rev)
  for k,f in [('reviewer','reviewer'),('note','note')]:c[k].setText(d.get('roof_review',{}).get(f,''))
  e=d['shear_wall_detail'].get('input',{})
  for k,f in [('floor','floor_id'),('id','system_id'),('building','building_id'),('axis','axis')]:c[k].setText(str(d.get(f,'')))
  for k,f in [('source','source_id'),('author','approved_by'),('plan','plan_ref'),('detail','detail_ref'),('measurement','measurement_ref')]:c[k].setText(str(d.get('source',{}).get(f,'')))
  for prefix in ('input','ownership'):
   for f in ('path','sha256','reference'):c[prefix+'_'+f].setText(d['shear_wall_detail'].get(prefix+'_document',{}).get(f,''))
  c['physical_wall_id'].setText(e.get('physical_wall_id',''))
  for k in ('coordinate_ref','axis_ref','level_ref','orientation'):c[k].setText(e.get('datum',{}).get(k,''))
  c['datum_author'].setText(e.get('datum',{}).get('approved_by',''))
  for k,f in [('engine_ref','source_ref'),('engine_author','approved_by'),('length_unit','length_unit')]:c[k].setText(e.get('source',{}).get(f,''))
  fw=e.get('formwork',{})
  for k,f in [('form_status','status'),('form_payment_ref','payment_scope_ref'),('form_payment_author','payment_approved_by'),('form_ref','source_ref'),('form_author','approved_by')]:c[k].setText(fw.get(f,''))
  for k,f in [('edge_status','status'),('edge_ref','source_ref'),('edge_author','approved_by')]:c[k].setText(fw.get('edge_scope',{}).get(f,''))
  for key,t in c['tables'].items():
   vals=e.get(key,[]) if key in ('segments','openings') else fw.get(key,[]) if key in ('main_faces','edge_faces') else e.get('rebars',{}).get(key,{}).get('series',[])
   t.setRowCount(len(vals))
   for row,p in enumerate(vals):
    for col,f in enumerate(c['columns'][key]):put_cell(t,row,col,f,json.dumps(p[f],ensure_ascii=False) if f in JSON_FIELDS and f in p else str(p.get(f,'')))
   t.resizeColumnsToContents()
  for group,widgets in c['groups'].items():
   for f,w in widgets.items():w.setText(e.get('rebars',{}).get(group,{}).get(f,''))
 def capture():
  d=deepcopy(c['state']['data'] or new_detail(c['floor'].text(),c['id'].text()));d.update(floor_id=c['floor'].text(),system_id=c['id'].text(),building_id=c['building'].text(),axis=c['axis'].text());d['source']={'mode':'manual',**{f:c[k].text() for k,f in [('source','source_id'),('author','approved_by'),('plan','plan_ref'),('detail','detail_ref'),('measurement','measurement_ref')]}}
  e=deepcopy(d['shear_wall_detail'].get('input',{}));e.update(schema_version=SCHEMA,kind='shear_wall',project_id=c['project'].text(),floor_id=d['floor_id'],wall_id=d['system_id'],physical_wall_id=c['physical_wall_id'].text(),source={'mode':'manual','source_id':d['source']['source_id'],'source_ref':c['engine_ref'].text(),'approved_by':c['engine_author'].text(),'length_unit':c['length_unit'].text()},datum={**{k:c[k].text() for k in ('coordinate_ref','axis_ref','level_ref','orientation')},'approved_by':c['datum_author'].text()})
  fw={'status':c['form_status'].text(),'payment_scope_ref':c['form_payment_ref'].text(),'payment_approved_by':c['form_payment_author'].text(),'source_ref':c['form_ref'].text(),'approved_by':c['form_author'].text(),'edge_scope':{'status':c['edge_status'].text(),'source_ref':c['edge_ref'].text(),'approved_by':c['edge_author'].text()}}
  e.setdefault('interfaces',[]);e['rebars']={}
  for key,t in c['tables'].items():
   vals=[]
   for row in range(t.rowCount()):
    p={}
    for col,f in enumerate(c['columns'][key]):
     v=t.cellWidget(row,col).text() if t.cellWidget(row,col) else t.item(row,col).text() if t.item(row,col) else ''
     if not v and f in OPTIONAL:continue
     p[f]=parse_request(v) if f in JSON_FIELDS else v
    vals.append(p)
   if key in ('segments','openings'):e[key]=vals
   elif key in ('main_faces','edge_faces'):fw[key]=vals
   else:
    g={k:w.text() for k,w in c['groups'][key].items()}
    if g['status']!='not_applicable' or vals:g['series']=vals
    if not g['reason']:g.pop('reason')
    e['rebars'][key]=g
  e['formwork']=fw;d['shear_wall_detail']['input']=e
  for prefix in ('input','ownership'):d['shear_wall_detail'][prefix+'_document']={f:c[prefix+'_'+f].text() for f in ('path','sha256','reference')}
  old=deepcopy(c['state']['data']);before=deepcopy(d);before.pop('roof_review',None)
  if old:old.pop('roof_review',None)
  if before!=old:d.pop('roof_review',None)
  return d
 def new():fill(new_detail(c['floor'].text(),c['id'].text()),0);grid.setRowCount(0)
 def load():
  r=service.get_aec_system(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text())
  if not r:raise ValueError('دیوار یافت نشد')
  if r['data'].get('measurement_policy')!=POLICY:raise ValueError('تبدیل خاموش رکورد عمومی ممنوع است')
  fill(r['data'],r['revision']);message.setText('نسخه جاری از SQLite باز شد.')
 def load_input():
  path,_=QFileDialog.getOpenFileName(dialog,'دیتایل مستند','','JSON (*.json)')
  if not path:return
  p=Path(path)
  if p.stat().st_size>16*1024*1024:raise ValueError('مدرک بیش از حد بزرگ است')
  raw=p.read_bytes();e=parse_request(raw.decode('utf-8-sig'));d=deepcopy(c['state']['data'] or new_detail(c['floor'].text(),c['id'].text()));d.update(floor_id=e['floor_id'],system_id=e['wall_id']);d['source']={'mode':'manual','source_id':e['source']['source_id'],'approved_by':e['source']['approved_by'],'measurement_ref':e['source']['source_ref'],'plan_ref':'','detail_ref':''};d['shear_wall_detail']['input']=e;d['shear_wall_detail']['input_document']={'path':str(p.resolve()),'sha256':sha256(raw).hexdigest(),'reference':e['source']['source_ref']};fill(d,c['state']['revision'])
 def load_owner():
  path,_=QFileDialog.getOpenFileName(dialog,'سند مالکیت مستقل','','JSON (*.json)')
  if path:
   p=Path(path)
   if p.stat().st_size>16*1024*1024:raise ValueError('مدرک بیش از حد بزرگ است')
   raw=p.read_bytes();o=parse_request(raw.decode('utf-8-sig'));c['ownership_path'].setText(str(p.resolve()));c['ownership_sha256'].setText(sha256(raw).hexdigest());c['ownership_reference'].setText(o['reference'])
 def write_input():
  path,_=QFileDialog.getSaveFileName(dialog,'مدرک جدید دیتایل','','JSON (*.json)')
  if path:
   raw=json.dumps(capture()['shear_wall_detail']['input'],ensure_ascii=False,indent=2).encode()
   with Path(path).open('xb') as f:f.write(raw)
   c['input_path'].setText(str(Path(path).resolve()));c['input_sha256'].setText(sha256(raw).hexdigest());message.setText('مدرک جدید ذخیره شد؛ سند مالکیت باید به همین هش و نسخه بازبینی شود.')
 def show_preview():
  r=preview(capture(),service.takeoff);grid.setRowCount(len(r['rows']))
  for i,v in enumerate(r['rows']):
   for j,k in enumerate(('description','quantity','unit','formula','source_id')):grid.setItem(i,j,QTableWidgetItem(str(v[k])))
  grid.resizeColumnsToContents();message.setText('محاسبه معتبر؛ ثبت نهایی وابسته به گیت پروژه و بازبینی است.' if r['ready'] else 'ثبت مسدود: '+'؛ '.join(r['blockers']))
 def save():
  r=service.save_aec_system_draft(c['project'].text(),capture(),expected_revision=c['state']['revision']);fill(r['data'],r['revision']);message.setText('پیش‌نویس در SQLite ذخیره شد.')
 def review():
  if capture()!=c['state']['data']:raise ValueError('تغییرات را پیش از بازبینی ذخیره کنید')
  r=service.review_roof_system(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision'],reviewer=c['reviewer'].text(),note=c['note'].text());fill(r['data'],r['revision']);message.setText('بازبینی مستقل ثبت شد.')
 def commit():
  if capture()!=c['state']['data']:raise ValueError('تغییرات ذخیره‌نشده وجود دارد')
  service.commit_aec_system(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision']);load();message.setText('ثبت قطعی در BOQ انجام شد.')
 def copy():
  r=service.aec_workflow().copy_roof(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text(),new_system_id=c['new_id'].text(),new_source_id=c['new_source'].text(),reason=c['reason'].text());fill(r['data'],r['revision']);message.setText('کپی با هویت جدید؛ مدارک و هویت فیزیکی باید دوباره تکمیل شوند.')
 def delete():
  if QMessageBox.question(dialog,'حذف کنترل‌شده','پیش‌نویس با حفظ تاریخچه حذف شود؟')==QMessageBox.Yes:
   service.aec_workflow().delete_roof(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text(),expected_revision=c['state']['revision'],reason=c['reason'].text());new();message.setText('پیش‌نویس حذف و تاریخچه حفظ شد.')
 def create_amendment():
  p=Path(c['evidence_path'].text());evidence={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':c['evidence_ref'].text()};a=service.create_roof_amendment(c['project'].text(),'shear_wall',c['floor'].text(),c['id'].text(),capture(),expected_revision=c['state']['revision'],created_by=c['creator'].text(),reason=c['reason'].text(),evidence=evidence);c['amend_id'].setText(a['id']);refresh_history()
 def refresh_history():
  p=service.open_project(c['project'].text());vals=[a for a in p.get('beam_amendments',{}).values() if a['previous']['data'].get('kind')=='shear_wall' and a['previous']['data']['system_id']==c['id'].text() and a['previous']['data']['floor_id']==c['floor'].text()];history.setRowCount(len(vals))
  for i,a in enumerate(vals):
   for j,v in enumerate((a['id'],{'draft':'درخواست','reviewed':'بازبینی','applied':'اعمال‌شده'}[a['status']],json.dumps(a['delta'],ensure_ascii=False))):history.setItem(i,j,QTableWidgetItem(v))
 def review_amendment():service.review_beam_amendment(c['project'].text(),c['amend_id'].text(),expected_revision=1,reviewer=c['reviewer'].text(),note=c['note'].text());refresh_history()
 def apply_amendment():service.apply_beam_amendment(c['project'].text(),c['amend_id'].text(),expected_revision=1);load();refresh_history()
 def export(fmt):
  path,_=QFileDialog.getSaveFileName(dialog,'گزارش دیوار برشی','',fmt.upper()+' (*.'+fmt+')')
  if path:service.export_shear_wall_detail_report(c['project'].text(),c['floor'].text(),c['id'].text(),path,format=fmt);message.setText('گزارش نسخه ذخیره‌شده صادر شد.')
 for entries in [[('new','جدید',new),('input_file','خواندن دیتایل',load_input),('owner_file','خواندن مالکیت',load_owner),('write_input','فایل جدید دیتایل',write_input),('preview','پیش‌نمایش',show_preview),('save','ذخیره',save),('load','بازگشایی',load)],[('review','بازبینی',review),('commit','ثبت قطعی',commit),('copy','کپی',copy),('delete','حذف پیش‌نویس',delete),('create_amendment','درخواست اصلاحیه',create_amendment),('review_amendment','بازبینی اصلاحیه',review_amendment),('apply_amendment','اعمال اصلاحیه',apply_amendment)]]:
  row=QHBoxLayout();outer.addLayout(row)
  for k,title,fn in entries:button(row,k,title,fn)
 row=QHBoxLayout();outer.addLayout(row)
 for fmt in ('pdf','xlsx','docx','csv'):button(row,fmt,{'pdf':'گزارش PDF','xlsx':'گزارش Excel','docx':'گزارش Word','csv':'گزارش CSV'}[fmt],lambda f=fmt:export(f))
 button(row,'close','بستن',dialog.reject);dialog.wall_controls=c;new();dialog.exec();return dialog
