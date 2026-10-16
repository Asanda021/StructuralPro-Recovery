"""Architecture ledger adapter to the existing four shared report exporters."""
from decimal import Decimal
from core.commercial.exact_values import exact,wire
from core.takeoff.architecture_detail import preview,POLICY,LABELS,COMMON,LAYER_FIELDS,REGION_FIELDS,SURFACE_FIELDS,OPENING_FIELDS
from core.takeoff.reviewed_aec import _id
from core.reports.exporters import export_pdf,export_xlsx,export_docx,export_csv
FIELD_LABELS={'id':'شناسه جزء','physical_key':'هویت فیزیکی','source_ref':'مرجع دیتایل','approved_by':'تأییدکننده','physical_wall_id':'شناسه فیزیکی دیوار','unit':'واحد ابعاد','length_m':'طول (متر)','height_m':'ارتفاع (متر)','wall_thickness_m':'ضخامت دیوار (متر)','count':'تعداد مستقل','repeat_ref':'دامنه تکرار','material_kind':'نوع واحد بنایی','offset_m':'ابتدای ضخامت لایه (متر)','thickness_m':'ضخامت لایه (متر)','unit_length_m':'طول واقعی واحد (متر)','unit_height_m':'ارتفاع واقعی واحد (متر)','unit_depth_m':'عمق واقعی واحد (متر)','head_joint_m':'ضخامت بند قائم (متر)','bed_joint_m':'ضخامت بند افقی (متر)','unit_spec_ref':'مدرک ابعاد واحد','mortar_ref':'قرارداد بند کامل ملات','payment_unit':'واحد پرداخت','payment_ref':'مبنای پرداخت','layer_id':'شناسه لایه دیوار','mode':'نوع ناحیه جانمایی','x':'ابتدای طول (متر)','y':'ابتدای ارتفاع (متر)','width_m':'عرض ناحیه (متر)','nx':'تعداد واحد در طول','ny':'تعداد واحد در ارتفاع','surface_id':'شناسه سطح','face':'وجه اجرا','layer_code':'نوع لایه پوشش','material_ref':'مشخصات ماده','density_kg_m3':'چگالی گواهی‌شده (کیلوگرم بر متر مکعب)','density_ref':'مرجع چگالی','opening_ids':'بازشوهای مرتبط','deduction_ref':'قرارداد کسورات','coverage_scope':'دامنه پوشش','scope_ref':'مرجع محدوده اجرا','penetration':'نفوذ بازشو','gross_area_m2':'سطح ناخالص (متر مربع)','net_area_m2':'سطح خالص (متر مربع)','deducted_area_m2':'کسر مؤثر (متر مربع)','net_volume_m3':'حجم خالص (متر مکعب)','installed_count':'تعداد واقعی نصب‌شده','joint_volume_m3':'حجم بند بیرونی (متر مکعب)','repeat_count':'تعداد تکرار مستند'}
VALUES={'brick':'آجر','cement_block':'بلوک سیمانی','clay_block':'بلوک سفالی','light_block':'بلوک سبک','aac':'بلوک بتن هوادار','inside':'داخلی','outside':'خارجی','units':'واحدهای بنایی','mortar':'بند کامل ملات','complete':'تمام وجه','partial':'بخشی از وجه مستند','full_wall':'تمام ضخامت','m':'متر','m2':'متر مربع','m3':'متر مکعب','kg':'کیلوگرم',**LABELS}
from core.takeoff.floor_detail import LABELS as FLOOR_LABELS,INSULATION_LABELS,INSULATION_KINDS
LABELS={**LABELS,**FLOOR_LABELS,**INSULATION_LABELS}
FIELD_LABELS.update(physical_region_id='شناسه فیزیکی ناحیه افقی',space_id='شناسه فضا',shape='شکل ناحیه',base_level_m='تراز مبنای سطح (متر)',level_ref='مرجع تراز',layer_key='هویت لایه مستقل',operation='نوع عملیات',method='روش هندسی',bottom_m='ابتدای لایه از مبنا (متر)',bottom_level_m='تراز زیر لایه (متر)',top_level_m='تراز روی لایه (متر)',purchase_quantity='خرید مستند هر ناحیه',purchase_unit='واحد خرید',purchase_ref='مدرک خرید مستقل هر ناحیه')
FIELD_LABELS.update(installation_plane='جهت سطح نصب',installation_ref='مرجع سطح افقی')
VALUES.update(horizontal='افقی مستند',**INSULATION_LABELS)
VALUES.update(rectangle='مستطیل',constant_rectangular='مستطیل با ضخامت ثابت',all_layers='تمام لایه‌های ناحیه',**FLOOR_LABELS)
from core.takeoff.interior_cover_detail import FIELD_LABELS as COVER_FIELDS,VALUES as COVER_VALUES,LABELS as COVER_LABELS,is_cover,TITLES as COVER_TITLES
FIELD_LABELS.update(COVER_FIELDS);VALUES.update(COVER_VALUES);LABELS.update(COVER_LABELS)
from core.takeoff.skirting_detail import FIELD_LABELS as SKIRT_FIELDS,VALUES as SKIRT_VALUES,LABELS as SKIRT_LABELS,is_skirting,TITLES as SKIRT_TITLES
FIELD_LABELS.update(SKIRT_FIELDS);VALUES.update(SKIRT_VALUES);LABELS.update(SKIRT_LABELS)
def field_label(key,record,cover=False,skirting=False,horizontal=False):
 if skirting and key=='height_m':return 'ارتفاع مقطع قرنیز (متر)'
 if cover:
  if key=='width_m':return 'امتداد دوم سطح (متر)' if 'physical_surface_id' in record else 'عرض قطعه خرید (متر)' if 'length_m' in record else 'اندازه محدوده در راستای طول (متر)'
  if key=='height_m':return 'اندازه محدوده در راستای دوم (متر)'
  if key=='y':return 'ابتدای راستای دوم (متر)'
 if horizontal and key=='height_m':return 'امتداد عرض ناحیه (متر)'
 if horizontal and key=='y':return 'ابتدای عرض (متر)'
 return FIELD_LABELS[key]

