"""Documented stair report adapter; uses the four existing shared exporters only.

Report rows are informational snapshots, never takeoffs or payment authorization.
Engineering totals include unallocated operations; ownership is not project clearance.
"""
from decimal import Decimal
from core.commercial.exact_values import exact
from core.reports import exporters
from core.takeoff.stair_detail import POLICY,LABELS as OPERATIONS
from core.takeoff.stair_detail_fields import FIELDS,LABELS,CHOICES,TITLES
from core.takeoff.reviewed_aec import _id

@exact
def build(service,pid,floor,sid):
 record=service.get_aec_system(pid,'stair',floor,sid)
 if not record or record['data'].get('measurement_policy')!=POLICY:raise ValueError('پله تخصصی یافت نشد؛ تبدیل رکورد تاریخی مجاز نیست')
 data=record['data'];result=service.preview_aec_system(pid,'stair',floor,sid)
 if not result.get('engineering_ready'):raise ValueError('؛ '.join(result['blockers']))
 project=service.open_project(pid);dt=data['stair_detail'];e=dt['input'];rows=[]
 def add(description,**values):rows.append(dict(description=description,**values))
 for operation,value in result['totals_exact'].items():
  unit='m3' if operation.endswith('concrete') else 'm2' if operation=='formwork' else 'kg'
  add('جمع مهندسی؛ '+OPERATIONS.get(operation,'آرماتور')+'؛ غیرقابل پرداخت مستقل',quantity=value,unit=unit,notes='شامل عملیات فاقد مالکیت؛ مجوز ثبت مالی نیست')
 for unit,value in result.get('payable_totals_exact',{}).items():add('جمع دارای مالکیت؛ وابسته به مجوز گردش پروژه',quantity=value,unit=unit,notes='فقط عملیات تخصیص‌یافته؛ در جمع مهندسی دوباره اضافه نشود')
 if result['blockers']:add('ثبت مالی مسدود/نیازمند مدرک',notes='؛ '.join(result['blockers']))
 owned={(r['component'],r['params']['physical_component_id']) for r in result['rows']}
 for r in result['engineering_rows']:
  status='دارای مالکیت؛ وابسته به بازبینی و قفل مالی' if (r['operation'],r['physical_id']) in owned else 'مسدود/نیازمند مدرک مالکیت؛ خارج از پرداخت'
  add(OPERATIONS[r['operation']],quantity=r['quantity_exact'],unit=r['unit'],source=r['physical_id'],formula=r['formula'],notes=status+'؛ مرجع: '+r['source_ref'])
 # Typed input details retain every field and technical identity verbatim.
 for group,fields in FIELDS.items():
  for p in e[group]:
   values=[]
   for k in fields:
    v=p[k];v=dict(CHOICES.get(k,[])).get(v,v)
    if k=='group':
     from core.takeoff.stair_detail import BAR_LABELS
     v=BAR_LABELS.get(v,v)
    if isinstance(v,str) and len(v)>20 and all(ch in '0123456789.-+Ee' for ch in v):
     add(TITLES[group]+'؛ '+str(p.get('id',p.get('key','')))+'؛ '+LABELS[k],quantity=v)
    else:values.append(LABELS[k]+': '+str(v))
   add(TITLES[group]+'؛ دیتایل غیرقابل پرداخت مستقل',source=p.get('id',p.get('physical_id',p.get('key'))),notes='؛ '.join(values))
 for c in result['component_calculations']:
  names={'plan_area_m2':'مساحت پلان (مترمربع)','void_area_m2':'مساحت بازشو (مترمربع)','volume_gross_m3':'حجم ناخالص (مترمکعب)','volume_deduction_m3':'کسور حجم (مترمکعب)','volume_net_m3':'حجم خالص (مترمکعب)','sloped_length_m':'طول شیبدار (متر)','slope_angle_deg':'زاویه (درجه)','slope_direction':'جهت شیب'}
  for key,label in names.items():
   value=c[key]
   if value is not None:
    value=dict(CHOICES['direction']).get(value,value)
    add('محاسبات هندسی؛ '+c['component']+'؛ '+label+'؛ غیرقابل پرداخت مستقل',quantity=value)
 for name,label in [('input_document','مدرک دیتایل'),('ownership_document','مدرک مالکیت')]:
  doc=dt.get(name)
  if doc:
   add(label+'؛ مرجع',notes=doc['reference'])
   add(label+'؛ مسیر اصلی',quantity=doc['path'])
   add(label+'؛ SHA-256',quantity=doc['sha256'])
  else:add(label+'؛ مسدود/نیازمند مدرک',notes='مقدار نامعلوم؛ صفر تلقی نشده است')
 amendments=project.get('beam_amendments',{})
 for a in amendments.values():
  if a.get('beam_key')!=_id('stair',floor,sid):continue
  add('اصلاحیه '+{'draft':'درخواست‌شده','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[a['status']],source=a['id'],notes='علت: '+a['reason']+'؛ مرجع: '+a['evidence']['evidence_reference']+'؛ بازبین: '+a.get('review',{}).get('reviewer','نیازمند بازبینی'))
  add('مدرک اصلاحیه؛ SHA-256',quantity=a['evidence']['evidence_sha256'])
  from core.takeoff.stair_detail import preview
  old={r['source_id']:r for r in preview(a['previous']['data'],None)['rows']};new={r['source_id']:r for r in a['rows']}
  for source,delta in a['delta'].items():
   if Decimal(delta)==0:continue
   before=old.get(source);after=new.get(source);q=after['quantities'][0] if after else None
   add('اختلاف اصلاحیه؛ غیرقابل پرداخت مستقل',source=source,quantity=delta,unit=before['unit'] if before else q['unit'],notes='پیشین: '+str(before['quantity'] if before else 'فاقد ردیف')+'؛ جدید: '+str(q['amount'] if q else 'فاقد ردیف')+'؛ در جمع نسخه مؤثر دوباره اضافه نمی‌شود')
 for h in project.get('aec_system_history',[]):
  if _id('stair',floor,sid) in (h.get('source_key'),h.get('target_key')):add('تاریخچه '+{'copy':'کپی','delete_draft':'حذف پیش‌نویس'}.get(h['action'],h['action']),source=h.get('at',''),notes=h['reason'])
 # Vertical detail records give long evidence and exact numbers full width;
 # they are report information only and never ledger rows.
 flat=[]
 for r in rows:
  title=r['description']
  if r.get('unit'):title+=' ('+exporters.FA_UNITS.get(r['unit'],r['unit'])+')'
  if r.get('source'):title+='؛ '+str(r['source'])
  detail=str(r.get('notes',''))
  if 'quantity' in r:
   flat.append(dict(description=title,quantity=r['quantity']))
   if r.get('formula'):flat.append(dict(description='فرمول مستند ردیف پیشین؛ متن فنی اصلی',quantity=r['formula']))
   if detail:flat.append(dict(description='مدرک و وضعیت عملیات پیشین',quantity=detail))
  else:flat.append(dict(description=title,quantity=detail))
 rows=flat
 for i,r in enumerate(rows,1):r['item_no']=i
 reviewer=amendments.get(record.get('amendment_id'),{}).get('review',{}).get('reviewer') or data.get('roof_review',{}).get('reviewer','نیازمند بازبینی')
 metadata={'project_name':project['name'],'project_id':pid,'building_id':data['building_id'],'floor':floor,'member':sid,'revision':record['revision'],'reviewer':reviewer,'status':'قطعی' if record['status']=='committed' else 'پیش‌نویس','پلان':data['source']['plan_ref'],'دیتایل':data['source']['detail_ref'],'هویت فیزیکی':dt['physical_stair_id'],'محدوده':'بازوهای مستقیم و پاگردهای مستطیلی مستند؛ اشتراک نامعلوم مسدود؛ صحت هش معادل اصالت مهندسی نیست','مجوز مالی':'گزارش به‌تنهایی مجوز ثبت یا پرداخت نیست؛ جمع دارای مالکیت با جمع مهندسی جمع نشود'}
 return rows,metadata

def export(service,pid,floor,sid,path,*,format):
 functions={'pdf':exporters.export_pdf,'xlsx':exporters.export_xlsx,'docx':exporters.export_docx,'csv':exporters.export_csv}
 if format not in functions:raise ValueError('قالب گزارش نامعتبر است')
 rows,metadata=build(service,pid,floor,sid)
 options={'landscape':True} if format=='docx' else {}
 summary={'amount_by_group':{r['description']:r['quantity'] for r in rows if r['description'].startswith(('جمع مهندسی','جمع دارای مالکیت'))}}
 return functions[format](rows,path,**options,summary=summary,title='ریزمتره تخصصی پله بتنی و پاگرد',metadata=metadata,columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار دقیق یا دیتایل مستند')])
