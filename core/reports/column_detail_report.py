"""Column detail adapter through existing Persian PDF/Excel exporters."""
from core.reports.exporters import export_pdf,export_xlsx
from core.reports.beam_legacy_mapping_report import LABELS,STATUS

LABELS={**LABELS,'building_id':'ساختمان','axis':'محور','gross_m3':'بتن ناخالص','net_m3':'بتن خالص','series':'سری میلگرد','surfaces':'سطوح قالب','geometry':'هندسه','intersections':'کسورات','width':'عرض','depth':'عمق','height':'ارتفاع','count':'تعداد','gross_area_m2':'قالب ناخالص','unit_weight_kg_m':'وزن واحد مستند','cut_length_m':'طول برش','nominal_diameter_mm':'قطر میلی‌متر','diameter':'قطر ستون، متر','curved_wall':'قالب جانبی منحنی','axis_diameter_m':'قطر محور مارپیچ، متر','pitch_m':'گام مارپیچ، متر','turns':'تعداد دور مستند','cover_m':'پوشش واقعی، متر','start_m':'آغاز ناحیه، متر','end_m':'پایان ناحیه، متر','end_parts_m':'اجزای انتهایی مستند','end_condition':'قرارداد انتهایی','end_condition_ref':'مرجع جزئیات انتهایی','helix_length_policy':'سیاست دقت محاسبه طول مارپیچ','pi_policy':'سیاست عددی پی','count_scope':'دامنه تعداد','shape_kind':'شکل خاموت','coverage':'پوشش سطح','area_method':'روش محاسبه سطح','cut_length_ref':'مرجع طول برش','source_ref':'مرجع دیتایل'}

LABELS.update({'approved_by':'بازبین دیتایل','intersection_scope':'دامنه کسورات','intersection_ref':'مرجع کسورات','repeat_scope':'دامنه تکرار','variable_units':'واحد ابعاد','length':'طول','thickness':'ضخامت','deductions_m3':'حجم کسورات','volume_m3':'حجم کسر','area_m2':'مساحت کسر','contact':'تماس قالب','shape':'هندسه','id':'شناسه','status':'وضعیت','longitudinal':'میلگرد طولی','stirrups':'خاموت شناژ','bottom_x':'تحتانی راستای یک','bottom_y':'تحتانی راستای دو','top_x':'فوقانی راستای یک','top_y':'فوقانی راستای دو','additional':'تقویتی','crossties':'سنجاقی','starters':'انتظار','rebars':'میلگردها','source':'منشأ','source_id':'شناسه منبع','plan_ref':'مرجع نقشه','detail_ref':'مرجع دیتایل','measurement_policy':'قرارداد محاسبات','kind':'نوع عضو','floor_id':'طبقه','member_id':'شناسه عضو','reason':'علت','mode':'روش ورود','count_scope_ref':'مرجع دامنه شمارش','area_scope':'دامنه قالب','area_scope_ref':'مرجع دامنه قالب','deductions':'کسورات','segments':'گروه میلگرد','reviewer':'بازبین مستقل','note':'یادداشت بازبینی','digest':'اثر انگشت بازبینی','evidence_path':'مسیر مدرک','evidence_sha256':'هش مدرک','evidence_reference':'مرجع مدرک','cut_length_ref':'مرجع برش','first_bar_m':'موقعیت خاموت اول','last_bar_m':'موقعیت خاموت آخر','spacing_m':'گام خاموت','shape_ref':'مرجع شکل برش'})

VALUE_NAMES={**STATUS,'spiral':'مارپیچ','circular_column':'ستون دایره‌ای','full_lateral':'سطح جانبی کامل','circular_lateral':'محاسبه جانبی دایره‌ای','detailed_extensions':'افزودنی‌های انتهایی مستند','no_extension_reviewed':'بدون طول اضافی با تأیید صریح','per_member':'برای هر عضو','total_group':'برای کل گروه','identical_members':'اعضای هم‌تیپ','rectangular':'منشوری مستطیلی','foundation_tie_specialist_v1':'قرارداد تخصصی پی و شناژ، نسخه یک','manual':'ورود دستی','m':'متر','cm':'سانتی‌متر','mm':'میلی‌متر','True':'بله','False':'خیر'}

def export(service,pid,floor,member,path,*,format,kind="column"):
 from core.takeoff.reviewed_structural import KINDS
 VALUE_NAMES.update({k:v[0] for k,v in KINDS.items()})
 r=service.preview_structural_member(pid,kind,floor,member)
 if not r['ready']:raise ValueError('گزارش نهایی ستون ناقص مسدود است')
 record=service.get_structural_member(pid,kind,floor,member);rows=[]
 def walk(component,label,value):
  if isinstance(value,dict):
   for k,v in value.items():walk(component,label+' / '+LABELS.get(k,k),v)
  elif isinstance(value,list):
   for i,v in enumerate(value,1):walk(component,label+' '+str(i),v)
  else:rows.append({'component':component,'field':label,'value':str(VALUE_NAMES.get(str(value),value))})
 for q in r['rows']:
  description=q['description']
  if kind!='column':
   for key in ('longitudinal','stirrups','bottom_x','bottom_y','top_x','top_y','additional','crossties','starters'):description=description.replace(key,LABELS[key])
  q={**q,'description':description}
  walk(q['description'],'مقدار دقیق',q['quantity']);walk(q['description'],'واحد',{'m3':'متر مکعب','m2':'متر مربع','kg':'کیلوگرم'}[q['unit']]);walk(q['description'],'فرمول',q['formula']);walk(q['description'],'منبع',q['source_id']);walk(q['description'],'جزئیات',q['params'])
 walk('هویت و منشأ','نسخه',record['revision']);walk('هویت و منشأ','منبع اصلی',record['data']['source'])
 for a in service.open_project(pid).get('beam_amendments',{}).values():
  if a.get('kind') in ('column_amendment','foundation_amendment') and a['proposal'].get('kind')==kind and a['proposal']['floor_id']==floor and a['proposal']['member_id']==member:
   walk('اصل عضو','دیتایل قبلی',a['previous']['data']);walk('اصلاحیه','دلتا',a['delta']);walk('اصلاحیه','علت',a['reason']);walk('اصلاحیه','بازبینی',a.get('review',{}));walk('اصلاحیه','وضعیت',a['status']);walk('اصلاحیه','مدرک جدید',a.get('evidence',{}))
 from core.takeoff.reviewed_structural import KINDS
 title=KINDS[kind][0]
 walk('هویت و منشأ','نوع عضو',title);walk('هویت و منشأ','شناسه عضو',member);walk('هویت و منشأ','طبقه',floor)
 kwargs={'title':'ریزمتره مستند '+title+' '+member,'columns':[('component','جزء عضو'),('field','عنوان'),('value','مقدار و مرجع')]}
 if format=='pdf':return export_pdf(rows,path,**kwargs,fill_width=kind!='column')
 if format!='xlsx':raise ValueError('قالب گزارش نامعتبر')
 from pathlib import Path
 from tempfile import TemporaryDirectory
 from openpyxl import load_workbook
 destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True)
 with TemporaryDirectory(dir=destination.parent) as folder:
  temporary=Path(folder)/'column.xlsx';export_xlsx(rows,temporary,**kwargs);book=load_workbook(temporary)
  for sheet in book:
   for row in sheet:
    for cell in row:
     if cell.value is not None:cell.value=str(cell.value);cell.data_type='s'
  book.save(destination)
 return destination
