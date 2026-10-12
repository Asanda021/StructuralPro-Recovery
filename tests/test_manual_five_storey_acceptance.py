"""Independent synthetic five-floor acceptance through real persistence and exports.

Reference values come from an explicit fixture, not calls to the application
quantity functions. This is Linux source QA, not Windows/design acceptance.
"""
import csv
import json
import os
from decimal import Decimal
from io import StringIO
from pathlib import Path
import pytest
import pymupdf
from core.platform.application import StructuralProApp
from core.pricing.catalog import PriceCatalog
from core.drawings.graphical_takeoff import Point
from core.drawings.takeoff_session import DrawingTakeoffSession
from test_recovery_13_finishes_five_floors import CODES, WALL, HORIZONTAL, explicit_inputs

FIXTURE=Path(__file__).parent/'fixtures/manual_five_storey_acceptance_20261012.json'


def output_path(tmp_path,name):
 root=Path(os.environ.get('STRUCTURALPRO_ACCEPTANCE_EVIDENCE',str(tmp_path/'evidence')))
 root.mkdir(parents=True,exist_ok=True)
 return root/name


def test_manual_five_floors_independent_reference_priced_boq_statement_and_exports(tmp_path):
 data=json.loads(FIXTURE.read_text());assert data['floors']==5
 catalog=PriceCatalog();buf=StringIO();w=csv.writer(buf)
 w.writerow(['year','group','chapter','code','description','unit','unit_price'])
 for c in data['cases']:w.writerow([1405,'آزمون مصنوعی','سازه و تأسیسات','P-'+c['item'],'شرح مصنوعی '+c['item'],c['unit'],c['unit_price']])
 for code in CODES:w.writerow([1405,'آزمون مصنوعی','نازک‌کاری','P-'+code,'نازک‌کاری '+code,'m' if code=='skirting' else 'm2',5 if code=='skirting' else 10])
 csv_text=buf.getvalue();assert catalog.import_csv(csv_text)==len(data['cases'])+13
 output_path(tmp_path,'فهرست‌بهای_مصنوعی.csv').write_text(csv_text,encoding='utf-8-sig')
 app=StructuralProApp(tmp_path/'manual-db');app.create_project('ساختمان پنج‌طبقه — داده مصنوعی','manual-five')
 comparisons=[];reference_base=Decimal(0);expected_boq={}
 for floor in range(1,6):
  for c in data['cases']:
   source=f"synthetic:L{floor}:{c['item']}";price=catalog.resolve('P-'+c['item'],year=1405,unit=c['unit']);assert price['status']=='ok'
   row=app.add_takeoff('manual-five',c['domain'],c['item'],source_id=source,system=f'L{floor}',manual_location_id='EXPLICIT-'+c['item'],description='متره مصنوعی '+c['item'],price_code='P-'+c['item'],unit_price=price['unit_price'],**c['inputs'])
   q=row['quantities'][0];assert q['amount']==pytest.approx(c['expected_per_floor'],abs=1e-9),c['item'];assert q['unit']==c['unit']
   expected_boq[c['item']]=c['expected_per_floor']*5
   reference_base+=Decimal(str(c['expected_per_floor']))*Decimal(str(c['unit_price']))
   comparisons.append(dict(floor=floor,item=c['item'],expected=c['expected_per_floor'],actual=q['amount'],unit=q['unit'],difference=q['amount']-c['expected_per_floor'],reference=c['reference'],source=source))
  for code in CODES:
   amount=6 if code=='skirting' else 28 if code in WALL else 19
   rate=5 if code=='skirting' else 10;unit='m' if code=='skirting' else 'm2'
   resolved=catalog.resolve('P-'+code,year=1405,unit=unit);assert resolved['status']=='ok'
   r=app.add_assembly_takeoff('manual-five',code,explicit_inputs(code),floor_id=f'L{floor}',location_id='ROOM-001',component_prices={code+'_work':dict(price_code='P-'+code,unit=unit,unit_price=resolved['unit_price'])})
   assert {x['component_role'] for x in r['rows']}=={'work','procurement','material'}
   actual=next(x['quantities'][0]['amount'] for x in r['rows'] if x['component_role']=='work')
   assert actual==amount
   expected_boq[code+'_work']=amount*5;reference_base+=Decimal(amount*rate)
   comparisons.append(dict(floor=floor,item=code+'_work',expected=amount,actual=actual,unit=unit,difference=actual-amount,reference='(10×3−2), (5×4−1), or (7−1); procurement/material excluded',source=r['assembly']['id']))
 # Both manual and assembly duplicate paths remain safe after a new app opens.
 app.store.close();app=StructuralProApp(tmp_path/'manual-db');p=app.open_project('manual-five')
 assert len(p['takeoffs'])==5*len(data['cases'])+195 and len(p['takeoff_assemblies'])==65
 assert len(p['boq'])==len(data['cases'])+13
 by_code={r['item_code']:r for r in p['boq']}
 for code,expected in expected_boq.items():assert by_code[code]['quantity']==pytest.approx(expected,abs=1e-8),code
 assert all(x['price_code'] and x['unit_price'] is not None for x in p['boq'])
 c=data['cases'][0]
 with pytest.raises(ValueError):app.add_takeoff('manual-five',c['domain'],c['item'],source_id='different-session',system='L1',manual_location_id='EXPLICIT-'+c['item'],**c['inputs'])
 with pytest.raises(ValueError):app.add_assembly_takeoff('manual-five',CODES[0],explicit_inputs(CODES[0]),floor_id='L1',location_id='ROOM-001')
 estimate=app.recalculate_estimate('manual-five',factors={'سربار':.1,'منطقه':.05})
 expected_total=reference_base*Decimal('1.10')*Decimal('1.05')
 assert estimate['cost']['base']==pytest.approx(float(reference_base),abs=1e-7)
 assert estimate['cost']['grand_total']==pytest.approx(float(expected_total),abs=1e-7)
 quantities={r['price_code']:r['quantity']*.4 for r in p['boq']}
 digest=app.store.current_digest('manual-five');preview=app.save_statement_period('manual-five',period_no=1,current_quantities=quantities,retention_rate=.1,persist=False)
 assert app.store.current_digest('manual-five')==digest and app.statement_periods('manual-five')==[]
 period=app.save_statement_period('manual-five',period_no=1,current_quantities=quantities,retention_rate=.1)
 assert period==preview;assert period['gross_current']==pytest.approx(float(reference_base*Decimal('.4')))
 assert period['payable_current']==pytest.approx(float(reference_base*Decimal('.4')*Decimal('.9')))
 before=app.open_project('manual-five')['takeoffs']
 outputs=[]
 for fmt in ['csv','xlsx','docx','pdf']:
  target=output_path(tmp_path,'گزارش_پنج‌طبقه.'+fmt);app.report('manual-five',fmt,target,period_no=1);assert target.stat().st_size>0;outputs.append(target.name)
 assert app.open_project('manual-five')['takeoffs']==before
 doc=pymupdf.open(output_path(tmp_path,'گزارش_پنج‌طبقه.pdf'));assert len(doc)>0
 for page in doc:assert page.get_pixmap().width>0
 doc[0].get_pixmap().save(str(output_path(tmp_path,'گزارش_پنج‌طبقه_صفحه۱.png')));pdf_pages=len(doc);doc.close()
 app.store.close();app=StructuralProApp(tmp_path/'manual-db');final=app.open_project('manual-five')
 assert final['takeoffs']==before and app.statement_periods('manual-five')[0]==period
 assert final['estimate']['cost']['grand_total']==pytest.approx(float(expected_total))
 output_path(tmp_path,'manual_five_floor_result.json').write_text(json.dumps(dict(status='PASS',scope='synthetic Linux source acceptance; Windows BLOCKED',cases=len(data['cases']),floors=5,takeoffs=len(final['takeoffs']),assemblies=65,boq=len(final['boq']),reference_base=str(reference_base),reference_total=str(expected_total),statement_gross=period['gross_current'],statement_payable=period['payable_current'],pdf_pages=pdf_pages,outputs=outputs,comparisons=comparisons),ensure_ascii=False,indent=2))
 app.store.close()


