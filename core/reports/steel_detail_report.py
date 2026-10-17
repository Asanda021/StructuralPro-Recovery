"""Steel adapter to the four shared Persian exporters, no separate exporter."""
from decimal import Decimal
from core.takeoff.steel_detail import preview,POLICY,LABELS
from core.takeoff.reviewed_aec import SPECS,_id
from core.commercial.exact_values import exact,wire
from core.reports.exporters import export_pdf,export_xlsx,export_docx,export_csv
FIELD_LABELS={'id':'شناسه قطعه','physical_key':'هویت فیزیکی','source_ref':'مرجع','approved_by':'تأییدکننده','count':'تعداد','length_m':'طول برش (متر)','width_m':'عرض (متر)','thickness_m':'ضخامت (متر)','unit_weight_kg_m':'وزن واحد طول (کیلوگرم بر متر)','unit_weight_source':'گواهی وزن واحد','section_ref':'مشخصات مقطع','steel_ref':'مشخصات فولاد','scope_ref':'دامنه تأمین یا اجرا','cut_ref':'دیتایل طول برش','x':'ابتدای طول','y':'ابتدای عرض','z':'تراز','density_kg_m3':'چگالی مستند (کیلوگرم بر متر مکعب)','density_source':'مرجع چگالی','unit_mass_kg':'جرم واحد مجموعه (کیلوگرم)','mass_source':'گواهی جرم','spec_ref':'مشخصات فنی','payment_basis':'مبنای پرداخت','method_ref':'روش اجرا','quantity':'مقدار مستقل','unit':'واحد','operation':'نوع عملیات','basis_ref':'مبنای قراردادی','effective_width_m':'عرض مؤثر (متر)','nominal_width_m':'عرض اسمی (متر)','side_lap_m':'هم‌پوشانی عرضی (متر)','end_lap_m':'هم‌پوشانی طولی (متر)','unit_weight_kg_m2':'وزن بر مساحت اسمی (کیلوگرم بر متر مربع)','weight_source':'گواهی وزن','topping_m':'ضخامت رویه (متر)','flute_depth_m':'عمق شیار (متر)','flute_top_m':'عرض بالای شیار (متر)','flute_bottom_m':'عرض پایین شیار (متر)','pitch_m':'گام شیار (متر)','profile_ref':'مرجع مقطع ذوزنقه‌ای'}
@exact
def export(service,pid,kind,floor,sid,path,*,format):
 record=service.get_aec_system(pid,kind,floor,sid)
 if not record or record['data'].get('measurement_policy')!=POLICY:raise ValueError('عضو تخصصی فولاد یافت نشد')
 data=record['data'];result=preview(data,service.takeoff)
 if not result['ready']:raise ValueError('؛ '.join(result['blockers']))
 rows=[];totals={}
 for v in result['rows']:
  notes='؛ '.join(FIELD_LABELS[k]+': '+str({'count':'تعداد مجموعه کامل','kg':'کیلوگرم','fabrication':'ساخت','erection':'نصب','surface_preparation':'آماده‌سازی سطح'}.get(x,x)) for k,x in v['params'].items() if k in FIELD_LABELS)
  notes+='؛ '+('قابل پرداخت مستقل' if v['role']=='work' else 'اطلاعات مصالح؛ غیرقابل پرداخت مستقل')
  rows.append(dict(description=v['description'],quantity=v['quantity'],unit=v['unit'],source=v['source_id'],formula=v['formula'],notes=notes))
  label=v['description'].removesuffix(' '+sid)+' ('+v['unit']+')؛ '+('عملیات' if v['role']=='work' else 'مصالح اطلاعاتی');totals[label]=totals.get(label,Decimal(0))+Decimal(str(v['quantity']))
 for group,part in data['steel_detail']['groups'].items():
  if part['status']=='not_applicable':rows.append(dict(description=LABELS[group]+'؛ عدم کاربرد مستند',notes=part['reason']+'؛ مرجع: '+part['source_ref']+'؛ تأییدکننده: '+part['approved_by']))
 project=service.open_project(pid)
 for a in project.get('beam_amendments',{}).values():
  if a.get('beam_key')!=_id(kind,floor,sid):continue
  rows.append(dict(description='اصلاحیه '+{'draft':'درخواست‌شده','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[a['status']],source=a['id'],notes='علت: '+a['reason']+'؛ مدرک: '+a['evidence']['evidence_reference']+'؛ هش: '+a['evidence']['evidence_sha256']+'؛ بازبین: '+a.get('review',{}).get('reviewer','نیازمند بازبینی')))
  old={v['source_id']:v for v in preview(a['previous']['data'],service.takeoff)['rows']};new={v['source_id']:v for v in a['rows']}
  for source,delta in a['delta'].items():
   before=old.get(source,{});after=new.get(source,{});rows.append(dict(description='اختلاف مقدار اصلاحیه؛ غیرقابل پرداخت مستقل',source=source,quantity=delta,unit=before.get('unit') or after.get('quantities',[{}])[0].get('unit',''),notes='پیشین: '+str(before.get('quantity',0))+'؛ پیشنهادی: '+str(after.get('quantities',[{'amount':0}])[0]['amount'])+'؛ اختلاف: '+str(delta)+'؛ در جمع نسخه مؤثر دوباره اضافه نمی‌شود'))
 for i,row in enumerate(rows,1):row['item_no']=i
 rv=project.get('beam_amendments',{}).get(record.get('amendment_id'),{}).get('review',{}).get('reviewer') or data.get('roof_review',{}).get('reviewer','نیازمند بازبینی')
 metadata={'project_name':project['name'],'building_id':data['building_id'],'floor':floor,'member':sid,'محور':data['axis'],'revision':record['revision'],'status':'قطعی' if record['status']=='committed' else 'پیش‌نویس','source':data['source']['source_id'],'پلان':data['source']['plan_ref'],'دیتایل':data['source']['detail_ref'],'بازبین':rv}
 exporters={'pdf':export_pdf,'xlsx':export_xlsx,'docx':export_docx,'csv':export_csv}
 if format not in exporters:raise ValueError('قالب خروجی نامعتبر است')
 return exporters[format](rows,path,title='ریزمتره تخصصی '+SPECS[kind].title,metadata=metadata,summary={'amount_by_group':wire(totals)},columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار'),('unit','واحد'),('source','منبع'),('formula','فرمول'),('notes','مدارک و دیتایل')])
