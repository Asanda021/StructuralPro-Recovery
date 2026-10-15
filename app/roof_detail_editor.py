"""Typed Persian roof specialization launched from the existing AEC editor."""
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QLabel,QTabWidget,QWidget,QTableWidget,QTableWidgetItem,QMessageBox,QFileDialog,QScrollArea)
from core.takeoff.roof_detail import KINDS,WAFFLE_KINDS,BARS,LABELS,POLICY,review_digest
from core.takeoff.reviewed_aec import SPECS,preview_system,_id

REGIONS=[('id','شناسه'),('component','نوع ناحیه'),('x','ابتدای طول'),('y','ابتدای عرض'),('z','تراز ابتدا'),('length','طول'),('width','عرض'),('height','ارتفاع'),('source_ref','مرجع'),('approved_by','تأییدکننده')]
DEDUCTIONS=[('id','شناسه کسر'),('kind','نوع کسر'),('owner_source_id','منبع مالک بتن مشترک')]+REGIONS[2:]
PIECES=[('id','شناسه قطعه'),('region_id','شناسه ناحیه پرکننده'),('count','تعداد واقعی'),('length','طول'),('width','عرض'),('height','ارتفاع'),('nx','تعداد در طول'),('ny','تعداد در عرض'),('nz','تعداد در ارتفاع'),('source_ref','مرجع چیدمان'),('spec_ref','مشخصات قطعه')]
LAYOUT=[field for field in REGIONS if field[0]!='component']
RIB_LAYOUT=[LAYOUT[0],('axis','جهت ریب')]+LAYOUT[1:]
WAFFLE_PIECES=[(key,'شناسه ناحیه حفره قالب' if key=='region_id' else title) for key,title in PIECES]+[('physical_key','هویت مستقل قالب'),('shape','هندسه قالب'),('approved_by','تأییدکننده قالب')]
STEEL=[('id','شناسه سری'),('supply_scope','دامنه تأمین میلگرد'),('physical_key','هویت فیزیکی مستقل'),('diameter_mm','قطر (میلی‌متر)'),('count','تعداد'),('cut_length_m','طول برش (متر)'),('unit_weight_kg_m','وزن واحد (کیلوگرم بر متر)'),('unit_weight_source','منبع وزن واحد'),('shape_ref','شکل دیتایل'),('source_ref','مرجع سری')]
FACES=[('id','شناسه وجه'),('physical_key','هویت سطح مستقل'),('length_m','طول (متر)'),('width_m','عرض (متر)'),('deduction_m2','کسر سطح مستند'),('source_ref','مرجع')]
PROPS=[('id','شناسه شمع'),('physical_key','هویت مستقل'),('count','تعداد'),('height_m','ارتفاع (متر)'),('source_ref','مرجع'),('system_ref','روش و مشخصات')]
ENUMS={'axis':[('امتداد طول','x'),('امتداد عرض','y')],'shape':[('منشوری مستطیلی مستند','rectangular_prism')],'supply_scope':[('کارگاهی؛ پرداخت مستقل','site'),('داخل تیرچه خریداری‌شده؛ مصالح غیرقابل پرداخت مستقل','factory')],'component':[(LABELS[k],k) for k in ('concrete','topping','ribs','ties','solid_zones','precast','void','ribs_x','ribs_y','junctions')],'kind':[('بازشو','opening'),('تقاطع تیر و سقف','beam_joint')]}


def fill_table(table,cols,records):
 table.setRowCount(0)
 for data in records:
  row=table.rowCount();table.insertRow(row)
  for col,(key,_) in enumerate(cols):
   if key in ENUMS:
    w=QComboBox();w.addItem('انتخاب صریح',None)
    for label,value in ENUMS[key]:
     allowed=table.property('allowed_components') if key=='component' else None
     if allowed is None or value in allowed:w.addItem('حفره قالب وافل' if key=='component' and value=='void' and allowed and 'junctions' in allowed else label,value)
    w.setCurrentIndex(max(0,w.findData(data.get(key))));table.setCellWidget(row,col,w)
   else:table.setItem(row,col,QTableWidgetItem(str(data.get(key,''))))
  table.item(row,0).setData(Qt.ItemDataRole.UserRole,deepcopy(data))


def read_table(table,cols):
 rows=[]
 for row in range(table.rowCount()):
  first=table.item(row,0);data=deepcopy(first.data(Qt.ItemDataRole.UserRole) or {}) if first else {}
  for col,(key,_) in enumerate(cols):
   w=table.cellWidget(row,col);item=table.item(row,col)
   data[key]=w.currentData() if w else (item.text().strip() if item else '')
  rows.append(data)
 return rows


