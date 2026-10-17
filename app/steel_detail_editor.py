"""Persian typed steel/deck forms using existing AEC, amendment and report services."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QLabel,QTabWidget,QWidget,QTableWidget,QMessageBox,QFileDialog
from app.roof_detail_editor import fill_table as _fill_table,read_table
from core.takeoff.steel_detail import POLICY,KINDS,GROUPS,COMMON,FIELDS,PANEL_FIELDS,LABELS,review_digest
from core.reports.steel_detail_report import FIELD_LABELS,export
from core.takeoff.reviewed_aec import SPECS
DECK_FIELDS=('length_m','width_m','topping_m','flute_depth_m','flute_top_m','flute_bottom_m','pitch_m','profile_ref','source_ref','approved_by')


def fill_table(table,columns,records):
 _fill_table(table,columns,records)
 choices={'payment_basis':[('تعداد مجموعه کامل','count'),('جرم مجموعه کامل','kg')],'operation':[('ساخت','fabrication'),('نصب','erection'),('آماده‌سازی سطح','surface_preparation')]}
 for row,p in enumerate(records):
  for col,(key,_) in enumerate(columns):
   if key not in choices:continue
   w=QComboBox();w.addItem('نیازمند انتخاب','')
   for title,value in choices[key]:w.addItem(title,value)
   w.setCurrentIndex(max(0,w.findData(p.get(key,''))));table.setCellWidget(row,col,w)

def open_steel_editor(service,*,parent=None,project_id='',floor_id='',kind='steel_frame'):
 dialog=QDialog(parent);dialog.setObjectName('SteelDetailEditor');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1200,820);outer=QVBoxLayout(dialog);c={};dialog.steel_controls=c;state={'record':None,'data':None,'group':None}
 def line(layout,key,title,value=''):
  w=QLineEdit(str(value));layout.addRow(title,w);c[key]=w;return w
 top=QFormLayout();outer.addLayout(top);line(top,'project','پروژه',project_id);line(top,'floor','طبقه',floor_id);line(top,'id','شناسه مستقل عضو یا سقف')
 family=QComboBox();[family.addItem(SPECS[k].title,k) for k in KINDS];family.setCurrentIndex(family.findData(kind));top.addRow('نوع سیستم',family);c['kind']=family
 tabs=QTabWidget();outer.addWidget(tabs,1)
 def page(title):
  w=QWidget();layout=QVBoxLayout(w);tabs.addTab(w,title);return layout
 basic=page('هویت و منابع');f=QFormLayout();basic.addLayout(f)
 for key,title in [('building','ساختمان'),('axis','محور'),('source','شناسه منبع مستقل'),('plan','نقشه مرجع'),('detail','دیتایل مرجع')]:line(f,key,title)
 basic.addWidget(QLabel('فقط متره دستی مستند؛ وزن مقطع، چگالی، طول برش و قیمت حدس زده نمی‌شوند.'))
 group_page=page('اعضا، ورق‌ها و اتصالات');f=QFormLayout();group_page.addLayout(f);group=QComboBox();[group.addItem(LABELS[k],k) for k in GROUPS];f.addRow('گروه مستقل',group);c['group']=group
 status=QComboBox();[status.addItem(a,b) for a,b in [('نیازمند دیتایل','unreviewed'),('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable')]];f.addRow('وضعیت',status);c['status']=status
 for key,title in [('approver','تأییدکننده دیتایل'),('group_source','منبع گروه'),('na_reason','دلیل عدم کاربرد')]:line(f,key,title)
 entries=QTableWidget();entries.setAlternatingRowColors(True);group_page.addWidget(entries);c['entries']=entries
 def buttons(layout,items):
  row=QHBoxLayout();layout.addLayout(row)
  for key,title in items:
   b=QPushButton(title);row.addWidget(b);c[key]=b
 buttons(group_page,[('add','افزودن قطعه'),('remove','حذف قطعه انتخاب‌شده'),('store','اعمال گروه')])
 geometry=page('مقطع مستند عرشه');f=QFormLayout();geometry.addLayout(f);c['deck_fields']={}
 for key in DECK_FIELDS:
  w=QLineEdit();f.addRow(FIELD_LABELS[key],w);c['deck_fields'][key]=w
 geometry.addWidget(QLabel('شیار ذوزنقه‌ای؛ ورق تمام‌دهانه، هم‌پوشانی طولی صفر؛ بازشو و برش تا قرارداد معتبر مسدودند.'))
 panel_page=page('جانمایی ورق‌های عرشه');panels=QTableWidget();panel_page.addWidget(panels);c['panels']=panels;c['panel_columns']=[(k,FIELD_LABELS[k]) for k in COMMON+PANEL_FIELDS];panels.setColumnCount(len(c['panel_columns']));panels.setHorizontalHeaderLabels([x[1] for x in c['panel_columns']]);fill_table(panels,c['panel_columns'],[])
 buttons(panel_page,[('panel_add','افزودن ورق عرشه'),('panel_remove','حذف ورق انتخاب‌شده')])
 approval=page('بازبینی و اصلاحیه رسمی');f=QFormLayout();approval.addLayout(f)
 for key,title in [('reviewer','بازبین مستقل'),('note','یادداشت بازبینی'),('creator','درخواست‌کننده اصلاحیه'),('reason','علت اصلاح یا کپی یا حذف'),('evidence_path','مسیر مدرک جدید'),('evidence_ref','مرجع مدرک جدید'),('amend_id','شناسه اصلاحیه')]:line(f,key,title)
 buttons(approval,[('create_amendment','ثبت درخواست اصلاحیه'),('review_amendment','بازبینی مستقل اصلاحیه'),('apply_amendment','اعمال اصلاحیه')])
 f=QFormLayout();approval.addLayout(f);line(f,'new_id','شناسه مستقل کپی');line(f,'new_source','منبع مستقل کپی');buttons(approval,[('copy','کپی با هویت جدید'),('delete','حذف کنترل‌شده پیش‌نویس')])
 summary=page('ریزمتره و خروجی');grid=QTableWidget(0,4);grid.setHorizontalHeaderLabels(['شرح','مقدار','واحد','مرجع']);summary.addWidget(grid);buttons(summary,[(x,y) for x,y in [('pdf','گزارش پی‌دی‌اف'),('xlsx','گزارش اکسل'),('docx','گزارش ورد'),('csv','داده جدولی')]])
 message=QLabel('داده ناقص قابل ثبت قطعی نیست.');message.setWordWrap(True);outer.addWidget(message);c['message']=message
 buttons(outer,[('new','عضو جدید'),('load','بازگشایی'),('save','ذخیره'),('preview','محاسبه و ریزمتره'),('review','بازبینی'),('commit','ثبت قطعی در فهرست مقادیر')])
 def context():return c['project'].text().strip(),family.currentData(),c['floor'].text().strip(),c['id'].text().strip()
 def store_group():
  if not state['data'] or not state['group']:return
  state['data']['steel_detail']['groups'][state['group']]={'status':status.currentData(),'approved_by':c['approver'].text().strip(),'source_ref':c['group_source'].text().strip(),'reason':c['na_reason'].text().strip(),'entries':read_table(entries,c['columns'])}
 def show_group():
  k=group.currentData();p=state['data']['steel_detail']['groups'][k];c['columns']=[(x,FIELD_LABELS[x]) for x in COMMON+FIELDS[k]];entries.setColumnCount(len(c['columns']));entries.setHorizontalHeaderLabels([x[1] for x in c['columns']]);fill_table(entries,c['columns'],p.get('entries',[]));state['group']=k;status.setCurrentIndex(max(0,status.findData(p.get('status'))))
  for key,field in [('approver','approved_by'),('group_source','source_ref'),('na_reason','reason')]:c[key].setText(str(p.get(field,'')))
 def change_group():store_group();show_group()
 group.currentIndexChanged.connect(change_group)
 def paint(record):
  for key in ('save','preview','review','commit'):c[key].setEnabled(True)
  for i in range(tabs.count()):tabs.setTabEnabled(i,True)
  state.update(record=deepcopy(record),data=deepcopy(record['data']),group=None);d=state['data'];dialog.setWindowTitle('متره تخصصی '+SPECS[d['kind']].title);family.setCurrentIndex(family.findData(d['kind']))
  for k,field in [('building','building_id'),('axis','axis')]:c[k].setText(str(d.get(field,'')))
  for k,field in [('source','source_id'),('plan','plan_ref'),('detail','detail_ref')]:c[k].setText(str(d.get('source',{}).get(field,'')))
  deck=d['steel_detail'].get('deck') or {}
  for key,w in c['deck_fields'].items():w.setText(str(deck.get(key,'')))
  fill_table(panels,c['panel_columns'],deck.get('panels',[]));tabs.setTabEnabled(2,d['kind']=='steel_deck');tabs.setTabEnabled(3,d['kind']=='steel_deck');show_group();message.setText('نسخه '+str(record['revision'])+'؛ '+('قطعی؛ تغییر فقط با اصلاحیه' if record['status']=='committed' else 'پیش‌نویس'))
 def capture():
  if state['data'] is None:raise ValueError('ابتدا عضو جدید یا بازگشایی را انتخاب کنید')
  store_group();d=deepcopy(state['data']);d.update(building_id=c['building'].text().strip(),axis=c['axis'].text().strip());d['source']={'mode':'manual','source_id':c['source'].text().strip(),'plan_ref':c['plan'].text().strip(),'detail_ref':c['detail'].text().strip()}
  if d['kind']!=context()[1] or d['system_id']!=context()[3] or d['floor_id']!=context()[2]:raise ValueError('هویت فرم تغییر کرده؛ عضو جدید یا بازگشایی را انتخاب کنید')
  d['steel_detail']['deck']={**{k:w.text().strip() for k,w in c['deck_fields'].items()},'panels':read_table(panels,c['panel_columns']),'openings':[]} if d['kind']=='steel_deck' else None
  if d.get('roof_review',{}).get('digest')!=review_digest(d):d.pop('roof_review',None)
  return d
 def new():
  pid,k,floor,sid=context()
  if not pid or not floor or not sid or service.open_project(pid) is None:raise ValueError('پروژه، طبقه و شناسه لازم است')
  if service.get_aec_system(pid,k,floor,sid):raise ValueError('شناسه موجود است؛ بازگشایی کنید')
  d=service.new_aec_system(k,floor,sid);d.update(measurement_policy=POLICY,steel_detail={'groups':{g:{'status':'unreviewed','entries':[]} for g in GROUPS},'deck':None});paint({'data':d,'revision':0,'status':'draft'})
 def load():
  r=service.get_aec_system(*context())
  if not r or r['data'].get('measurement_policy')!=POLICY:raise ValueError('رکورد تخصصی یافت نشد؛ مهاجرت خاموش تاریخی ممنوع است')
  paint(r)
 def save():
  d=capture();d.pop('roof_review',None);paint(service.save_aec_system_draft(context()[0],d,expected_revision=state['record']['revision']))
 def unchanged():
  if review_digest(capture())!=review_digest(state['record']['data']):raise ValueError('ابتدا تغییرات پیش‌نویس را ذخیره کنید')
 def preview():
  from core.takeoff.steel_detail import preview as calculate
  r=calculate(capture(),service.takeoff);grid.setRowCount(len(r['rows']))
  from PySide6.QtWidgets import QTableWidgetItem
  for i,v in enumerate(r['rows']):
   for j,x in enumerate([v['description'],v['quantity'],v['unit'],v['source_ref']]):grid.setItem(i,j,QTableWidgetItem(str(x)))
  message.setText('محاسبه معتبر؛ نیازمند بازبینی نسخه جاری' if r['ready'] else '؛ '.join(r['blockers']))
 def review():unchanged();paint(service.review_roof_system(*context(),expected_revision=state['record']['revision'],reviewer=c['reviewer'].text(),note=c['note'].text()))
 def commit():unchanged();service.commit_aec_system(*context(),expected_revision=state['record']['revision']);load()
 def create_amendment():
  path=Path(c['evidence_path'].text().strip());a=service.create_roof_amendment(*context(),capture(),expected_revision=state['record']['revision'],created_by=c['creator'].text(),reason=c['reason'].text(),evidence={'evidence_path':str(path),'evidence_sha256':sha256(path.read_bytes()).hexdigest(),'evidence_reference':c['evidence_ref'].text()});c['amend_id'].setText(a['id'])
 def review_amendment():service.review_beam_amendment(context()[0],c['amend_id'].text(),expected_revision=1,reviewer=c['reviewer'].text(),note=c['note'].text());message.setText('اصلاحیه با بازبین مستقل بازبینی شد')
 def apply_amendment():service.apply_beam_amendment(context()[0],c['amend_id'].text(),expected_revision=1);load()
 def copy():service.aec_workflow().copy_roof(*context(),new_system_id=c['new_id'].text(),new_source_id=c['new_source'].text(),reason=c['reason'].text());c['id'].setText(c['new_id'].text());load()
 def delete():
  if QMessageBox.question(dialog,'حذف کنترل‌شده','حذف پیش‌نویس با حفظ تاریخچه انجام شود؟')!=QMessageBox.Yes:return
  service.aec_workflow().delete_roof(*context(),expected_revision=state['record']['revision'],reason=c['reason'].text());message.setText('پیش‌نویس حذف شد؛ تاریخچه محفوظ است')
 def report(fmt):
  unchanged();path,_=QFileDialog.getSaveFileName(dialog,'مسیر گزارش','',fmt.upper()+' (*.'+fmt+')')
  if path:export(service,*context(),path,format=fmt);message.setText('گزارش ذخیره شد')
 def add(table,columns):
  records=read_table(table,columns);records.append({});fill_table(table,columns,records)
 def remove(table):
  if table.currentRow()<0:raise ValueError('قطعه را انتخاب کنید')
  table.removeRow(table.currentRow())
 def guarded(fn):
  def run(*_):
   try:fn()
   except (ValueError,RuntimeError,KeyError,TypeError,OSError) as e:QMessageBox.warning(dialog,'کنترل مهندسی',str(e))
  return run
 for key,fn in [('new',new),('load',load),('save',save),('preview',preview),('review',review),('commit',commit),('store',store_group),('add',lambda:add(entries,c['columns'])),('remove',lambda:remove(entries)),('panel_add',lambda:add(panels,c['panel_columns'])),('panel_remove',lambda:remove(panels)),('create_amendment',create_amendment),('review_amendment',review_amendment),('apply_amendment',apply_amendment),('copy',copy),('delete',delete)]:c[key].clicked.connect(guarded(fn))
 for fmt in ('pdf','xlsx','docx','csv'):c[fmt].clicked.connect(guarded(lambda fmt=fmt:report(fmt)))
 for key in ('save','preview','review','commit'):c[key].setEnabled(False)
 for i in range(1,tabs.count()):tabs.setTabEnabled(i,False)
 dialog.exec();return dialog
