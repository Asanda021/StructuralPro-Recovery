"""Source-backed row editing inside the existing beam workflow, no data store."""
from copy import deepcopy
from uuid import uuid4
from hashlib import sha256
import json
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QPushButton,QLineEdit,QLabel,QMessageBox

SCHEMAS={
 'series':[('id','شناسه فیزیکی'),('position','موقعیت'),('count','تعداد'),('nominal_diameter_mm','قطر میلی‌متر'),('shape_ref','مرجع شکل'),('cut_length_m','طول برش متر'),('cut_length_ref','مرجع برش شامل خم و مهار'),('unit_weight_kg_m','وزن واحد کیلوگرم بر متر'),('unit_weight_source','مرجع وزن واحد'),('source_ref','دیتایل')],
 'sections':[('id','شناسه ناحیه'),('start_m','شروع متر'),('end_m','پایان متر'),('width_m','عرض متر'),('depth_m','ارتفاع متر'),('source_ref','دیتایل')],
 'surfaces':[('id','شناسه سطح'),('role','کف/جان/انتها'),('gross_area_m2','مساحت ناخالص متر مربع'),('contact','تماس با قالب؛ بله/خیر'),('source_ref','مرجع سطح')],
 'intersections':[('id','شناسه کسر'),('volume_m3','حجم کسر متر مکعب'),('source_ref','مرجع هندسی')],
 'face_deductions':[('id','شناسه کسر سطح'),('area_m2','مساحت کسر متر مربع'),('source_ref','مرجع هندسی')],
 'parts':[('id','شناسه جزء'),('kind','مستقیم/خم/قلاب/مهاری/وصله'),('length_m','طول واقعی متر'),('source_ref','مرجع جزء')],
}
FA={'side3':'وجه سوم','side4':'وجه چهارم','rectangular':'مستطیلی','top':'بالا','bottom':'پایین','span':'دهانه','support':'تکیه‌گاه','side':'کمرکش','crosstie':'سنجاقی','bottom_face':'کف','side1':'جان اول','side2':'جان دوم','end':'انتها','other':'سایر','straight':'مستقیم','bend':'خم','hook':'قلاب','anchorage':'مهاری','lap':'وصله','spiral':'مارپیچ','full_lateral':'تمام سطح جانبی','circular_lateral':'محاسبه محیط در ارتفاع','no_extension_reviewed':'بدون طول اضافه با تأیید صریح','detailed_extensions':'اجزای انتهایی مستند','confirmed':'بازبینی‌شده','needs_review':'نیازمند بازبینی',True:'بله',False:'خیر'}
REV={v:k for k,v in FA.items()}
ENUMS={'shape_kind','position','role','contact','kind','review_status','coverage','area_method','end_condition'}
def shown(k,v):return FA.get(v,v) if k in ENUMS and (isinstance(v,str) or type(v) is bool) else v
from core.takeoff.beam_detail import component_fingerprint as fingerprint, component_reviewed as reviewed