def open_roof_editor(service,*,parent=None,project_id='',floor_id='',kind='solid_slab'):
 dialog=QDialog(parent);dialog.setObjectName('RoofDetailEditor');dialog.setWindowTitle('متره تخصصی '+SPECS[kind].title+' — ناحیه‌بندی و دیتایل مستند');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1280,850)
 outer=QVBoxLayout(dialog);tabs=QTabWidget();outer.addWidget(tabs);controls={};state={'record':None,'identity':None}
 def page(title):
  content=QWidget();layout=QVBoxLayout(content);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);tabs.addTab(scroll,title);return layout
 def line(layout,key,title,value=''):
  w=QLineEdit(str(value));layout.addRow(title,w);controls[key]=w;return w
 def combo(layout,key,title,options):
  w=QComboBox();w.addItem('انتخاب صریح',None)
  for label,value in options:w.addItem(label,value)
  layout.addRow(title,w);controls[key]=w;return w
 def piece_columns():return WAFFLE_PIECES if kindbox.currentData() in WAFFLE_KINDS else PIECES
 def table(layout,key,cols):
  t=QTableWidget(0,len(cols));t.setHorizontalHeaderLabels([title for _,title in cols]);t.setAlternatingRowColors(True);layout.addWidget(t);controls[key]=t
  bar=QHBoxLayout();layout.addLayout(bar)
  for action,label in [('add','افزودن ردیف'),('remove','حذف ردیف انتخابی')]:
   b=QPushButton(label);bar.addWidget(b);controls[key+'_'+action]=b
   if action=='add':b.clicked.connect(lambda _=False,t=t,c=cols,key=key:fill_table(t,piece_columns() if key=='pieces' else c,read_table(t,piece_columns() if key=='pieces' else c)+[{}]))
   else:
    def remove(_=False,t=t):
     rows={x.row() for x in t.selectedIndexes()}
     if not rows and t.currentRow()>=0:rows={t.currentRow()}
     for i in sorted(rows,reverse=True):t.removeRow(i)
    b.clicked.connect(remove)
  return t
 basic=page('مشخصات و هندسه');f=QFormLayout();basic.addLayout(f)
 project=line(f,'project','پروژه',project_id);floor=line(f,'floor','طبقه',floor_id)
 kindbox=combo(f,'kind','سیستم سقف',[(SPECS[k].title,k) for k in KINDS]);kindbox.setCurrentIndex(kindbox.findData(kind))
 for key,title in [('id','شناسه سقف'),('building','شناسه ساختمان'),('source','شناسه منبع مستقل'),('plan','پلان مرجع'),('detail','دیتایل مرجع')]:line(f,key,title)
 combo(f,'joist_supply_scope','دامنه تأمین تیرچه',[('تیرچه خریداری‌شده؛ بتن و میلگرد کارخانه‌ای غیرقابل پرداخت مستقل','purchased_joists')]);combo(f,'unit','واحد ابعاد',[('متر','m')]);combo(f,'shape','هندسه',[('مستطیلی و ناحیه‌های مستقل','rectangular')]);combo(f,'repeat_scope','دامنه تکرار',[('سقف‌های هم‌تیپ با تکرار صریح','identical_roofs')]);combo(f,'action','رفتار مستند دال',[('یک‌طرفه','one_way'),('دوطرفه','two_way')]);combo(f,'joist_axis','جهت تیرچه',[('امتداد طول','x'),('امتداد عرض','y')])
 for key,title in [('length','طول کل (متر)'),('width','عرض کل (متر)'),('depth','ارتفاع کل (متر)'),('count','تعداد سقف هم‌تیپ'),('topping_thickness','ضخامت رویه (متر)'),('joist_count','تعداد واقعی تیرچه'),('joist_spacing','فاصله واقعی محور تیرچه (متر)'),('geometry_ref','مرجع هندسه'),('geometry_approver','تأییدکننده هندسه'),('deductions_ref','مرجع کسورات یا نبود تقاطع'),('pieces_ref','مرجع چیدمان قطعات یا عدم کاربرد')]:line(f,key,title)
 combo(f,'rib_axis','جهت اصلی ریب وافل',[('امتداد طول','x'),('امتداد عرض','y')])
 basic.addWidget(QLabel('قرارداد فعلی: ناحیه‌بندی مستطیلی کامل و غیرهم‌پوشان؛ بازشوی قطع‌کننده تیرچه/قطعه نیازمند قرارداد قطعه‌بندی مستقل است.'))
 table(page('جانمایی واقعی تیرچه‌ها'),'joist_layout',LAYOUT);table(page('نواحی بتن و پرکننده'),'regions',REGIONS);table(page('بازشو و تقاطع مستند'),'deductions',DEDUCTIONS);table(page('قطعات و قالب‌های وافل'),'pieces',piece_columns());table(page('جانمایی مستقل ریب‌های وافل'),'rib_layout',RIB_LAYOUT)
 steel=page('گروه‌های مستقل میلگرد');sf=QFormLayout();steel.addLayout(sf);group=combo(sf,'bar_group','گروه مستقل',[(LABELS[k],k) for k in BARS]);bar_state=combo(sf,'bar_status','وضعیت',[('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable'),('نیازمند دیتایل','unreviewed')]);line(sf,'bar_approver','تأییدکننده');line(sf,'bar_ref','مرجع گروه');line(sf,'bar_reason','دلیل عدم کاربرد');table(steel,'bars',STEEL)
 cut=QPushButton('ریز اجزای برش، خم، قلاب و وصله');store_bar=QPushButton('اعمال گروه میلگرد');steel.addWidget(cut);steel.addWidget(store_bar);controls.update(cut=cut,store_bar=store_bar)
 for key,title,cols in [('formwork','وجه‌های مستقل قالب',FACES),('shoring','شمع‌بندی مستند',PROPS)]:
  layout=page(title);ff=QFormLayout();layout.addLayout(ff)
  combo(ff,key+'_status','وضعیت',[('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable'),('نیازمند دیتایل','unreviewed')])
  for suffix,label in [('approver','تأییدکننده'),('ref','مرجع'),('reason','دلیل عدم کاربرد')]:line(ff,key+'_'+suffix,label)
  table(layout,key,cols)
 review_page=page('بازبینی، اصلاحیه و گزارش');rf=QFormLayout();review_page.addLayout(rf)
 for key,title in [('reviewer','بازبین مستقل'),('note','یادداشت بازبینی'),('creator','سازنده اصلاحیه'),('reason','علت اصلاح، کپی یا حذف'),('evidence_path','فایل مدرک جدید اصلاحیه'),('evidence_ref','مرجع مدرک جدید'),('amend_id','شناسه اصلاحیه'),('new_id','شناسه مستقل کپی'),('new_source','منبع مستقل کپی')]:line(rf,key,title)
 summary=QTableWidget(0,4);summary.setHorizontalHeaderLabels(['شرح','مقدار','واحد','منبع']);review_page.addWidget(summary);controls['summary']=summary
 message=QLabel('سقف جدید بدون داده فرضی ایجاد می‌شود؛ بررسی‌نشده به معنی صفر نیست.');message.setWordWrap(True);outer.addWidget(message);controls['message']=message
 buttons={};bar=QHBoxLayout();outer.addLayout(bar)
 for action,label in [('new','عضو جدید'),('load','بازگشایی'),('save','ذخیره SQLite'),('preview','پیش‌نمایش'),('review','بازبینی نسخه جاری'),('commit','ثبت قطعی BOQ'),('copy','کپی مستقل'),('delete','حذف پیش‌نویس')]:
  b=QPushButton(label);bar.addWidget(b);buttons[action]=b
 second=QHBoxLayout();review_page.addLayout(second)
 for action,label in [('create_amendment','درخواست اصلاحیه'),('review_amendment','بازبینی مستقل اصلاحیه'),('apply_amendment','اعمال اصلاحیه'),('pdf','پی‌دی‌اف'),('xlsx','اکسل'),('docx','ورد'),('csv','داده متنی')]:
  b=QPushButton(label);second.addWidget(b);buttons[action]=b
 controls.update(buttons);dialog.roof_controls=controls
 bars_data={k:{'status':'unreviewed'} for k in BARS};editing=[None]
 def context():
  values=(project.text().strip(),kindbox.currentData(),floor.text().strip(),controls['id'].text().strip())
  if not all(values):raise ValueError('پروژه، سیستم، طبقه و شناسه سقف لازم است')
  if service.open_project(values[0]) is None:raise ValueError('پروژه موجود نیست')
  return values
 def draft():
  ctx=context()
  if state['identity']!=ctx or not state['record']:raise ValueError('ابتدا عضو جدید یا بازگشایی را انتخاب کنید')
  return deepcopy(state['record']['data'])
 def show_bar():
  k=group.currentData()
  if not k:return
  p=bars_data[k];bar_state.setCurrentIndex(max(0,bar_state.findData(p.get('status'))))
  for suffix,field in [('approver','approved_by'),('ref','source_ref'),('reason','reason')]:controls['bar_'+suffix].setText(str(p.get(field,'')))
  fill_table(controls['bars'],STEEL,p.get('series',[]));editing[0]=k
 def capture_bar():
  k=editing[0]
  if k:bars_data[k]={'status':bar_state.currentData(),'approved_by':controls['bar_approver'].text().strip(),'source_ref':controls['bar_ref'].text().strip(),'reason':controls['bar_reason'].text().strip(),'series':read_table(controls['bars'],STEEL)}
 def paint(entry):
  state.update(record=deepcopy(entry),identity=context());d=entry['data'];rd=d.get('roof_detail',{});g=rd.get('geometry',{})
  for key,field in [('building','building_id')]:controls[key].setText(str(d.get(field,'')))
  for key,field in [('source','source_id'),('plan','plan_ref'),('detail','detail_ref')]:controls[key].setText(str(d.get('source',{}).get(field,'')))
  for key in ('unit','shape','repeat_scope','action','joist_axis','joist_supply_scope','rib_axis'):controls[key].setCurrentIndex(max(0,controls[key].findData(g.get(key))))
  for key in ('length','width','depth','count','topping_thickness','joist_count','joist_spacing'):controls[key].setText(str(g.get(key,'')))
  for key,field in [('geometry_ref','source_ref'),('geometry_approver','approved_by')]:controls[key].setText(str(g.get(field,'')))
  for key in ('deductions_ref','pieces_ref'):controls[key].setText(str(rd.get(key,'')))
  if d['kind'] in WAFFLE_KINDS:controls['regions'].setProperty('allowed_components',['topping','ribs_x','ribs_y','junctions','solid_zones','void'])
  else:controls['regions'].setProperty('allowed_components',['concrete','topping','ribs','ties','solid_zones','precast','void'])
  controls['pieces'].setColumnCount(len(piece_columns()));controls['pieces'].setHorizontalHeaderLabels([title for _,title in piece_columns()])
  for key,cols in [('regions',REGIONS),('deductions',DEDUCTIONS),('pieces',piece_columns()),('joist_layout',LAYOUT),('rib_layout',RIB_LAYOUT)]:fill_table(controls[key],cols,rd.get(key,[]))
  bars_data.clear();bars_data.update(deepcopy(rd.get('rebars',{k:{'status':'unreviewed'} for k in BARS})));editing[0]=None;group.blockSignals(True);group.setCurrentIndex(1);group.blockSignals(False);show_bar()
  for key,cols,listkey in [('formwork',FACES,'faces'),('shoring',PROPS,'props')]:
   p=rd.get(key,{})
   controls[key+'_status'].setCurrentIndex(max(0,controls[key+'_status'].findData(p.get('status'))))
   for suffix,field in [('approver','approved_by'),('ref','source_ref'),('reason','reason')]:controls[key+'_'+suffix].setText(str(p.get(field,'')))
   fill_table(controls[key],cols,p.get(listkey,[]))
  is_slab=d['kind']=='solid_slab';is_waffle=d['kind'] in WAFFLE_KINDS
  dialog.setWindowTitle('متره تخصصی '+SPECS[d['kind']].title+' — ناحیه‌بندی و دیتایل مستند')
  for key in ('action',):controls[key].setEnabled(is_slab or is_waffle)
  for key in ('topping_thickness','joist_count','joist_spacing','joist_axis','joist_supply_scope','pieces','pieces_add','pieces_remove','joist_layout','joist_layout_add','joist_layout_remove'):controls[key].setEnabled(not is_slab)
  controls['topping_thickness'].setEnabled(not is_slab)
  for key in ('joist_count','joist_spacing','joist_axis','joist_supply_scope','joist_layout','joist_layout_add','joist_layout_remove'):controls[key].setEnabled(not is_slab and not is_waffle)
  for key in ('rib_axis','rib_layout','rib_layout_add','rib_layout_remove'):controls[key].setEnabled(is_waffle)
  message.setText('نسخه '+str(entry['revision'])+'؛ '+('قطعی؛ تغییر فقط با اصلاحیه' if entry['status']=='committed' else 'پیش‌نویس؛ نیازمند بازبینی نسخه جاری'))
 def capture():
  d=draft();capture_bar();g={key:(controls[key].currentData() if isinstance(controls[key],QComboBox) else controls[key].text().strip()) for key in ('unit','shape','repeat_scope','action','joist_axis','joist_supply_scope','rib_axis','length','width','depth','count','topping_thickness','joist_count','joist_spacing')}
  if kindbox.currentData() not in WAFFLE_KINDS:g.pop('rib_axis',None)
  g.update(source_ref=controls['geometry_ref'].text().strip(),approved_by=controls['geometry_approver'].text().strip());d['building_id']=controls['building'].text().strip()
  source=deepcopy(d.get('source',{}));source.update(mode=source.get('mode','manual'),source_id=controls['source'].text().strip(),plan_ref=controls['plan'].text().strip(),detail_ref=controls['detail'].text().strip());d['source']=source
  rd={'geometry':g,'rebars':deepcopy(bars_data)}
  for key,cols in [('regions',REGIONS),('deductions',DEDUCTIONS),('pieces',piece_columns()),('joist_layout',LAYOUT),('rib_layout',RIB_LAYOUT)]:rd[key]=read_table(controls[key],cols)
  if kindbox.currentData() not in WAFFLE_KINDS:rd.pop('rib_layout',None)
  for key in ('deductions_ref','pieces_ref'):rd[key]=controls[key].text().strip()
  for key,cols,listkey in [('formwork',FACES,'faces'),('shoring',PROPS,'props')]:rd[key]={'status':controls[key+'_status'].currentData(),'approved_by':controls[key+'_approver'].text().strip(),'source_ref':controls[key+'_ref'].text().strip(),'reason':controls[key+'_reason'].text().strip(),listkey:read_table(controls[key],cols)}
  d.update(measurement_policy=POLICY,roof_detail=rd)
  if d.get('roof_review',{}).get('digest')!=review_digest(d):d.pop('roof_review',None)
  return d
 def show_preview(r):
  summary.setRowCount(0)
  for v in r['rows']:
   i=summary.rowCount();summary.insertRow(i)
   for j,x in enumerate([v['description'],v['quantity'],v['unit'],v['source_ref']]):summary.setItem(i,j,QTableWidgetItem(str(x)))
  message.setText('محاسبه معتبر؛ ثبت نیازمند بازبینی نسخه جاری است' if r['ready'] else 'نیازمند اطلاعات یا دیتایل: '+'؛ '.join(r['blockers']))
 def load():
  ctx=context();e=service.get_aec_system(*ctx)
  if not e:raise ValueError('عضو ذخیره‌شده یافت نشد؛ عضو جدید را انتخاب کنید')
  if e['data'].get('measurement_policy')!=POLICY:raise ValueError('عضو تاریخی فاقد قرارداد تخصصی است؛ تبدیل خودکار ممنوع')
  paint(e)
 def new():
  pid,k,fl,mid=context()
  if service.get_aec_system(pid,k,fl,mid):raise ValueError('شناسه موجود است؛ بازگشایی کنید')
  d=service.new_aec_system(k,fl,mid);d['measurement_policy']=POLICY;paint({'status':'draft','revision':0,'data':d})
 def save():
  pid,*_=context();d=capture();d.pop('roof_review',None);paint(service.save_aec_system_draft(pid,d,expected_revision=state['record']['revision']))
 def unchanged():
  d=capture()
  if review_digest(d)!=review_digest(state['record']['data']):raise ValueError('تغییرات ابتدا باید ذخیره شوند')
  return d
 def review():
  unchanged();ctx=context();paint(service.review_roof_system(*ctx,expected_revision=state['record']['revision'],reviewer=controls['reviewer'].text(),note=controls['note'].text()))
 def commit():
  unchanged();ctx=context();service.commit_aec_system(*ctx,expected_revision=state['record']['revision']);load()
 def copy():
  pid,k,fl,mid=context();service.aec_workflow().copy_roof(pid,k,fl,mid,new_system_id=controls['new_id'].text(),new_source_id=controls['new_source'].text(),reason=controls['reason'].text());controls['id'].setText(controls['new_id'].text());load()
 def delete():
  ctx=context()
  if state['record']['status']=='committed':raise ValueError('حذف سقف قطعی ممنوع است')
  if QMessageBox.question(dialog,'حذف کنترل‌شده','پیش‌نویس حذف و در تاریخچه نگهداری شود؟',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
  service.aec_workflow().delete_roof(*ctx,expected_revision=state['record']['revision'],reason=controls['reason'].text());state.update(record=None,identity=None);message.setText('پیش‌نویس حذف شد؛ تاریخچه محفوظ است')
 def create_amendment():
  ctx=context();p=Path(controls['evidence_path'].text().strip())
  if not p.is_file():raise ValueError('فایل مدرک جدید موجود نیست')
  d=capture();d.pop('roof_review',None)
  a=service.create_roof_amendment(*ctx,d,expected_revision=state['record']['revision'],created_by=controls['creator'].text(),reason=controls['reason'].text(),evidence={'evidence_path':str(p),'evidence_sha256':sha256(p.read_bytes()).hexdigest(),'evidence_reference':controls['evidence_ref'].text()});controls['amend_id'].setText(a['id']);message.setText('درخواست اصلاحیه ثبت شد؛ اختلاف‌ها: '+str(a['delta']))
 def selected_amendment():
  pid,k,fl,mid=context();aid=controls['amend_id'].text().strip();a=service.open_project(pid).get('beam_amendments',{}).get(aid)
  if not a or a.get('kind')!='roof_amendment' or a['beam_key']!=_id(k,fl,mid):raise ValueError('اصلاحیه متعلق به سقف انتخابی نیست')
  return pid,aid,a
 def review_amendment():
  pid,aid,a=selected_amendment();service.review_beam_amendment(pid,aid,expected_revision=a['revision'],reviewer=controls['reviewer'].text(),note=controls['note'].text());message.setText('اصلاحیه مستقل بازبینی شد')
 def apply_amendment():
  pid,aid,a=selected_amendment();service.apply_beam_amendment(pid,aid,expected_revision=a['revision']);load()
 def report(fmt):
  ctx=context();path,_=QFileDialog.getSaveFileName(dialog,'ذخیره گزارش سقف','',fmt.upper()+' (*.'+fmt+')')
  if path:service.export_roof_detail_report(*ctx,path,format=fmt);message.setText('گزارش از نسخه ذخیره‌شده صادر شد: '+str(path))
 def cut_parts():
  row=controls['bars'].currentRow()
  if row<0:raise ValueError('یک سری میلگرد انتخاب کنید')
  records=read_table(controls['bars'],STEEL);child=QDialog(dialog);child.setObjectName('RoofCutParts');child.setWindowTitle('اجزای طول برش مستند');child.setLayoutDirection(Qt.RightToLeft);layout=QVBoxLayout(child);cols=[('id','شناسه جزء'),('length_m','طول مستند (متر)'),('source_ref','مرجع مستقیم، خم، قلاب یا وصله')];t=table(layout,'cut_parts',cols);fill_table(t,cols,records[row].get('cut_parts',[]));actions=QHBoxLayout();layout.addLayout(actions);ok=QPushButton('اعمال اجزای برش');cancel=QPushButton('انصراف');actions.addWidget(ok);actions.addWidget(cancel);ok.clicked.connect(child.accept);cancel.clicked.connect(child.reject);child.cut_controls={'grid':t,'add':controls['cut_parts_add'],'remove':controls['cut_parts_remove'],'save':ok,'cancel':cancel}
  if child.exec()==QDialog.Accepted:records[row]['cut_parts']=read_table(t,cols);fill_table(controls['bars'],STEEL,records)
  for k in ('cut_parts','cut_parts_add','cut_parts_remove'):controls.pop(k,None)
 def run(fn):
  try:fn()
  except Exception as exc:QMessageBox.warning(dialog,'کنترل دیتایل سقف',str(exc))
 for key,fn in [('new',new),('load',load),('save',save),('preview',lambda:show_preview(preview_system(capture(),service.takeoff))),('review',review),('commit',commit),('copy',copy),('delete',delete),('create_amendment',create_amendment),('review_amendment',review_amendment),('apply_amendment',apply_amendment)]:buttons[key].clicked.connect(lambda _=False,f=fn:run(f))
 for fmt in ('pdf','xlsx','docx','csv'):buttons[fmt].clicked.connect(lambda _=False,f=fmt:run(lambda:report(f)))
 cut.clicked.connect(lambda:run(cut_parts));store_bar.clicked.connect(lambda:run(capture_bar))
 def switch_group():capture_bar();show_bar()
 group.currentIndexChanged.connect(lambda:run(switch_group))
 controls['capture']=capture;controls['paint']=paint
 return dialog.exec()
