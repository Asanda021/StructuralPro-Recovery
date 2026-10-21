"""Typed Persian architecture form on the existing AEC workflow and SQLite."""
from copy import deepcopy
import json
from hashlib import sha256
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLineEdit,QComboBox,QPushButton,QLabel,QTabWidget,QWidget,QTableWidget,QMessageBox,QFileDialog,QListWidget,QScrollArea
from app.roof_detail_editor import fill_table as _fill_table,read_table
from core.takeoff.architecture_detail import POLICY,KINDS,COMMON,LAYER_FIELDS,REGION_FIELDS,SURFACE_FIELDS,OPENING_FIELDS,review_digest,suggestions
from core.reports.architecture_detail_report import FIELD_LABELS,VALUES,export,field_label
from core.takeoff.reviewed_aec import SPECS,_id
GEOMETRY=('physical_wall_id','length_m','height_m','wall_thickness_m','count','repeat_ref','source_ref','approved_by')
TABLES={'openings':OPENING_FIELDS,'masonry_layers':LAYER_FIELDS,'unit_regions':REGION_FIELDS,'surfaces':SURFACE_FIELDS}
CHOICES={'operation':('floor_fill','floor_screed','floor_concrete','floor_subbase','floor_separator','floor_protection'),'method':('constant_rectangular',),'purchase_unit':('m2','m3','kg'),'material_kind':('brick','cement_block','clay_block','light_block','aac'),'face':('inside','outside'),'layer_code':('base_plaster','white_plaster','cement_render','levelling','protective'),'mode':('units','mortar'),'payment_unit':('m2','m3','kg'),'coverage_scope':('complete','partial'),'penetration':('full_wall','all_layers')}

# UI-only schema metadata. The existing engines own all quantities and safety rules.
SPECIAL_FIELDS={
 'physical_surface_id':'شناسه فیزیکی سطح','host_id':'شناسه میزبان واقعی','space_id':'فضای اجرا',
 'face':'وجه اجرا','plane':'صفحه نصب','shape':'هندسه مستند',
 'width_m':'امتداد دوم (متر)','height_m':'ارتفاع (متر)',
 'x':'ابتدای طول (متر)','y':'ابتدای عرض (متر)',
 'opening_ids':'شناسه بازشوها؛ آرایه JSON مثل ["O1"]',
 'scope_ref':'مرجع محدوده اجرا','zone_id':'شناسه ناحیه رنگ','pass_no':'شماره دست صریح',
 'material_basis':'مبنای مصرف ماده','quantity_per_m2':'مصرف مستند در متر مربع',
 'quantity_unit':'واحد مصرف','material_ref':'مرجع مصالح','rate_ref':'مرجع نرخ مصرف',
 'no_material_reason':'دلیل عدم مصرف ماده','axis':'محور قطعه',
 'fixed_m':'مختصات عمود (متر)','start_m':'ابتدا (متر)','end_m':'انتها (متر)',
 'profile_ref':'مرجع پروفیل','rail_id':'شناسه پروفیل اصلی',
 'hanger_ref':'مرجع آویز','anchorage_ref':'مرجع مهار آویز',
 'main_id':'شناسه پروفیل اصلی','cross_id':'شناسه پروفیل فرعی',
 'connection_ref':'دیتایل اتصال','trim_ref':'مدرک نبشی لبه',
 'stock_ref':'دیتایل برش پانل','placement_ref':'مدرک جانمایی پانل',
 'count':'تعداد مستقل','repeat_ref':'مرجع تعداد تکرار',
 'source_ref':'مرجع مستقل','approved_by':'بازبین/تأییدکننده'}
SPECIAL_VALUE_LABELS={'rectangle':'مستطیل مستند','horizontal':'افقی','vertical':'قائم',
 'ceiling':'سقف','inside':'داخلی','outside':'خارجی','documented_rate':'نرخ مستند',
 'not_applicable':'عدم کاربرد مستند','kg':'کیلوگرم','litre':'لیتر',
 'none':'بدون ماده','x':'در راستای طول','y':'در راستای عرض'}
SPECIAL_ENUMS={'axis':('x','y'),'material_basis':('documented_rate','not_applicable'),
 'quantity_unit':('kg','litre','none')}