class BeamComponentEditor(QDialog):
 def __init__(self,kind,rows=None,parent=None,extra_fields=None,*,spiral_mode=False,spiral_column_diameter=None,circular_formwork_mode=False):
  super().__init__(parent);self.kind=kind;self.rows=None;self.spiral_mode=spiral_mode;self.spiral_column_diameter=spiral_column_diameter;self.circular_formwork_mode=circular_formwork_mode;self.fields=[f for f in SCHEMAS[kind] if not (spiral_mode and f[0]=='cut_length_m') and not (circular_formwork_mode and f[0]=='gross_area_m2')]+(extra_fields or [])+[('review_status','وضعیت بازبینی'),('reviewed_by','بازبین')];self.setWindowTitle('ویرایش ردیفی دیتایل ستون' if (spiral_mode or circular_formwork_mode) else 'ویرایش ردیفی دیتایل تیر');self.resize(1100,520);self.setLayoutDirection(Qt.RightToLeft);layout=QVBoxLayout(self)
  layout.addWidget(QLabel(('طول مارپیچ از گام، تعداد دور و قطر محور حساب می‌شود؛ انتهای بدون طول اضافه را صریح تأیید کنید. ' if spiral_mode else '')+'واحدها در سربرگ صریح‌اند؛ داده ناقص، عدد یا دیتایل حدسی مجاز نیست.'))
  self.table=QTableWidget(0,len(self.fields)+(1 if kind=='series' else 0));self.table.setHorizontalHeaderLabels([v for k,v in self.fields]+(['پیش‌نمایش وزن بر اساس تعداد سری؛ کیلوگرم'] if kind=='series' else []));layout.addWidget(self.table);self.reviewer=QLineEdit();self.reviewer.setPlaceholderText('نام بازبین صریح');layout.addWidget(self.reviewer);bar=QHBoxLayout();layout.addLayout(bar)
  self.add_button=QPushButton('افزودن');self.copy_button=QPushButton('کپی با شناسه جدید');self.delete_button=QPushButton('حذف ردیف منتخب');self.review_button=QPushButton('بازبینی ردیف منتخب');self.nested_button=QPushButton('جزئیات انتهایی مارپیچ' if spiral_mode else 'اجزای برش' if kind=='series' else 'کسورات سطح');self.save_button=QPushButton('انتقال به پیش‌نویس')
  for b in (self.add_button,self.copy_button,self.delete_button,self.review_button,self.nested_button,self.save_button):bar.addWidget(b)
  self.nested_button.setEnabled(kind in ('series','surfaces'));self.add_button.clicked.connect(lambda:self.add());self.copy_button.clicked.connect(self.copy);self.delete_button.clicked.connect(self.delete);self.review_button.clicked.connect(self.review);self.nested_button.clicked.connect(self.nested);self.save_button.clicked.connect(self.finish)
  self.total=QLabel();layout.addWidget(self.total);self.calculate_button=QPushButton('بازحساب وزن مستقل سری‌ها');layout.addWidget(self.calculate_button);self.calculate_button.setEnabled(kind=='series');self.calculate_button.clicked.connect(self.calculate)
  for r in rows or []:self.add(r)
 def add(self,row=None,*,index=None):
  r=deepcopy(row) if row is not None else {'id':'BD-'+uuid4().hex,'review_status':'needs_review'};i=self.table.rowCount() if index is None else index;self.table.insertRow(i)
  for j,(k,label) in enumerate(self.fields):self.table.setItem(i,j,QTableWidgetItem(str(shown(k,r.get(k,'')))))
  self.table.item(i,0).setData(Qt.UserRole,r);self.table.selectRow(i);self.table.setCurrentCell(i,0)
 def collect(self,i):
  old=deepcopy(self.table.item(i,0).data(Qt.UserRole) or {});r=deepcopy(old)
  for j,(k,label) in enumerate(self.fields):
   value=self.table.item(i,j).text().strip();value=REV.get(value,value) if k in ENUMS else value
   if k in old and str(shown(k,old[k]))==self.table.item(i,j).text().strip():value=old[k]
   if value!='':r[k]=value
   else:r.pop(k,None)
  if any(str(shown(k,old.get(k,'')))!=self.table.item(i,j).text().strip() for j,(k,label) in enumerate(self.fields) if k not in ('review_status','reviewed_by')):
   r['review_status']='needs_review';r.pop('review_digest',None);r.pop('approved_by',None)
  return r
 def selected(self):
  i=self.table.currentRow()
  if i<0:raise ValueError('ردیف را انتخاب کنید')
  return i
 def copy(self):
  try:
   r=self.collect(self.selected());r.update(id='BD-'+uuid4().hex,review_status='needs_review')
   r.pop('review_digest',None);r.pop('approved_by',None);r.pop('reviewed_by',None)
   # Nested parts and deductions have independent physical identities too.
   # Never reuse them when copying another physical bar or surface.
   for name in ('end_parts_m','length_parts_m','deductions'):
    for child in r.get(name,[]):
     if isinstance(child,dict):
      child['id']='BD-'+uuid4().hex
      for k in ('review_status','review_digest','reviewed_by','approved_by'):
       child.pop(k,None)
   self.add(r)
  except Exception as e:QMessageBox.warning(self,'کپی',str(e))
 def delete(self):
  if self.table.currentRow()>=0:self.table.removeRow(self.table.currentRow())
 def review(self):
  try:
   i=self.selected();r=self.collect(i);actor=self.reviewer.text().strip()
   if not actor or not r.get('source_ref'):raise ValueError('بازبین و مرجع دیتایل لازم‌اند')
   from core.commercial.exact_values import number
   required={'series':['count','nominal_diameter_mm','unit_weight_kg_m'],'sections':['end_m','width_m','depth_m'],'surfaces':['gross_area_m2'],'intersections':['volume_m3'],'face_deductions':['area_m2'],'parts':['length_m']}[self.kind]
   if self.kind=='surfaces' and self.circular_formwork_mode:required=[]
   for key in required:
    value=number(r.get(key),'ورودی '+key,True)
    if value<=0 or (key=='count' and value!=value.to_integral_value()):raise ValueError('مقدار مثبت و تعداد صحیح لازم است')
   if self.kind=='series':
    if self.spiral_mode:
     from core.takeoff.reviewed_structural import _reviewed_spiral_length
     from core.commercial.exact_values import number
     from core.takeoff.reviewed_components import require_text
     def checked(value,label,zero=False,integer=False):
      n=number(value,label,True)
      if n<0 or (not zero and n==0) or (integer and n!=n.to_integral_value()):raise ValueError(label)
      return n
     if r.get('count') not in ('1',1):raise ValueError('هر ناحیه مارپیچ یک قطعه مستقل دارد')
     _reviewed_spiral_length(r,checked(self.spiral_column_diameter,'قطر ستون'),check=checked,require=require_text)
     if not r.get('shape_ref') or not r.get('unit_weight_source'):raise ValueError('مرجع شکل و وزن واحد لازم است')
    else:
     for key in ('position','shape_ref','unit_weight_source','cut_length_ref'):
      if not r.get(key):raise ValueError('شکل، موقعیت و منابع وزن و برش باید صریح باشند')
     if r.get('length_parts_m'):
      for piece in r['length_parts_m']:reviewed(piece)
     elif number(r.get('cut_length_m'),'طول برش',True)<=0:raise ValueError('طول برش نامعتبر است')
   if self.kind=='surfaces':
    if type(r.get('contact')) is not bool or not r.get('role'):
     raise ValueError('نقش سطح و تماس با قالب را صریح ثبت کنید')
    if self.circular_formwork_mode:
     if r.get('role')!='curved_wall' or r.get('coverage')!='full_lateral' or r.get('area_method')!='circular_lateral' or 'gross_area_m2' in r:
      raise ValueError('قالب جانبی دایره‌ای باید از قطر و ارتفاع واقعی محاسبه شود')
   if self.kind=='sections' and number(r.get('start_m'),'شروع',True)>=number(r['end_m'],'پایان'):raise ValueError('مرز ناحیه نامعتبر است')
   r.update(review_status='confirmed' ,reviewed_by=actor,approved_by=actor);r['review_digest']=fingerprint(r);self.table.removeRow(i);self.add(r,index=i)
  except Exception as e:QMessageBox.warning(self,'بازبینی',str(e))
 def nested(self):
  try:
   i=self.selected();r=self.collect(i);key=('end_parts_m' if self.spiral_mode else 'length_parts_m' if self.kind=='series' else 'deductions');child=BeamComponentEditor('parts' if self.kind=='series' else 'face_deductions',r.get(key,[]),self)
   if child.exec()!=QDialog.DialogCode.Accepted:return
   r[key]=child.rows
   if self.kind=='series' and child.rows:r.pop('cut_length_m',None)
   if self.spiral_mode:r['end_condition']='detailed_extensions' if child.rows else 'no_extension_reviewed'
   r.update(review_status='needs_review');r.pop('review_digest',None);r.pop('approved_by',None);self.table.removeRow(i);self.add(r,index=i)
  except Exception as e:QMessageBox.warning(self,'جزئیات',str(e))
 def finish(self):
  try:
   rows=[self.collect(i) for i in range(self.table.rowCount())];ids=[r.get('id') for r in rows]
   if any(not i for i in ids) or len(ids)!=len(set(ids)):raise ValueError('شناسه خالی یا تکراری مجاز نیست')
   self.rows=rows;self.accept()
  except Exception as e:QMessageBox.warning(self,'دیتایل',str(e))

 def calculate(self):
  from core.takeoff.formulas import evaluate
  from core.commercial.exact_values import number,exact
  @exact
  def run():
   total=number(0,'جمع');missing=False
   for i in range(self.table.rowCount()):
    try:
     row=self.collect(i)
     cut=row.get('cut_length_m')
     if self.spiral_mode:
      from core.takeoff.reviewed_structural import _reviewed_spiral_length
      from core.takeoff.reviewed_components import require_text
      def check(v,label,zero=False,integer=False):
       n=number(v,label,True)
       if n<0 or (not zero and n==0) or (integer and n!=n.to_integral_value()):raise ValueError(label)
       return n
      _,_,cut=_reviewed_spiral_length(row,check(self.spiral_column_diameter,'قطر واقعی ستون'),check=check,require=require_text)
     if row.get('length_parts_m'):cut=evaluate('+'.join('p'+str(j) for j in range(len(row['length_parts_m']))),{'p'+str(j):v['length_m'] for j,v in enumerate(row['length_parts_m'])},variable_units={'p'+str(j):'m' for j in range(len(row['length_parts_m']))},output_unit='m')
     value=evaluate('count*cut*weight',{'count':row.get('count'),'cut':cut,'weight':row.get('unit_weight_kg_m')},variable_units={'count':'عدد','cut':'m','weight':'kg/m'},output_unit='kg');total+=number(value,'وزن');text=str(value)
    except ValueError:missing=True;text='نیازمند دیتایل معتبر'
    cell=QTableWidgetItem(text);cell.setFlags(cell.flags()&~Qt.ItemIsEditable);self.table.setItem(i,len(self.fields),cell)
   self.total.setText('جمع پیش‌نمایش سری‌ها: '+str(total)+' کیلوگرم'+('؛ ردیف ناقص وجود دارد، جمع قطعی نیست' if missing else '؛ تأیید و دامنه تکرار در فرم اصلی کنترل می‌شوند'))
  run()
