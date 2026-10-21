"""Thin source/version detail adapter over existing report exporters."""
from core.takeoff.beam_detail import BAR_LABELS
from core.reports.exporters import export_pdf,export_xlsx,export_docx,export_csv

LABELS={'segments':'سری میلگرد','sections':'ناحیه مقطع','surfaces':'سطح قالب','id':'شناسه','count':'تعداد','length':'طول','unit_weight':'وزن واحد','source_ref':'مرجع دیتایل','unit_weight_source':'مرجع وزن واحد','cut':'جزئیات طول برش','cut_length_m':'طول برش متر','cut_length_ref':'مرجع طول برش','nominal_diameter_mm':'قطر میلی‌متر','position':'موقعیت','member_count':'تعداد تیرها','count_scope':'دامنه تعداد','area_scope':'دامنه قالب','gross_m3':'بتن ناخالص متر مکعب','deductions_m3':'کسورات متر مکعب','variable_units':'واحد ورودی','net_area_m2':'مساحت خالص قالب','section_width_m':'عرض خاموت متر','section_depth_m':'ارتفاع خاموت متر','section_ref':'مرجع مقطع','shape_ref':'مرجع شکل','shape_kind':'شکل','start_m':'شروع متر','end_m':'پایان متر','width':'عرض','depth':'ارتفاع','volume_m3':'حجم متر مکعب','approved_by':'بازبین','intersections':'کسورات اتصال','first_bar_m':'اولین خاموت متر','last_bar_m':'آخرین خاموت متر','spacing_m':'فاصله متر','name':'نام ناحیه','deduction_scope':'دامنه کسورات'}
LABELS.update({'evidence_path':'مسیر مدرک','evidence_sha256':'هش مدرک','evidence_reference':'مرجع مستقل مدرک','version':'نسخه مهاجرت','from_policy':'قرارداد قبلی','to_policy':'قرارداد مقصد','gross_area_m2':'مساحت ناخالص قالب','role':'نقش سطح','contact':'تماس واقعی با قالب','deductions':'کسورات سطح','area_m2':'مساحت متر مربع','review_status':'وضعیت بازبینی','reviewed_by':'بازبین مستقل','review_digest':'هش بازبینی','length_parts_m':'اجزای طول برش','kind':'نوع جزء','length_m':'طول متر','width_m':'عرض متر','depth_m':'عمق متر'})
VALUES={'draft':'پیش‌نویس','reviewed':'بازبینی‌شده','applied':'اعمال‌شده','confirmed':'تأییدشده','needs_review':'نیازمند بازبینی','bottom_face':'کف','side1':'جان اول','side2':'جان دوم','end':'انتها','other':'سایر','straight':'مستقیم','hook':'قلاب','bend':'خم','lap':'وصله','anchorage':'مهاری','per_member':'هر تیر هم‌تیپ','total_group':'کل گروه','top':'بالا','bottom':'پایین','span':'دهانه','support':'تکیه‌گاه','side':'کمرکش','crosstie':'سنجاقی','stirrup':'خاموت','rectangular':'مستطیلی','m':'متر','m2':'متر مربع','m3':'متر مکعب','kg':'کیلوگرم','kg/m':'کیلوگرم بر متر','عدد':'عدد'}
def export(service,pid,floor,beam,path,*,format):
 report=service.preview_beam_detail(pid,floor,beam);record=service.get_beam_detail(pid,floor,beam)
 if not report['ready']:raise ValueError('گزارش نهایی تیر ناقص مسدود است؛ دیتایل‌ها را کامل کنید')
 rows=[]
 def add(component,field,value):rows.append({'component':component,'field':field,'value':str(VALUES.get(value,value) if isinstance(value,str) else value)})
 def walk(component,path,value):
  if isinstance(value,dict):
   for key,v in value.items():walk(component,path+' / '+LABELS.get(key,key),v)
  elif isinstance(value,list):
   for i,v in enumerate(value,1):walk(component,path+' '+str(i),v)
  else:add(component,path,value)
 for row in report['rows']:
  component=row['description'];add(component,'مقدار دقیق',row['quantity']);add(component,'واحد',row['unit']);add(component,'فرمول',row['formula']);add(component,'منبع',row['source_id']);walk(component,'جزئیات',row['params'])
 project=service.open_project(pid)
 for a in project.get('beam_amendments',{}).values():
  if a.get('kind') in ('legacy_link','column_amendment'):continue
  if a['proposal']['floor_id']==floor and a['proposal']['beam_id']==beam:
   add('اصلاحیه','شناسه',a['id']);add('اصلاحیه','علت',a['reason']);add('اصلاحیه','سازنده',a['created_by']);add('اصلاحیه','بازبین',a.get('review',{}).get('reviewer','بررسی نشده'));walk('اصلاحیه','دلتا',a['delta']);walk('اصل','دیتایل پیشین',a['previous']['data']);add('اصلاحیه','وضعیت',a['status'])
   if a.get('migration'):walk('مهاجرت تاریخی','مدرک و قرارداد',a['migration'])
 source=record['data']['source'];add('منابع','پلان',source.get('plan_ref','تاریخی؛ ثبت نشده'));add('منابع','دیتایل',source.get('detail_ref','تاریخی؛ ثبت نشده'));add('منابع','شناسه برداشت',source['source_id']);add('وضعیت','نسخه',record['revision']);add('وضعیت','ثبت','قطعی' if report['committed'] else 'پیش‌نویس بازبینی‌شده اجزا؛ سند مالی نیست')
 fn={'xlsx':export_xlsx,'pdf':export_pdf,'docx':export_docx,'csv':export_csv}.get(format)
 if fn is None:raise ValueError('قالب گزارش تیر معتبر نیست')
 if format=='xlsx':
  from pathlib import Path
  from tempfile import TemporaryDirectory
  from openpyxl import load_workbook
  destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True)
  with TemporaryDirectory(dir=destination.parent) as folder:
   temp=Path(folder)/'beam.xlsx';fn(rows,temp,title='ریزمتره مستند تیر '+beam,columns=[('component','جزء تیر'),('field','عنوان'),('value','مقدار و مرجع')])
   book=load_workbook(temp)
   book.save(destination)
  return destination
 return fn(rows,path,title='ریزمتره مستند تیر '+beam,columns=[('component','جزء تیر'),('field','عنوان'),('value','مقدار و مرجع')])
