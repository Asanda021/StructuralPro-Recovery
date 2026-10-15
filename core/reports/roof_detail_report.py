"""Thin roof adapter over the four existing shared exporters."""
from decimal import Decimal
from core.commercial.exact_values import wire,exact
from core.reports.exporters import export_pdf,export_xlsx,export_docx,export_csv
from core.takeoff.roof_detail import preview,POLICY,LABELS,HOLLOW_KIND
from core.takeoff.reviewed_aec import SPECS,_id


@exact
def export(service,pid,kind,floor,sid,path,*,format):
 record=service.get_aec_system(pid,kind,floor,sid)
 if not record or record['data'].get('measurement_policy')!=POLICY:raise ValueError('سقف تخصصی موجود نیست')
 d=record['data'];result=preview(d,service.takeoff)
 if not result['ready']:raise ValueError('گزارش قطعی برای داده ناقص مجاز نیست؛ '+'؛ '.join(result['blockers']))
 rows=[]
 for v in result['rows']:
  params=v['params'];notes='ورودی‌ها برای هر سقف هم‌تیپ؛ مرجع: '+str(v['source_ref'])+'؛ نقش: '+('عملیات قابل پرداخت مستقل' if v['role']=='work' else ('قطعات قالب وافل؛ بدون استنتاج سطح تماس یا نرخ مالی' if v['item_code']=='waffle_molds' else 'مصالح داخل تیرچه خریداری‌شده؛ غیرقابل پرداخت مستقل'))
  if kind==HOLLOW_KIND and v['role']!='work':notes='ورودی مستند هر سقف هم‌تیپ؛ غیرقابل پرداخت مستقل؛ مرجع: '+str(v['source_ref'])
  if 'panel' in params:
   p=params['panel'];notes+='؛ قطعه: '+p['id']+'؛ مقطع: '+p['spec_ref']+'؛ مدرک قطعه نهایی: '+p['fabrication_ref']+'؛ حجم حفره (متر مکعب): '+str(p['void_volume_m3'])+'؛ منبع حفره: '+p['void_source_ref']
   for key,label in [('length','طول (متر)'),('width','عرض (متر)'),('height','ارتفاع (متر)'),('net_volume_m3','حجم خالص گواهی‌شده'),('volume_source_ref','منبع حجم خالص'),('unit_mass_kg','جرم کل شامل فولاد کارخانه‌ای (کیلوگرم)'),('mass_source_ref','منبع جرم')]:
    if p.get(key) not in (None,''):notes+='؛ '+label+': '+str(p[key])
  if 'series' in params:
   s=params['series'];notes+='؛ قطر (میلی‌متر): '+str(s['diameter_mm'])+'؛ تعداد: '+str(s['count'])+'؛ طول برش (متر): '+str(s['cut_length_m'])+'؛ وزن واحد (کیلوگرم بر متر): '+str(s['unit_weight_kg_m'])+'؛ شکل: '+s['shape_ref']+'؛ منبع وزن: '+s['unit_weight_source']
   if kind==HOLLOW_KIND:notes+='؛ نوع فولاد: '+('رشته پیش‌تنیدگی' if s['steel_kind']=='prestressing_strand' else 'میلگرد معمولی')+'؛ قطعه مالک: '+(s.get('panel_id') or 'کارگاهی، مستقل از کارخانه')
   notes+='؛ اجزای برش: '+'؛ '.join(str(p['id'])+'، '+str(p['length_m'])+' متر، '+p['source_ref'] for p in s['cut_parts'])
  if 'geometry' in params:
   g=params['geometry'];notes+='؛ ناحیه: '+g['id']+'؛ ابتدا (متر): '+', '.join(str(g[k]) for k in ('x','y','z'))+'؛ طول، عرض، ارتفاع (متر): '+', '.join(str(g[k]) for k in ('length','width','height'))+'؛ ناخالص هر سقف: '+str(params['gross_m3'])+'؛ کسر هر سقف: '+str(params['deducted_m3'])
  for key,label in [('length','طول قطعه'),('width','عرض قطعه'),('height','ارتفاع قطعه'),('nx','تعداد در طول'),('ny','تعداد در عرض'),('nz','تعداد در ارتفاع'),('count','تعداد'),('spec_ref','مشخصات قطعه'),('physical_key','هویت فیزیکی'),('approved_by','تأییدکننده'),('length_m','طول (متر)'),('width_m','عرض (متر)'),('deduction_m2','کسر وجه (متر مربع)'),('height_m','ارتفاع شمع (متر)'),('system_ref','روش شمع‌بندی'),('spacing_m','فاصله تیرچه (متر)')]:
   if key in params:notes+='؛ '+label+': '+str(params[key])
  rows.append({'description':v['description'],'quantity':v['quantity'],'unit':v['unit'],'source':v['source_id'],'formula':v['formula'],'notes':notes})
 for p in d['roof_detail'].get('rib_layout',[]):
  rows.append({'description':'جانمایی مستند ریب '+('جهت طول' if p['axis']=='x' else 'جهت عرض')+'؛ ردیف مرجع غیرقابل پرداخت','source':p['id'],'notes':'مرجع: '+p['source_ref']+'؛ تأییدکننده: '+p['approved_by']+'؛ ابتدا (متر): '+', '.join(str(p[k]) for k in ('x','y','z'))+'؛ طول، عرض، ارتفاع (متر): '+', '.join(str(p[k]) for k in ('length','width','height'))})
 for group,p in {**d['roof_detail']['rebars'],'formwork':d['roof_detail']['formwork'],'shoring':d['roof_detail']['shoring']}.items():
  if p.get('status')=='not_applicable':rows.append({'description':LABELS[group]+' — عدم کاربرد مستند','notes':p['reason']+'؛ مرجع: '+p['source_ref']+'؛ تأییدکننده: '+p['approved_by']})
 for p in d['roof_detail']['deductions']:
  rows.append({'description':'هندسه کسری مستند؛ ردیف غیرقابل پرداخت','source':p['id'],'notes':'مرجع: '+p['source_ref']+'؛ ابتدا (متر): '+', '.join(str(p[k]) for k in ('x','y','z'))+'؛ طول، عرض، ارتفاع (متر): '+', '.join(str(p[k]) for k in ('length','width','height'))+'؛ مالک بتن مشترک: '+str(p.get('owner_source_id','بازشو'))})
 key=_id(kind,floor,sid);project=service.open_project(pid)
 amendments=[a for a in project.get('beam_amendments',{}).values() if a.get('beam_key')==key and a.get('kind')=='roof_amendment']
 for a in amendments:
  status={'draft':'درخواست‌شده','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[a['status']]
  rows.append({'description':'اصلاحیه '+status,'notes':'علت: '+a['reason']+'؛ مدرک: '+a['evidence']['evidence_reference']+'؛ سازنده: '+a['created_by']+'؛ بازبین: '+a.get('review',{}).get('reviewer','نیازمند بازبینی')+'؛ مسیر مدرک: '+a['evidence']['evidence_path']+'؛ هش مدرک: '+a['evidence']['evidence_sha256'],'source':a['id']})
  original=a['previous']['data'];old_result=preview(original,service.takeoff)
  previous={r['source_id']:r for r in old_result['rows']};proposed={r['source_id']:r for r in a['rows']}
  for source_id,delta in a['delta'].items():
   old=previous.get(source_id,{});new=proposed.get(source_id,{})
   rows.append({'description':'مقایسه مقدار پیشین، پیشنهادی و اختلاف اصلاحیه','quantity':delta,'unit':old.get('unit') or new.get('quantities',[{}])[0].get('unit',''),'source':source_id,'notes':'پیشین: '+str(old.get('quantity',0))+'؛ پیشنهادی: '+str(new.get('quantities',[{'amount':0}])[0]['amount'])+'؛ اختلاف: '+str(delta)})
 effective_review=project.get('beam_amendments',{}).get(record.get('amendment_id'),{}).get('review',{}).get('reviewer')
 meta={'project_name':project['name'],'building_id':d['building_id'],'floor':floor,'member':sid,'revision':record['revision'],'status':{'draft':'پیش‌نویس','committed':'قطعی'}[record['status']],'source':d['source']['source_id'],'پلان':d['source']['plan_ref'],'دیتایل':d['source']['detail_ref'],'بازبین':effective_review or d.get('roof_review',{}).get('reviewer','نیازمند بازبینی'),'طول (متر)':d['roof_detail']['geometry']['length'],'عرض (متر)':d['roof_detail']['geometry']['width'],'ارتفاع کل (متر)':d['roof_detail']['geometry']['depth'],'تعداد سقف هم‌تیپ':d['roof_detail']['geometry']['count'],'منبع کسورات':d['roof_detail']['deductions_ref']}
 totals={}
 units={'m3':'متر مکعب','kg':'کیلوگرم','m2':'متر مربع','عدد':'عدد'}
 labels={'concrete':'بتن درجاریز','precast_concrete':'بتن پیش‌ساخته','rebar':'میلگرد','formwork':'قالب','joists':'تیرچه','blocks':'بلوک','foam':'فوم','shoring':'شمع‌بندی','waffle_molds':'تعداد قالب وافل','hollow_core_panels':'قطعه نهایی هالوکور','precast_panel_mass':'جرم کل قطعه شامل فولاد کارخانه‌ای','prestressing_steel':'فولاد پیش‌تنیدگی داخل قطعه'}
 for row in result['rows']:
  name=labels[row['item_code']]
  if kind==HOLLOW_KIND and row['item_code']=='rebar':name='میلگرد معمولی '+('کارخانه‌ای، داخل قطعه' if row['role']=='material' else 'کارگاهی')
  label=name+' ('+units[row['unit']]+')';totals[label]=totals.get(label,Decimal(0))+Decimal(str(row['quantity']))
 for index,row in enumerate(rows,1):row['item_no']=index
 exporters={'pdf':export_pdf,'xlsx':export_xlsx,'docx':export_docx,'csv':export_csv}
 if format not in exporters:raise ValueError('قالب گزارش معتبر نیست')
 # Signed amendment deltas are informative, not additional payable quantities.
 return exporters[format](rows,path,title='ریزمتره تخصصی '+SPECS[kind].title+' '+sid,summary={'amount_by_group':wire(totals)},metadata=meta,columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار'),('unit','واحد'),('source','منبع'),('formula','فرمول'),('notes','مدارک و دیتایل')])
