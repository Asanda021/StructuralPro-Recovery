"""Shear-wall rows for the existing four shared exporters; no new exporter."""
from decimal import Decimal
from core.reports.exporters import export_pdf,export_xlsx,export_docx,export_csv
from core.takeoff.shear_wall_detail import preview,POLICY,BAR_LABELS
from core.takeoff.reviewed_aec import _id
from core.commercial.exact_values import exact

@exact
def export(service,pid,floor,sid,path,*,format):
 record=service.get_aec_system(pid,'shear_wall',floor,sid)
 if not record or record['data'].get('measurement_policy')!=POLICY:raise ValueError('دیوار برشی تخصصی یافت نشد')
 data=record['data'];result=service.preview_aec_system(pid,'shear_wall',floor,sid)
 if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
 rows=[];totals={};detail=data['shear_wall_detail'];e=detail['input']
 for r in result['rows']:
  notes='هویت جزء: '+r['params']['physical_component_id']+'؛ مراجع: '+'، '.join(r['params']['source_refs'])
  notes+='؛ هش دیتایل: '+detail['input_document']['sha256']+'؛ هش مالکیت: '+detail['ownership_document']['sha256']
  rows.append(dict(description=r['description'],quantity=r['quantity'],unit=r['unit'],source=r['source_id'],formula=r['formula'],notes=notes))
  totals[r['unit']]=totals.get(r['unit'],Decimal(0))+Decimal(r['quantity'])
 from core.takeoff.shear_wall_specialist_chat import preview as engine_preview
 for v in engine_preview(e)['rows']:
  if v['kind'] in ('concrete_gross','concrete_opening_deduction','concrete_interface_deduction'):
   rows.append(dict(description={'concrete_gross':'حجم ناخالص بتن؛ اطلاعات محاسبه','concrete_opening_deduction':'کسر بازشوی مستند؛ اطلاعات محاسبه','concrete_interface_deduction':'کسر اشتراک؛ اطلاعات محاسبه'}[v['kind']],quantity=v['quantity'],unit=v['unit'],source=v['physical_id'],formula=v['formula'],notes='غیرقابل پرداخت مستقل؛ مراجع: '+'، '.join(v['source_refs'])))
 fields={'id':'شناسه قطعه','physical_part_id':'هویت فیزیکی قطعه','x_m':'مختصات طولی (متر)','y_m':'مختصات عرضی (متر)','z_m':'تراز (متر)','length_m':'طول (متر)','height_m':'ارتفاع (متر)','thickness_m':'ضخامت (متر)','width_m':'عرض (متر)','segment_id':'قطعه مرتبط','approved_by':'تأییدکننده','source_ref':'مرجع','count':'تعداد مستند','diameter_mm':'قطر (میلی‌متر)','unit_weight_kg_m':'وزن واحد طول','cut_length_m':'طول برش (متر)','unit_weight_source':'مرجع وزن واحد','physical_bar_set_id':'هویت سری میلگرد'}
 for title,parts in [('هندسه مستند قطعات',e['segments']),('بازشو و کسورات مستند',e['openings'])]+[(BAR_LABELS[k],g.get('series',[])) for k,g in e['rebars'].items()]:
  for p in parts:
   notes='؛ '.join(fields[k]+': '+str(v) for k,v in p.items() if k in fields)
   if p.get('cut_parts'):notes+='؛ اجزای طول برش: '+'؛ '.join({'straight':'مستقیم','bend':'خم','hook':'قلاب','lap':'وصله','anchorage':'مهاری','other':'جزء مستند دیگر'}.get(x['kind'],x['kind'])+': '+str(x['length_m']) for x in p['cut_parts'])
   rows.append(dict(description=title+'؛ اطلاعات غیرقابل پرداخت مستقل',source=p.get('id'),notes=notes))
 for key,group in e['rebars'].items():
  if group['status']=='not_applicable':rows.append(dict(description=BAR_LABELS[key]+'؛ عدم کاربرد مستند',source=group['source_ref'],notes=group['reason']+'؛ تأییدکننده: '+group['approved_by']))
 for face in e['formwork']['main_faces']+e['formwork']['edge_faces']:
  if face['status']=='not_required':rows.append(dict(description='قالب وجه؛ عدم نیاز مستند',source=face['id'],notes=face['reason']+'؛ مرجع: '+face['source_ref']+'؛ مبنای پرداخت: '+face['payment_ref']))
 project=service.open_project(pid)
 for a in project.get('beam_amendments',{}).values():
  if a.get('beam_key')!=_id('shear_wall',floor,sid):continue
  rows.append(dict(description='اصلاحیه '+{'draft':'درخواست‌شده','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[a['status']],source=a['id'],notes='علت: '+a['reason']+'؛ مدرک: '+a['evidence']['evidence_reference']+'؛ هش: '+a['evidence']['evidence_sha256']+'؛ بازبین: '+a.get('review',{}).get('reviewer','نیازمند بازبینی')))
  old={r['source_id']:r for r in preview(a['previous']['data'],None)['rows']};new={r['source_id']:r for r in a['rows']}
  for source,delta in a['delta'].items():
   before=old.get(source);after=new.get(source);rows.append(dict(description='اختلاف اصلاحیه؛ غیرقابل پرداخت مستقل',quantity=delta,unit=before['unit'] if before else after['quantities'][0]['unit'],source=source,notes='پیشین: '+str(before['quantity'] if before else 'فاقد ردیف')+'؛ پیشنهادی: '+str(after['quantities'][0]['amount'] if after else 'فاقد ردیف')+'؛ در جمع نسخه مؤثر دوباره اضافه نمی‌شود'))
 for i,r in enumerate(rows,1):r['item_no']=i
 reviewer=project.get('beam_amendments',{}).get(record.get('amendment_id'),{}).get('review',{}).get('reviewer') or data.get('roof_review',{}).get('reviewer','نیازمند بازبینی')
 metadata={'project_name':project['name'],'building_id':data['building_id'],'floor':floor,'member':sid,'محور':data['axis'],'revision':record['revision'],'status':'قطعی' if record['status']=='committed' else 'پیش‌نویس','source':data['source']['source_id'],'پلان':data['source']['plan_ref'],'دیتایل':data['source']['detail_ref'],'بازبین':reviewer,'محدوده پذیرش':'قطعات مستطیلی مستقل؛ اشتراک با اعضای دیگر مسدود؛ صحت هش معادل اصالت مهندسی نیست'}
 exporters={'pdf':export_pdf,'xlsx':export_xlsx,'docx':export_docx,'csv':export_csv}
 if format not in exporters:raise ValueError('قالب خروجی نامعتبر است')
 return exporters[format](rows,path,title='ریزمتره تخصصی دیوار برشی',metadata=metadata,summary={'amount_by_group':{k:f'{v:f}' for k,v in totals.items()}},columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار'),('unit','واحد'),('source','منبع'),('formula','فرمول'),('notes','مدارک و دیتایل')])