def fill_table(table,columns,records):
 table.setColumnCount(len(columns));table.setHorizontalHeaderLabels([x[1] for x in columns]);_fill_table(table,columns,records)
 for row,p in enumerate(records):
  for col,(key,_) in enumerate(columns):
   choices={**CHOICES,**(table.property('architecture_choices') or {})}
   if key not in choices:continue
   w=QComboBox();w.addItem('نیازمند انتخاب','')
   for v in choices[key]:w.addItem(SPECIAL_VALUE_LABELS.get(v,VALUES.get(v,v)),v)
   w.setCurrentIndex(max(0,w.findData(p.get(key,''))));table.setCellWidget(row,col,w)

 if table.property('fit_slope_headers'):
  table.resizeColumnsToContents();table.resizeRowsToContents()

def open_architecture_editor(service,*,parent=None,project_id='',floor_id='',kind='block_wall',specialism=''):
 from core.takeoff.floor_detail import GEOMETRY as FLOOR_GEOMETRY,FIELDS as FLOOR_FIELDS,OPENINGS as FLOOR_OPENINGS,INSULATION_KINDS,INSULATION_OPERATIONS
 from core.takeoff.interior_cover_detail import KINDS as COVER_KINDS,GEOMETRY as COVER_GEOMETRY,TABLES as COVER_TABLES,TITLES as COVER_TITLES,CHOICES as COVER_CHOICES,CONTRACT
 from core.takeoff.skirting_detail import GEOMETRY as SKIRT_GEOMETRY,TABLES as SKIRT_TABLES,TITLES as SKIRT_TITLES,CHOICES as SKIRT_CHOICES,CONTRACT as SKIRT_CONTRACT
 from core.takeoff.slope_aec_detail import GEOMETRY as SLOPE_GEOMETRY,TABLES as SLOPE_TABLES,TITLES as SLOPE_TITLES,CHOICES as SLOPE_CHOICES,CONTRACT as SLOPE_CONTRACT
 from core.takeoff.paint_finish_detail import (CONTRACT as PAINT_CONTRACT,GEOMETRY as PAINT_GEOMETRY,
                                           ZONE as PAINT_ZONE,PASS as PAINT_PASS,OPERATIONS as PAINT_OPERATIONS)
 from core.takeoff.suspended_ceiling_detail import (CONTRACT as CEILING_CONTRACT,GEOMETRY as CEILING_GEOMETRY,
                                           BOX as CEILING_BOX,PANEL as CEILING_PANEL,RAIL as CEILING_RAIL,
                                           HANGER as CEILING_HANGER,CONNECTOR as CEILING_CONNECTOR,
                                           EDGE as CEILING_EDGE,GROUPS as CEILING_GROUPS)
 paint_mode=kind=='paint_finish';ceiling_mode=kind=='suspended_ceiling'
 specialist=paint_mode or ceiling_mode
 special_group_key='stages' if paint_mode else 'groups'
 special_items_key='passes' if paint_mode else 'items'
 special_names=tuple(PAINT_OPERATIONS if paint_mode else CEILING_GROUPS if ceiling_mode else ())
 special_fields={'panels':CEILING_PANEL,'main_rails':CEILING_RAIL,'cross_rails':CEILING_RAIL,
                 'hangers':CEILING_HANGER,'connectors':CEILING_CONNECTOR,'edge_trims':CEILING_EDGE}
 special_titles={'surface_preparation':'آماده‌سازی سطح','putty':'بتونه','primer':'آستر',
                 'finish_coat':'رنگ نهایی','panels':'پانل‌ها','main_rails':'پروفیل اصلی',
                 'cross_rails':'پروفیل فرعی','hangers':'آویزها',
                 'connectors':'اتصال‌ها','edge_trims':'نبشی لبه'}
 def special_title(key):
  return SPECIAL_FIELDS.get(key,FIELD_LABELS.get(key,key))
 def ui_rows(records):
  return [{**r,**({'opening_ids':json.dumps(r['opening_ids'],ensure_ascii=False)}
                  if 'opening_ids' in r else {})} for r in records]
 def domain_rows(name,table,columns):
  rows=read_table(table,columns)
  if paint_mode and name=='zones':
   for item in rows:
    try:linked=json.loads(item['opening_ids'])
    except (ValueError,TypeError) as exc:
     raise ValueError('بازشوها باید آرایه JSON از شناسه‌ها باشند') from exc
    if not isinstance(linked,list) or any(not isinstance(v,str) or not v.strip() for v in linked):
     raise ValueError('شناسه بازشوها باید فهرست متنی صریح باشد')
    item['opening_ids']=linked
  return rows
 slope=kind=='floor_finish' and specialism=='slope'
 skirt=kind=='floor_finish' and specialism=='skirting'
 cover=kind in COVER_KINDS
 insulation=kind in INSULATION_KINDS;floor_mode=kind=='floor_finish' or insulation;geometry_keys=FLOOR_GEOMETRY+(('installation_plane','installation_ref') if insulation else ()) if floor_mode else GEOMETRY;table_fields={'openings':FLOOR_OPENINGS,'layers':FLOOR_FIELDS} if floor_mode else TABLES;state_groups=[] if floor_mode else [('masonry','دیوارچینی'),('finishes','اندود مستقل'),('accessories','اتصال و مسلح‌سازی')]
 if cover:geometry_keys=COVER_GEOMETRY;table_fields=COVER_TABLES;state_groups=[]
 if skirt:geometry_keys=SKIRT_GEOMETRY;table_fields=SKIRT_TABLES;state_groups=[]
 if slope:geometry_keys=SLOPE_GEOMETRY;table_fields=SLOPE_TABLES;state_groups=[]
 if paint_mode:geometry_keys=PAINT_GEOMETRY;table_fields={'openings':CEILING_BOX,'zones':PAINT_ZONE};state_groups=[]
 if ceiling_mode:geometry_keys=CEILING_GEOMETRY;table_fields={'openings':CEILING_BOX};state_groups=[]
 dialog=QDialog(parent);dialog.setObjectName('ArchitectureDetailEditor');dialog.setLayoutDirection(Qt.RightToLeft);dialog.resize(1220,840);outer=QVBoxLayout(dialog);c={};dialog.architecture_controls=c;state={'record':None,'data':None,'project':None}
 def line(layout,key,title,value=''):
  w=QLineEdit(str(value));layout.addRow(title,w);c[key]=w;return w
 def buttons(layout,items):
  row=QHBoxLayout();layout.addLayout(row)
  for key,title in items:
   w=QPushButton(title);row.addWidget(w);c[key]=w
 top=QFormLayout();outer.addLayout(top)
 for key,title,value in [('project','پروژه',project_id),('floor','طبقه',floor_id),('id','شناسه مستقل عضو','')]:line(top,key,title,value)
 family=QComboBox();[family.addItem('شیب‌بندی چندناحیه‌ای مستند' if slope else 'قرنیز؛ قرارداد طولی' if skirt else SPECS[k].title,k) for k in ((kind,) if floor_mode or cover or specialist else tuple(k for k in KINDS if k not in ('floor_finish','paint_finish','suspended_ceiling')+INSULATION_KINDS+COVER_KINDS))];family.setCurrentIndex(family.findData(kind));top.addRow('نوع عملیات',family);c['kind']=family
 tabs=QTabWidget();outer.addWidget(tabs,1);c['tabs']=tabs
 def page(title):
  w=QWidget();layout=QVBoxLayout(w);tabs.addTab(w,title);return layout
 basic=page('هویت و هندسه')
 if slope or specialist:
  content=QWidget();f=QFormLayout(content);scroll=QScrollArea();scroll.setWidgetResizable(True);scroll.setWidget(content);basic.addWidget(scroll);c['geometry_scroll']=scroll
 else:f=QFormLayout();basic.addLayout(f)
 for key,title in [('building','ساختمان'),('axis','فضا و موقعیت'),('source','شناسه منبع مستقل'),('plan','نقشه مرجع'),('detail','دیتایل مرجع')]:line(f,key,title)
 c['geometry_fields']={}
 for key in geometry_keys:
  w=QComboBox() if key in ('shape','installation_plane','plane','face','corner_status') else QLineEdit()
  if key in ('shape','installation_plane','plane','face','corner_status'):
   w.addItem('نیازمند انتخاب','')
   for value in ((('inside','outside','ceiling') if paint_mode else ('ceiling',)) if key=='face' and specialist else
                 ('horizontal','vertical') if key=='plane' and paint_mode else
                 ('horizontal',) if key=='plane' and ceiling_mode else
                 SKIRT_CHOICES[key] if key=='corner_status' else
                 COVER_CHOICES[key] if key in ('plane','face') else
                 ('horizontal',) if key=='installation_plane' else ('rectangle',)):
    w.addItem(SPECIAL_VALUE_LABELS.get(value,VALUES.get(value,value)),value)
  f.addRow(special_title(key) if specialist else field_label(key,{'physical_surface_id':''} if cover else {},cover,skirt),w);c['geometry_fields'][key]=w
 basic.addWidget(QLabel('نواحی مستطیلی متصل؛ ضخامت سه گوشه صریح و گوشه چهارم تابع صفحه است. زیرکار افقی مشترک و مدرک واقعی با هش لازم‌اند. ضخامت، خرید و پرت پیش‌فرض ندارند.' if slope else 'قرنیز طولی مستند؛ درگاه و عدم اجرا با بازه مستقل کسر می‌شوند. قطعات، کنج‌ها و خرید بدون دیتایل ساخته نمی‌شوند.' if skirt else 'سطح مستطیلی با جانمایی مستقل قطعات؛ تعداد، برش و خرید فقط از نقشه چیدمان مستند. خرید و مصالح نصب اطلاعاتی و غیرقابل پرداخت مستقل هستند.' if cover else 'عایق افقی مستطیلی با ضخامت ثابت؛ خرید، رول، هم‌پوشانی نوار، برگشت و شیب مسدود هستند.' if insulation else 'تمام ابعاد بر حسب متر؛ ناحیه مستطیلی و ضخامت ثابت هر لایه با تراز مستقل. ضخامت متغیر نیازمند قرارداد است.' if floor_mode else 'سطح رنگ فقط قائم مستطیلی یا سقف افقی؛ تعداد دست، نرخ مصرف و بازشو باید مستقل مستند شوند.' if paint_mode else 'سقف کاذب مستطیلی افقی؛ پانل، پروفیل، آویز و اتصال واقعی با مدرک مستقل لازم است.' if ceiling_mode else 'تمام ابعاد بر حسب متر؛ فقط دیوار مستطیلی و بند کامل مستند. مقدار، پرت و مصرف حدس زده نمی‌شوند.'))
 states=page('بررسی گروه‌ها و پیشنهادها');f=QFormLayout();states.addLayout(f);c['states']={}
 for group,title in state_groups:
  widgets={};combo=QComboBox();[combo.addItem(t,v) for t,v in [('نیازمند دیتایل','unreviewed'),('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable')]];f.addRow(title,combo);widgets['status']=combo
  for key,label in [('source_ref','مرجع'),('approved_by','تأییدکننده'),('reason','علت عدم کاربرد')]:
   w=QLineEdit();f.addRow(title+'؛ '+label,w);widgets[key]=w
  c['states'][group]=widgets
 buttons(states,[('suggest','پیشنهاد عملیات نیازمند دیتایل')]);proposals=QListWidget();states.addWidget(proposals);c['proposals']=proposals
 c['tables']={};c['columns']={}
 for name,title in (list(SLOPE_TITLES.items()) if slope else list(SKIRT_TITLES.items()) if skirt else list(COVER_TITLES.items()) if cover else [('openings','بازشوهای تمام لایه‌های ناحیه' if insulation else 'بازشوهای تمام لایه‌های کف'),('layers','لایه‌های مستقل عایق؛ خرید مسدود' if insulation else 'لایه‌های مستقل کف و خرید مستند')] if floor_mode else ([('openings','بازشوهای مستند رنگ'),('zones','نواحی مستقل رنگ')] if paint_mode else [('openings','بازشوهای سقف کاذب')] if ceiling_mode else [('openings','بازشوها'),('masonry_layers','لایه‌های مستقل دیوار'),('unit_regions','جانمایی واحدها و بندها'),('surfaces','وجه‌ها و لایه‌های مستقل اندود')])):
  layout=page(title);table=QTableWidget();table.setProperty('fit_slope_headers',slope);table.setProperty('architecture_choices',(SPECIAL_ENUMS if specialist else SLOPE_CHOICES if slope else SKIRT_CHOICES if skirt else {**COVER_CHOICES,'operation':(('ceramic_surface',) if kind=='ceramic_finish' else ('stone_surface',)) if name=='surfaces' else ('adhesive','bedding','grout')} if cover else {'operation':INSULATION_OPERATIONS[kind]} if insulation else {}));table.setAlternatingRowColors(True);layout.addWidget(table);c['tables'][name]=table;columns=[(k,special_title(k) if specialist else field_label(k,{'length_m':''} if name=='stocks' else {},cover,skirt,floor_mode and not skirt)) for k in COMMON+table_fields[name]];c['columns'][name]=columns;fill_table(table,columns,[])
  buttons(layout,[(name+'_add','افزودن ردیف'),(name+'_remove','حذف ردیف انتخاب‌شده')])

 # Specialized tables extend the same architecture dialog, engine and SQLite flow.
 # Status starts unreviewed: the form never invents layers, passes or equipment.
 c['special_groups']={};c['special_tables']={};c['special_columns']={}
 for group_name in special_names:
  group_layout=page(special_titles[group_name]);group_form=QFormLayout();group_layout.addLayout(group_form)
  widgets={};combo=QComboBox()
  for text_value,status_value in [('نیازمند دیتایل','unreviewed'),('تأییدشده','confirmed'),('عدم کاربرد مستند','not_applicable')]:
   combo.addItem(text_value,status_value)
  group_form.addRow('وضعیت مستند گروه',combo);widgets['status']=combo
  for key,title in [('source_ref','مرجع گروه'),('approved_by','بازبین گروه'),('reason','علت عدم کاربرد')]:
   widget=QLineEdit();group_form.addRow(title,widget);widgets[key]=widget
  c['special_groups'][group_name]=widgets
  group_table=QTableWidget();group_table.setAlternatingRowColors(True)
  group_table.setProperty('architecture_choices',SPECIAL_ENUMS)
  group_columns=[(key,special_title(key)) for key in COMMON+(PAINT_PASS if paint_mode else special_fields[group_name])]
  c['special_tables'][group_name]=group_table;c['special_columns'][group_name]=group_columns
  group_layout.addWidget(group_table);fill_table(group_table,group_columns,[])
  buttons(group_layout,[(group_name+'_add','افزودن جزء مستند'),(group_name+'_remove','حذف جزء انتخاب‌شده')])
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
  state.update(record=deepcopy(record),data=deepcopy(record['data']),project=context()[0]);d=state['data'];a=d['architecture_detail'];dialog.setWindowTitle('متره تخصصی شیب‌بندی' if slope else 'متره تخصصی قرنیز' if skirt else 'متره تخصصی '+SPECS[d['kind']].title)
  for key in ('save','preview','review','commit'):c[key].setEnabled(True)
  for i in range(tabs.count()):tabs.setTabEnabled(i,True)
  for key,field in [('building','building_id'),('axis','axis')]:c[key].setText(str(d.get(field,'')))
  for key,field in [('source','source_id'),('plan','plan_ref'),('detail','detail_ref')]:c[key].setText(str(d.get('source',{}).get(field,'')))
  for k,w in c['geometry_fields'].items():
   if isinstance(w,QComboBox):w.setCurrentIndex(max(0,w.findData(a.get('geometry',{}).get(k,''))))
   else:w.setText(str(a.get('geometry',{}).get(k,'')))
  for group,ws in c['states'].items():
   g=a.get(group,{})
   for k,w in ws.items():
    if k=='status':w.setCurrentIndex(max(0,w.findData(g.get(k))))
    else:w.setText(str(g.get(k,'')))
  for name,table in c['tables'].items():fill_table(table,c['columns'][name],ui_rows(a.get(name,[])) if paint_mode else a.get(name,[]))
  for name,widgets in c['special_groups'].items():
   group=a.get(special_group_key,{}).get(name,{})
   for key,w in widgets.items():
    if key=='status':w.setCurrentIndex(max(0,w.findData(group.get(key,'unreviewed'))))
    else:w.setText(str(group.get(key,'') or ''))
   fill_table(c['special_tables'][name],c['special_columns'][name],group.get(special_items_key,[]))
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
  a=d['architecture_detail'];a['geometry']={k:(w.currentData() if isinstance(w,QComboBox) else w.text().strip()) for k,w in c['geometry_fields'].items()};a['geometry']['unit']='m'
  for group,ws in c['states'].items():a[group]={k:w.currentData() if k=='status' else w.text().strip() for k,w in ws.items()}
  for name,table in c['tables'].items():a[name]=domain_rows(name,table,c['columns'][name]) if specialist else read_table(table,c['columns'][name])
  if specialist:
   a[special_group_key]={}
   for name,widgets in c['special_groups'].items():
    group={key:(w.currentData() if key=='status' else w.text().strip()) for key,w in widgets.items()}
    group[special_items_key]=read_table(c['special_tables'][name],c['special_columns'][name])
    a[special_group_key][name]=group
  if d.get('roof_review',{}).get('digest')!=review_digest(d):d.pop('roof_review',None)
  return d
 def new():
  pid,k,floor,sid=context()
  if not pid or not floor or not sid or service.open_project(pid) is None:raise ValueError('پروژه، طبقه و شناسه لازم است')
  if service.get_aec_system(pid,k,floor,sid):raise ValueError('شناسه موجود است؛ بازگشایی کنید')
  d=service.new_aec_system(k,floor,sid);detail={**({'contract':PAINT_CONTRACT} if paint_mode else {'contract':CEILING_CONTRACT} if ceiling_mode else {'contract':SLOPE_CONTRACT} if slope else {'contract':SKIRT_CONTRACT} if skirt else {'contract':CONTRACT} if cover else {}),'geometry':{},**{key:[] for key in table_fields},**{key:{'status':'unreviewed'} for key,title in state_groups}}
  if specialist:detail[special_group_key]={key:dict(status='unreviewed',source_ref='',approved_by='',reason='',**{special_items_key:[]}) for key in special_names}
  d.update(measurement_policy=POLICY,architecture_detail=detail);paint({'data':d,'revision':0,'status':'draft'})
 def load():
  r=service.get_aec_system(*context())
  if not r or r['data'].get('measurement_policy')!=POLICY:raise ValueError('رکورد تخصصی یافت نشد؛ مهاجرت خاموش تاریخی ممنوع است')
  if r['data'].get('architecture_detail',{}).get('contract')!=(PAINT_CONTRACT if paint_mode else CEILING_CONTRACT if ceiling_mode else SLOPE_CONTRACT if slope else SKIRT_CONTRACT if skirt else CONTRACT if cover else None):raise ValueError('قرارداد فرم با رکورد سازگار نیست؛ تبدیل خاموش ممنوع است')
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
   before=old.get(src,{});after=new.get(src,{});q=after.get('quantities',[{}])[0];missing_info=not after and before.get('role')=='material'
   for col,value in enumerate([before.get('description') or after.get('description'),before.get('quantity',0),'فاقد ردیف اطلاعاتی فعال' if missing_info else q.get('amount',0),'حذف ردیف اطلاعاتی؛ صفر استنتاج نمی‌شود' if missing_info else delta,VALUES.get(before.get('unit') or q.get('unit'),before.get('unit') or q.get('unit'))]):comparison.setItem(row,col,QTableWidgetItem(str(value)))
  comparison.resizeColumnsToContents()
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
  if specialist:
   for name in special_names:proposals.addItem(special_titles[name]+'؛ نیازمند دیتایل و جانمایی مستقل')
   message.setText('اطلاعات نمایشی‌اند؛ هیچ مقدار، لایه، دست رنگ یا ردیف مالی حدسی ایجاد نشده است')
   return
  for v in suggestions('wall'):proposals.addItem(v['title']+'؛ '+v['status'])
  message.setText('پیشنهادها مقدار یا فهرست مقادیر ایجاد نمی‌کنند؛ انتخاب و دیتایل مستقل لازم است')
 def guarded(fn):
  def run(*_):
   try:fn()
   except (ValueError,RuntimeError,KeyError,TypeError,OSError) as exc:QMessageBox.warning(dialog,'کنترل مهندسی',str(exc))
  return run
 for key,fn in [('new',new),('load',load),('save',save),('preview',calculate),('review',review),('commit',commit),('create_amendment',create_amendment),('review_amendment',review_amendment),('apply_amendment',apply_amendment),('copy',copy),('delete',delete),('suggest',propose)]:c[key].clicked.connect(guarded(fn))
 for name in table_fields:
  c[name+'_add'].clicked.connect(guarded(lambda name=name:add(name)));c[name+'_remove'].clicked.connect(guarded(lambda name=name:remove(name)))
 for name in special_names:
  def add_special(name=name):
   t=c['special_tables'][name];columns=c['special_columns'][name]
   records=read_table(t,columns);records.append({});fill_table(t,columns,records)
  def remove_special(name=name):
   t=c['special_tables'][name]
   if t.currentRow()<0:raise ValueError('جزء مستند را انتخاب کنید')
   t.removeRow(t.currentRow())
  c[name+'_add'].clicked.connect(guarded(add_special))
  c[name+'_remove'].clicked.connect(guarded(remove_special))
 for fmt in ('pdf','xlsx','docx','csv'):c[fmt].clicked.connect(guarded(lambda fmt=fmt:report(fmt)))
 for key in ('save','preview','review','commit'):c[key].setEnabled(False)
 for i in range(1,tabs.count()):tabs.setTabEnabled(i,False)
 dialog.exec();return dialog