def test_vector_pdf_five_floors_explicit_scale_area_length_reopen_and_dedup(tmp_path):
 path=output_path(tmp_path,'نقشه_برداری_مصنوعی_پنج‌طبقه.pdf');doc=pymupdf.open()
 for floor in range(1,6):
  page=doc.new_page(width=200,height=150);page.draw_rect((10,10,110,90));page.draw_line((10,110),(110,110))
 doc.save(path);doc.close()
 app=StructuralProApp(tmp_path/'drawing-db');app.create_project('نقشه مصنوعی پنج‌طبقه','drawing-five')
 s=DrawingTakeoffSession(str(path))
 for floor in range(1,6):
  s.calibrate(floor,100,10)
  s.add_area([Point(10,10),Point(110,10),Point(110,90),Point(10,90)],page=floor,takeoff_code='FLOOR-AREA',label=f'سطح طبقه {floor}')
  s.add_length([Point(10,110),Point(110,110)],page=floor,takeoff_code='WALL-LENGTH',label=f'طول طبقه {floor}')
 assert len(s.items)==10
 for x in s.items:assert x.quantity==pytest.approx(80 if x.kind=='area' else 10)
 saved=app.save_drawing_takeoff_session('drawing-five',s)
 app.commit_drawing_takeoff_to_boq('drawing-five',saved['session_id'],[x.id for x in s.items],expected_session_revision=1)
 duplicate=DrawingTakeoffSession(str(path));duplicate.calibrate(1,100,10);duplicate.add_length([Point(110,110),Point(10,110)],page=1,takeoff_code='WALL-LENGTH')
 ds=app.save_drawing_takeoff_session('drawing-five',duplicate)
 with pytest.raises(ValueError):app.commit_drawing_takeoff_to_boq('drawing-five',ds['session_id'],[duplicate.items[0].id],expected_session_revision=1)
 app.store.close();app=StructuralProApp(tmp_path/'drawing-db');p=app.open_project('drawing-five')
 assert len(p['takeoffs'])==10
 by_unit={x['unit']:x['quantity'] for x in p['boq']};assert by_unit=={'m2':400,'m':50}
 assert all(x['params']['source_sha256'] and x['params']['measurement_identity'] for x in p['takeoffs'])
 output_path(tmp_path,'drawing_five_floor_result.json').write_text(json.dumps(dict(status='PASS_SUPPORTED_VECTOR_SUBSET',source=str(path),pages=5,takeoffs=10,quantity_by_unit=by_unit,scale='100 explicit page coordinate units = 10 m, separately calibrated on each page',blocked=['DWG converter acceptance','real Windows rendering/region selection','automatic reinforcement or roof void inference','approved real building drawing']),ensure_ascii=False,indent=2))
 app.store.close()
