"""Identity-only legacy mapping report through existing safe exporters."""
from core.reports.exporters import export_pdf,export_xlsx
from core.takeoff.manual_formula_amendments import read,mapping_inventory

LABELS={'source_id':'شناسه منبع','project_id':'پروژه','floor_id':'طبقه مقصد','beam_id':'تیر مقصد','plan_ref':'مرجع پلان','detail_ref':'مرجع دیتایل','revision':'نسخه','member_code':'عضو اولیه','system':'طبقه اولیه','unit':'واحد','amount':'مقدار دقیق','code':'نوع عملیات','evidence_path':'فایل مدرک','evidence_sha256':'هش مدرک','evidence_reference':'مرجع مستقل','created_by':'سازنده','reviewer':'بازبین','note':'یادداشت','reason':'علت','description':'شرح اولیه'}
STATUS={'LINKED':'متصل معتبر','NEEDS_MAPPING':'نیازمند نگاشت','AMBIGUOUS':'ارتباط مبهم','SOURCE_DUPLICATE':'منبع تکراری','INCOMPLETE':'اطلاعات ناقص','FINANCIAL_LOCKED':'مبنای مالی قفل‌شده','draft':'پیشنهاد','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}

def export(service,pid,path,*,format):
 project,_=read(service,pid);rows=[]
 def walk(source,label,value):
  if isinstance(value,dict):
   for key,v in value.items():walk(source,label+' / '+LABELS.get(key,key),v)
  elif isinstance(value,list):
   for i,v in enumerate(value,1):walk(source,label+' '+str(i),v)
  else:rows.append({'source':source,'field':label,'value':STATUS.get(str(value),str(value))})
 for r in mapping_inventory(project):
  source=str(r['source_id']);walk(source,'وضعیت',r['status']);walk(source,'مبنای مالی قفل‌شده',r['financial_locked']);walk(source,'نیاز به مدرک واقعی',r['evidence_required']);walk(source,'علت انسداد',r['blockers']);walk(source,'اصل رکورد',r['original']);walk(source,'تیر مقصد',r['target']);walk(source,'مدرک و بازبینی',project.get('beam_amendments',{}).get(r['mapping_id'],{}));walk(source,'نیازمند اطلاعات','اجزای گمشده نیازمند دیتایل؛ نگاشت کمیت تازه تولید نمی‌کند')
 fn={'xlsx':export_xlsx,'pdf':export_pdf}.get(format)
 if fn is None:raise ValueError('قالب گزارش نگاشت نامعتبر است')
 kwargs={'title':'گزارش نگاشت تاریخی تیر؛ اصل کمیت محفوظ','columns':[('source','منبع'),('field','عنوان'),('value','مقدار و مرجع')]}
 if format=='xlsx':
  from pathlib import Path
  from tempfile import TemporaryDirectory
  from openpyxl import load_workbook
  destination=Path(path);destination.parent.mkdir(parents=True,exist_ok=True)
  with TemporaryDirectory(dir=destination.parent) as folder:
   temporary=Path(folder)/'mapping.xlsx';fn(rows,temporary,**kwargs);book=load_workbook(temporary)
   for sheet in book:
    for cells in sheet:
     for cell in cells:
      if cell.value is not None:cell.value=str(cell.value);cell.data_type='s'
   book.save(destination)
  return destination
 return fn(rows,path,**kwargs)
