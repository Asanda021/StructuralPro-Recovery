"""Typed Persian architecture form on the existing AEC workflow and SQLite."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QLabel,QTabWidget,QWidget,QTableWidget,QMessageBox,QFileDialog,QListWidget
from app.roof_detail_editor import fill_table as _fill_table,read_table
from core.takeoff.architecture_detail import POLICY,KINDS,COMMON,LAYER_FIELDS,REGION_FIELDS,SURFACE_FIELDS,OPENING_FIELDS,review_digest,suggestions
from core.reports.architecture_detail_report import FIELD_LABELS,VALUES,export
from core.takeoff.reviewed_aec import SPECS,_id
GEOMETRY=('physical_wall_id','length_m','height_m','wall_thickness_m','count','repeat_ref','source_ref','approved_by')
TABLES={'openings':OPENING_FIELDS,'masonry_layers':LAYER_FIELDS,'unit_regions':REGION_FIELDS,'surfaces':SURFACE_FIELDS}
CHOICES={'material_kind':('brick','cement_block','clay_block','light_block','aac'),'face':('inside','outside'),'layer_code':('base_plaster','white_plaster','cement_render','levelling','protective'),'mode':('units','mortar'),'payment_unit':('m2','m3','kg'),'coverage_scope':('complete','partial'),'penetration':('full_wall',)}
def fill_table(table,columns,records):
 table.setColumnCount(len(columns));table.setHorizontalHeaderLabels([x[1] for x in columns]);_fill_table(table,columns,records)
 for row,p in enumerate(records):
  for col,(key,_) in enumerate(columns):
   if key not in CHOICES:continue
   w=QComboBox();w.addItem('نیازمند انتخاب','')
   for v in CHOICES[key]:w.addItem(VALUES[v],v)
   w.setCurrentIndex(max(0,w.findData(p.get(key,''))));table.setCellWidget(row,col,w)

def open_architecture_editor(service,*,parent=None,project_id='',floor_id='',kind='block_wall'):
 dialog=QDialog(parent);dialog.setObjectName('ArchitectureDetailEditor');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1220,840);outer=QVBoxLayout(dialog);c={};dialog.architecture_controls=c;state={'record':None,'data':None,'project':None}
 def line(layout,key,title,value=''):
  w=QLineEdit(str(value));layout.addRow(title,w);c[key]=w;return w
 def buttons(layout,items):
  row=QHBoxLayout();layout.addLayout(row)
  for key,title in items:
   w=QPushButton(title);row.addWidget(w);c[key]=w
 top=QFormLayout();outer.addLayout(top)
 for key,title,value in [('project','پروژه',project_id),('floor','طبقه',floor_id),('id','شناسه مستقل عضو','')]:line(top,key,title,value)
 family=QComboBox();[family.addItem(SPECS[k].title,k) for k in KINDS];family.setCurrentIndex(family.findData(kind));top.addRow('نوع عملیات',family);c['kind']=family
 tabs=QTabWidget();outer.addWidget(tabs,1);c['tabs']=tabs
 def page(title):
  w=QWidget();layout=QVBoxLayout(w);tabs.addTab(w,title);return layout
 basic=page('هویت و هندسه');f=QFormLayout();basic.addLayout(f)
 for key,title in [('building','ساختمان'),('axis','فضا و موقعیت'),('source','شناسه منبع مستقل'),('plan','نقشه مرجع'),('detail','دیتایل مرجع')]:line(f,key,title)
 c['geometry_fields']={}
 for key in GEOMETRY:
  w=QLineEdit();f.addRow(FIELD_LABELS[key],w);c['geometry_fields'][key]=w
 basic.addWidget(QLabel('تمام ابعاد بر حسب متر؛ فقط دیوار مستطیلی و بند کامل مستند. مقدار، پرت و مصرف حدس زده نمی‌شوند.'))
 states=page('بررسی گروه‌ها و پیشنهادها');f=QFormLayout();states.addLayout(f);c['states']={}
 for group,title in [('masonry','دیوارچینی'),('finishes','اندود مستقل'),('accessories','اتصال و مسلح‌سازی')]:
  widgets={};combo=QComboBox();[combo.addItem(t,v) for t,v in [('نیازمند دیتایل','unreviewed'),('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable')]];f.addRow(title,combo);widgets['status']=combo
  for key,label in [('source_ref','مرجع'),('approved_by','تأییدکننده'),('reason','علت عدم کاربرد')]:
   w=QLineEdit();f.addRow(title+'؛ '+label,w);widgets[key]=w
  c['states'][group]=widgets
 buttons(states,[('suggest','پیشنهاد عملیات نیازمند دیتایل')]);proposals=QListWidget();states.addWidget(proposals);c['proposals']=proposals
 c['tables']={};c['columns']={}
 for name,title in [('openings','بازشوها'),('masonry_layers','لایه‌های مستقل دیوار'),('unit_regions','جانمایی واحدها و بندها'),('surfaces','وجه‌ها و لایه‌های مستقل اندود')]:
  layout=page(title);table=QTableWidget();table.setAlternatingRowColors(True);layout.addWidget(table);c['tables'][name]=table;columns=[(k,FIELD_LABELS[k]) for k in COMMON+TABLES[name]];c['columns'][name]=columns;fill_table(table,columns,[])
  buttons(layout,[(name+'_add','افزودن ردیف'),(name+'_remove','حذف ردیف انتخاب‌شده')])
 approval=page('بازبینی و اصلاحیه رسمی');f=QFormLayout();approval.addLayout(f)
 for key,title in [('reviewer','بازبین مستقل'),('note','یادداشت بازبینی'),('creator','درخواست‌کننده اصلاحیه'),('reason','علت اصلاح، کپی یا حذف'),('evidence_path','مسیر مدرک جدید'),('evidence_ref','مرجع مدرک جدید'),('amend_id','شناسه اصلاحیه'),('new_id','شناسه مستقل کپی'),('new_source','منبع مستقل کپی')]:line(f,key,title)
 buttons(approval,[('create_amendment','درخواست اصلاحیه'),('review_amendment','بازبینی اصلاحیه'),('apply_amendment','اعمال اصلاحیه'),('copy','کپی با هویت جدید'),('delete','حذف کنترل‌شده پیش‌نویس')])
 comparison=QTableWidget(0,5);comparison.setHorizontalHeaderLabels(['شرح','مقدار پیشین','مقدار پیشنهادی','اختلاف','واحد']);approval.addWidget(comparison);c['amendment_grid']=comparison
 summary=page('ریزمتره و گزارش');grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(['شرح','مقدار','واحد','مرجع']);summary.addWidget(grid);c['grid']=grid
 buttons(summary,[('pdf','گزارش پی‌دی‌اف'),('xlsx','گزارش اکسل'),('docx','گزارش ورد'),('csv','داده جدولی')])
 message=QLabel('ابتدا عضو جدید یا بازگشایی را انتخاب کنید.');message.setWordWrap(True);outer.addWidget(message);c['message']=message
 buttons(outer,[('new','عضو جدید'),('load','بازگشایی'),('save','ذخیره'),('preview','محاسبه و ریزمتره'),('review','بازبینی'),('commit','ثبت قطعی در فهرست مقادیر')])
 def context():return c['project'].text().strip(),family.currentData(),c['floor'].text().strip(),c['id'].text().strip()
 def paint(record):
  state.update(record=deepcopy(record),data=deepcopy(record['data']),project=context()[0]);d=state['data'];a=d['architecture_detail'];dialog.setWindowTitle('متره تخصصی '+SPECS[d['kind']].title)
  for key in ('save','preview','review','commit'):c[key].setEnabled(True)
  for i in range(tabs.count()):tabs.setTabEnabled(i,True)
  for key,field in [('building','building_id'),('axis','axis')]:c[key].setText(str(d.get(field,'')))
  for key,field in [('source','source_id'),('plan','plan_ref'),('detail','detail_ref')]:c[key].setText(str(d.get('source',{}).get(field,'')))
  for k,w in c['geometry_fields'].items():w.setText(str(a.get('geometry',{}).get(k,'')))
  for group,ws in c['states'].items():
   g=a.get(group,{})
   for k,w in ws.items():
    if k=='status':w.setCurrentIndex(max(0,w.findData(g.get(k))))
    else:w.setText(str(g.get(k,'')))
  for name,table in c['tables'].items():fill_table(table,c['columns'][name],a.get(name,[]))
  message.setText('نسخه '+str(record['revision'])+'؛ '+('قطعی؛ تغییر فقط با اصلاحیه' if record['status']=='committed' else 'پیش‌نویس'))
  comparison.setRowCount(0);c['amend_id'].clear()
  amendments=service.open_project(state['project']).get('beam_amendments',{});key=_id(d['kind'],d['floor_id'],d['system_id']);pending=[am for am in amendments.values() if am.get('beam_key')==key and am['status'] in ('draft','reviewed')]
  am=pending[-1] if pending else amendments.get(record.get('amendment_id'))
  if am:c['amend_id'].setText(am['id']);show_amendment(am)
 def capture():
  if state['data'] is None:raise ValueError('ابتدا عضو جدید یا بازگشایی را انتخاب کنید')
  d=deepcopy(state['data']);ctx=context()
  if ctx!=(state['project'],d['kind'],d['floor_id'],d['system_id']):raise ValueError('هویت فرم تغییر کرده؛ عضو جدید یا بازگشایی کنید')
  d.update(building_id=c['building'].text().strip(),axis=c['axis'].text().strip());d['source']={'mode':'manual','source_id':c['source'].text().strip(),'plan_ref':c['plan'].text().strip(),'detail_ref':c['detail'].text().strip()}
  a=d['architecture_detail'];a['geometry']={k:w.text().strip() for k,w in c['geometry_fields'].items()};a['geometry']['unit']='m'
  for group,ws in c['states'].items():a[group]={k:w.currentData() if k=='status' else w.text().strip() for k,w in ws.items()}
  for name,table in c['tables'].items():a[name]=read_table(table,c['columns'][name])
  if d.get('roof_review',{}).get('digest')!=review_digest(d):d.pop('roof_review',None)
  return d
 def new():
  pid,k,floor,sid=context()
  if not pid or not floor or not sid or service.open_project(pid) is None:raise ValueError('پروژه، طبقه و شناسه لازم است')
  if service.get_aec_system(pid,k,floor,sid):raise ValueError('شناسه موجود است؛ بازگشایی کنید')
  d=service.new_aec_system(k,floor,sid);d.update(measurement_policy=POLICY,architecture_detail={'geometry':{},**{k:[] for k in TABLES},**{k:{'status':'unreviewed'} for k in ('masonry','finishes','accessories')}});paint({'data':d,'revision':0,'status':'draft'})
 def load():
  r=service.get_aec_system(*context())
  if not r or r['data'].get('measurement_policy')!=POLICY:raise ValueError('رکورد تخصصی یافت نشد؛ مهاجرت خاموش تاریخی ممنوع است')
  paint(r)
 def unchanged():
  if review_digest(capture())!=review_digest(state['record']['data']):raise ValueError('ابتدا تغییرات پیش‌نویس را ذخیره کنید')
 def save():
  d=capture();d.pop('roof_review',None);paint(service.save_aec_system_draft(context()[0],d,expected_revision=state['record']['revision']))
 def calculate():
  from core.takeoff.architecture_detail import preview
  from PySide6.QtWidgets import QTableWidgetItem
  r=preview(capture(),service.takeoff);grid.setRowCount(len(r['rows']))
  for i,v in enumerate(r['rows']):
   for j,x in enumerate([v['description'],v['quantity'],v['unit'],v['source_ref']]):grid.setItem(i,j,QTableWidgetItem(str(x)))
  tabs.setCurrentIndex(tabs.count()-1);message.setText('محاسبه معتبر؛ نیازمند بازبینی نسخه جاری' if r['ready'] else '؛ '.join(r['blockers']))
 def review():unchanged();paint(service.review_roof_system(*context(),expected_revision=state['record']['revision'],reviewer=c['reviewer'].text(),note=c['note'].text()))
 def commit():unchanged();service.commit_aec_system(*context(),expected_revision=state['record']['revision']);load()
 def create_amendment():
  path=Path(c['evidence_path'].text().strip());a=service.create_roof_amendment(*context(),capture(),expected_revision=state['record']['revision'],created_by=c['creator'].text(),reason=c['reason'].text(),evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':c['evidence_ref'].text()});c['amend_id'].setText(a['id']);show_amendment(a);message.setText('درخواست اصلاحیه ثبت شد؛ مقادیر پیشین، پیشنهادی و اختلاف در جدول')
 def show_amendment(am):
  from core.takeoff.architecture_detail import preview
  from PySide6.QtWidgets import QTableWidgetItem
  old={v['source_id']:v for v in preview(am['previous']['data'],service.takeoff)['rows']};new={v['source_id']:v for v in am['rows']};comparison.setRowCount(len(am['delta']))
  for row,(src,delta) in enumerate(am['delta'].items()):
   before=old.get(src,{});after=new.get(src,{});q=after.get('quantities',[{}])[0]
   for col,value in enumerate([before.get('description') or after.get('description'),before.get('quantity',0),q.get('amount',0),delta,VALUES.get(before.get('unit') or q.get('unit'),before.get('unit') or q.get('unit'))]):comparison.setItem(row,col,QTableWidgetItem(str(value)))
 def amendment_context():
  capture();pid,kind,floor,sid=context();am=service.open_project(pid).get('beam_amendments',{}).get(c['amend_id'].text())
  if not am or am['beam_key']!=_id(kind,floor,sid):raise ValueError('اصلاحیه متعلق به عضو نمایش‌داده‌شده نیست')
  show_amendment(am);return am
 def review_amendment():
  am=amendment_context();service.review_beam_amendment(context()[0],am['id'],expected_revision=am['revision'],reviewer=c['reviewer'].text(),note=c['note'].text());message.setText('اصلاحیه مستقل بازبینی شد')
 def apply_amendment():
  am=amendment_context();service.apply_beam_amendment(context()[0],am['id'],expected_revision=am['revision']);load()
 def copy():service.aec_workflow().copy_roof(*context(),new_system_id=c['new_id'].text(),new_source_id=c['new_source'].text(),reason=c['reason'].text());c['id'].setText(c['new_id'].text());load()
 def delete():
  if QMessageBox.question(dialog,'حذف کنترل‌شده','حذف پیش‌نویس با حفظ تاریخچه انجام شود؟')!=QMessageBox.Yes:return
  service.aec_workflow().delete_roof(*context(),expected_revision=state['record']['revision'],reason=c['reason'].text());state['data']=None;message.setText('پیش‌نویس حذف شد؛ تاریخچه محفوظ است')
 def report(fmt):
  unchanged();path,_=QFileDialog.getSaveFileName(dialog,'مسیر گزارش','','*.'+fmt)
  if path:export(service,*context(),path,format=fmt);message.setText('گزارش ذخیره شد')
 def add(name):
  records=read_table(c['tables'][name],c['columns'][name]);records.append({});fill_table(c['tables'][name],c['columns'][name],records)
 def remove(name):
  table=c['tables'][name]
  if table.currentRow()<0:raise ValueError('ردیف را انتخاب کنید')
  table.removeRow(table.currentRow())
 def propose():
  proposals.clear()
  for v in suggestions('wall'):proposals.addItem(v['title']+'؛ '+v['status'])
  message.setText('پیشنهادها مقدار یا فهرست مقادیر ایجاد نمی‌کنند؛ انتخاب و دیتایل مستقل لازم است')
 def guarded(fn):
  def run(*_):
   try:fn()
   except (ValueError,RuntimeError,KeyError,TypeError,OSError) as exc:QMessageBox.warning(dialog,'کنترل مهندسی',str(exc))
  return run
 for key,fn in [('new',new),('load',load),('save',save),('preview',calculate),('review',review),('commit',commit),('create_amendment',create_amendment),('review_amendment',review_amendment),('apply_amendment',apply_amendment),('copy',copy),('delete',delete),('suggest',propose)]:c[key].clicked.connect(guarded(fn))
 for name in TABLES:
  c[name+'_add'].clicked.connect(guarded(lambda name=name:add(name)));c[name+'_remove'].clicked.connect(guarded(lambda name=name:remove(name)))
 for fmt in ('pdf','xlsx','docx','csv'):c[fmt].clicked.connect(guarded(lambda fmt=fmt:report(fmt)))
 for key in ('save','preview','review','commit'):c[key].setEnabled(False)
 for i in range(1,tabs.count()):tabs.setTabEnabled(i,False)
 dialog.exec();return dialog
