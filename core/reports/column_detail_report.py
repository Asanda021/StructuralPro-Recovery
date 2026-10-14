"""Column detail adapter through existing Persian PDF/Excel exporters."""
from core.reports.exporters import export_pdf,export_xlsx
from core.reports.beam_legacy_mapping_report import LABELS,STATUS

LABELS={**LABELS,'building_id':'ساختمان','axis':'محور','gross_m3':'بتن ناخالص','net_m3':'بتن خالص','series':'سری میلگرد','surfaces':'سطوح قالب','geometry':'هندسه','intersections':'کسورات','width':'عرض','depth':'عمق','height':'ارتفاع','count':'تعداد','gross_area_m2':'قالب ناخالص','unit_weight_kg_m':'وزن واحد مستند','cut_length_m':'طول برش','nominal_diameter_mm':'قطر میلی‌متر'}

def export(service,pid,floor,member,path,*,format):
 r=service.preview_structural_member(pid,'column',floor,member)
 if not r['ready']:raise ValueError('گزارش نهایی ستون ناقص مسدود است')
 record=service.get_structural_member(pid,'column',floor,member);rows=[]
 def walk(component,label,value):
  if isinstance(value,dict):
   for k,v in value.items():walk(component,label+' / '+LABELS.get(k,k),v)
  elif isinstance(value,list):
   for i,v in enumerate(value,1):walk(component,label+' '+str(i),v)
  else:rows.append({'component':component,'field':label,'value':str(STATUS.get(str(value),value))})
 for q in r['rows']:
  walk(q['description'],'مقدار دقیق',q['quantity']);walk(q['description'],'واحد',{'m3':'متر مکعب','m2':'متر مربع','kg':'کیلوگرم'}[q['unit']]);walk(q['description'],'فرمول',q['formula']);walk(q['description'],'منبع',q['source_id']);walk(q['description'],'جزئیات',q['params'])
 walk('هویت و منشأ','نسخه',record['revision']);walk('هویت و منشأ','منبع اصلی',record['data']['source'])
 for a in service.open_project(pid).get('beam_amendments',{}).values():
  if a.get('kind')=='column_amendment' and a['proposal']['floor_id']==floor and a['proposal']['member_id']==member:
   walk('اصل ستون','دیتایل قبلی',a['previous']['data']);walk('اصلاحیه','دلتا',a['delta']);walk('اصلاحیه','علت',a['reason']);walk('اصلاحیه','بازبینی',a.get('review',{}));walk('اصلاحیه','وضعیت',a['status'])
 kwargs={'title':'ریزمتره مستند ستون '+member,'columns':[('component','جزء ستون'),('field','عنوان'),('value','مقدار و مرجع')]}
 if format=='pdf':return export_pdf(rows,path,**kwargs)
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