EXPORTERS={'pdf':export_pdf,'xlsx':export_xlsx,'docx':export_docx,'csv':export_csv}

@exact
def export_project(service,pid,path,*,format,floor=None,member=None,family=None):
 project=service.open_project(pid);rows=[];totals={};found=0
 def add(description,**kw):rows.append(dict(description=description,**kw))
 for key,base in project.get('reviewed_aec_systems',{}).items():
  bd=base['data']
  if bd.get('measurement_policy')!=POLICY or family is not None and bd['kind']!=family or floor is not None and bd['floor_id']!=floor or member is not None and key!=member:continue
  record=service.get_aec_system(pid,bd['kind'],bd['floor_id'],bd['system_id']);d=record['data'];a=d['architecture_detail'];r=preview(d,service.takeoff)
  if not r['ready']:raise ValueError('؛ '.join(r['blockers']))
  found+=1;rv=project.get('beam_amendments',{}).get(record.get('amendment_id'),{}).get('review',{}).get('reviewer') or d.get('roof_review',{}).get('reviewer','نیازمند بازبینی')
  add('مشخصات عضو؛ طبقه '+d['floor_id']+'؛ '+d['system_id'],source=d['source']['source_id'],notes='ساختمان: '+d['building_id']+'؛ محل: '+d['axis']+'؛ نسخه: '+str(record['revision'])+'؛ وضعیت: '+('قطعی' if record['status']=='committed' else 'پیش‌نویس')+'؛ بازبین: '+rv+'؛ نقشه: '+d['source']['plan_ref']+'؛ دیتایل: '+d['source']['detail_ref'])
  def notes(p):return '؛ '.join(field_label(k,p,is_cover(d),is_skirting(d),d['kind'] in ('floor_finish',)+INSULATION_KINDS and not is_skirting(d))+': '+str(VALUES.get(str(v),v) if k in ('material_kind','face','layer_code','mode','payment_unit','coverage_scope','penetration','unit','shape','operation','method','purchase_unit','plane','layout_status','piece_type','basis','quantity_unit','corner_status','corner_type') else v) for k,v in p.items() if k in FIELD_LABELS and v not in ('',None))
  add('هویت و دامنه قرنیز طولی' if is_skirting(d) else 'هندسه و هویت سطح پوشش' if is_cover(d) else 'هندسه و دامنه لایه‌های افقی' if d['kind'] in ('floor_finish',)+INSULATION_KINDS else 'هندسه و دامنه دیوار',notes=notes(a['geometry']))
  for v in r['rows']:
   add(v['description'],quantity=v['quantity'],unit=v['unit'],source=v['source_id'],formula=v['formula'],notes=notes(v['params'])+'؛ '+('عملیات قابل پرداخت' if v['role']=='work' else 'خرید مستند اطلاعاتی؛ غیرقابل پرداخت مستقل' if v['item_code']=='floor_purchase' else 'مقدار اطلاعاتی مستند؛ مستقل وارد پرداخت نمی‌شود' if is_cover(d) or is_skirting(d) else 'مصالح اطلاعاتی؛ خرید و پرت تعیین نشده؛ غیرقابل پرداخت مستقل'))
   group=LABELS[v['item_code']]+' ('+VALUES.get(v['unit'],v['unit'])+')';totals[group]=totals.get(group,Decimal(0))+Decimal(str(v['quantity']))
  if not is_skirting(d) and d['kind'] in ('floor_finish',)+INSULATION_KINDS and all(not p.get('purchase_quantity') for p in a['layers']):add('خرید، رول، جانمایی نوار و هم‌پوشانی عایق در قرارداد فعلی مسدود است؛ مقدار نامعلوم صفر نیست' if d['kind'] in INSULATION_KINDS else 'مقدار خرید مصالح تعیین نشده؛ هیچ مقدار صفر یا ضریب پرت فرض نشده است')
  if is_cover(d) and any(p.get('layout_status')=='area_only' for p in a['surfaces']):add('جانمایی کامل تعیین نشده؛ تعداد، برش و خرید این سطح نامعلوم‌اند و صفر تلقی نشده‌اند')
  if is_skirting(d) and any(p.get('layout_status')=='length_only' for p in a['runs']):add('خرید و تعداد قطعات این ضلع نامعلوم‌اند؛ صفر فرض نشده‌اند')
  if is_skirting(d) and a['geometry']['corner_status']=='unknown':add('تعداد کنج تعیین نشده؛ صفر فرض نشده است')
  for table,title in ([(k,v) for k,v in SKIRT_TITLES.items() if k!='runs'] if is_skirting(d) else [('openings','بازشوی مستقل'),('unit_regions','جانمایی مستقل واحد و بند')]+([(k,v) for k,v in COVER_TITLES.items() if k in ('stocks','pieces','joints')] if is_cover(d) else [])):
   for p in a.get(table,[]):add(title,source=p['id'],notes=notes(p))
  for name,title in [('masonry','دیوارچینی'),('finishes','اندود'),('accessories','اتصال و مسلح‌سازی')]:
   if a.get(name,{}).get('status')=='not_applicable':add(title+'؛ عدم کاربرد مستند',notes=a[name]['reason']+'؛ مرجع: '+a[name]['source_ref']+'؛ تأییدکننده: '+a[name]['approved_by'])
  for am in project.get('beam_amendments',{}).values():
   if am.get('beam_key')!=key:continue
   add('اصلاحیه '+{'draft':'درخواست‌شده','reviewed':'بازبینی‌شده','applied':'اعمال‌شده'}[am['status']],source=am['id'],notes='علت: '+am['reason']+'؛ مدرک: '+am['evidence']['evidence_reference']+'؛ مسیر: '+am['evidence']['evidence_path']+'؛ هش: '+am['evidence']['evidence_sha256']+'؛ بازبین: '+am.get('review',{}).get('reviewer','نیازمند بازبینی'))
   old={v['source_id']:v for v in preview(am['previous']['data'],service.takeoff)['rows']};new={v['source_id']:v for v in am['rows']}
   for src,delta in am['delta'].items():
    before=old.get(src,{});after=new.get(src,{});missing_info=not after and before.get('role')=='material'
    add('حذف ردیف اطلاعاتی؛ مقدار جدید صفر فرض نشده است' if missing_info else 'اختلاف اصلاحیه؛ در جمع نسخه مؤثر دوباره اضافه نمی‌شود',source=src,quantity=None if missing_info else delta,unit=before.get('unit') or after.get('quantities',[{}])[0].get('unit',''),notes='پیشین: '+str(before.get('quantity',0))+('؛ وضعیت جدید: فاقد ردیف اطلاعاتی فعال؛ از حذف ردیف، مقدار جدید استنتاج نمی‌شود؛ تغییر ثبتی: '+str(delta) if missing_info else '؛ پیشنهادی: '+str(after.get('quantities',[{'amount':0}])[0]['amount'])))
 if not found:raise ValueError('رکورد معماری معتبر یافت نشد')
 if format not in EXPORTERS:raise ValueError('قالب خروجی نامعتبر است')
 for i,row in enumerate(rows,1):row['item_no']=i
 return EXPORTERS[format](rows,path,title='ریزمتره تخصصی معماری؛ دیوار، اندود، کف و عایق افقی',metadata={'project_name':project['name'],'floor':floor or 'تمام طبقات','محدوده':'فقط قرارداد مستطیلی مستند؛ مصالح خرید و پرت استنتاج نشده‌اند'},summary={'amount_by_group':wire(totals)},columns=[('item_no','ردیف'),('description','شرح'),('quantity','مقدار'),('unit','واحد'),('source','منبع'),('formula','فرمول'),('notes','مدارک و دیتایل')])

def export(service,pid,kind,floor,sid,path,*,format):return export_project(service,pid,path,format=format,floor=floor,member=_id(kind,floor,sid))
