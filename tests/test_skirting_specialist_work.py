"""Synthetic explicit linear skirting, doors and stock cuts."""
from copy import deepcopy
from decimal import Decimal
import pytest
from core.takeoff.reviewed_aec import empty_system,preview_system
from core.takeoff.engine import TakeoffEngine
from test_architecture_specialist_work import obj

def sample():
 d=empty_system('floor_finish','L1','S1');d.update(measurement_policy='architecture_specialist_v1',building_id='B1',axis='اتاق مصنوعی',source=dict(mode='manual',source_id='SYNTHETIC-SKIRT',plan_ref='پلان مصنوعی',detail_ref='دیتایل مصنوعی'))
 g=dict(physical_space_id='SKIRT-ROOM-1',space_id='ROOM-1',unit='m',count='1',repeat_ref='یک فضای مستقل مصنوعی',corner_status='documented',corner_ref='کنج مستقل مصنوعی',source_ref='پلان مصنوعی',approved_by='کنترل مصنوعی')
 a=dict(contract='interior_skirting_v1',geometry=g,runs=[obj('R1',side_key='EDGE-1',length_m='5',height_m='.1',material_ref='قرنیز مصنوعی',payment_ref='پرداخت طول نصب، قطعات و خرید اطلاعاتی',layout_status='documented',layout_ref='جانمایی مصنوعی',deduction_ref='کسر فقط درگاه مستند')],openings=[obj('D1',run_id='R1',start_m='2',length_m='1')],stocks=[obj('ST1',length_m='3',material_ref='قرنیز مصنوعی'),obj('ST2',length_m='2',material_ref='قرنیز مصنوعی')],pieces=[obj('P1',run_id='R1',stock_id='ST1',start_m='0',length_m='2',stock_start_m='0',piece_type='cut',cut_ref='برش مصنوعی'),obj('P2',run_id='R1',stock_id='ST2',start_m='3',length_m='2',stock_start_m='0',piece_type='full',cut_ref='قطعه کامل مصنوعی')],corners=[obj('K1',run_id='R1',at_m='0',corner_type='inner',detail_ref='کنج مستند مصنوعی')])
 d['architecture_detail']=a;return d

def result(d):return preview_system(d,TakeoffEngine())

def test_independent_net_length_and_stock():
 r=result(sample());assert r['ready'],r['blockers'];q={}
 for v in r['rows']:q[v['item_code']]=q.get(v['item_code'],Decimal(0))+Decimal(str(v['quantity']))
 assert q=={'skirting_work':Decimal(4),'skirting_pieces':Decimal(2),'skirting_cuts':Decimal(1),'skirting_stock':Decimal(2),'skirting_purchase_length':Decimal(5),'skirting_offcut_length':Decimal(1),'skirting_corners':Decimal(1)}
 assert sum(v['role']=='work' for v in r['rows'])==1

@pytest.mark.parametrize('fault',['door_overlap','door_outside','negative','zero_height','missing_detail','piece_overlap','piece_in_door','stock_overlap','no_stock','uncovered','unknown_waste','corner_duplicate','corner_in_door','corner_unknown','no_layout','wrong_unit'])
def test_skirting_fail_closed(fault):
 d=sample();a=d['architecture_detail'];p=a['pieces'][1]
 if fault=='door_overlap':a['openings'].append({**a['openings'][0],'id':'D2','physical_key':'D2'})
 if fault=='door_outside':a['openings'][0]['start_m']='5'
 if fault=='negative':a['runs'][0]['length_m']='-1'
 if fault=='zero_height':a['runs'][0]['height_m']='0'
 if fault=='missing_detail':p['cut_ref']=''
 if fault=='piece_overlap':p['start_m']='1'
 if fault=='piece_in_door':p['start_m']='2'
 if fault=='stock_overlap':p['stock_id']='ST1'
 if fault=='no_stock':p['stock_id']='NO'
 if fault=='uncovered':a['pieces'].pop()
 if fault=='unknown_waste':a['runs'][0]['waste']='.1'
 if fault=='corner_duplicate':a['corners'].append({**a['corners'][0],'id':'K2','physical_key':'K2'})
 if fault=='corner_in_door':a['corners'][0]['at_m']='2.5'
 if fault=='corner_unknown':a['geometry']['corner_status']='unknown'
 if fault=='no_layout':a['runs'][0]['layout_status']='length_only'
 if fault=='wrong_unit':a['geometry']['unit']='cm'
 assert not result(d)['ready']


def test_length_only_unknown_purchase_and_corners_not_zero():
 d=sample();a=d['architecture_detail'];a['pieces']=[];a['stocks']=[];a['corners']=[];a['geometry']['corner_status']='unknown';a['runs'][0]['layout_status']='length_only';r=result(d);assert r['ready'],r['blockers'];assert len(r['rows'])==1 and r['rows'][0]['quantity']==4

@pytest.mark.parametrize('case',['valid','cas','duplicate_source','duplicate_surface','legacy','same_reviewer','financial','evidence','unit','identity','copy'])
def test_skirting_workflow_store_history_boq(tmp_path,case):
 kind='floor_finish'
 from core.platform.application import StructuralProApp
 from hashlib import sha256
 a=StructuralProApp(tmp_path/'db');a.create_project('آزمون مصنوعی پوشش','P');d=sample()
 if case=='legacy':
  old=empty_system(kind,'L1','S1');old['source']={'mode':'manual','source_id':'OLD'};a.save_aec_system_draft('P',old,expected_revision=0)
  with pytest.raises(ValueError):a.save_aec_system_draft('P',d,expected_revision=1)
  a.store.close();return
 a.save_aec_system_draft('P',d,expected_revision=0)
 if case=='cas':
  b=StructuralProApp(tmp_path/'db');stale=b.get_aec_system('P',kind,'L1','S1');a.save_aec_system_draft('P',d,expected_revision=1)
  with pytest.raises(RuntimeError):b.save_aec_system_draft('P',stale['data'],expected_revision=1)
  b.store.close();a.store.close();return
 if case in ('duplicate_source','duplicate_surface'):
  other=deepcopy(d);other['system_id']='OTHER'
  if case=='duplicate_source':other['architecture_detail']['geometry'].update(physical_space_id='OTHER')
  else:other['source']['source_id']='OTHER'
  for table in ('openings','runs','pieces','stocks','corners'):
   for p in other['architecture_detail'][table]:p['physical_key']='OTHER-'+p['physical_key']
  with pytest.raises(ValueError):a.save_aec_system_draft('P',other,expected_revision=0)
  a.store.close();return
 if case=='copy':
  v=a.aec_workflow().copy_roof('P',kind,'L1','S1',new_system_id='COPY',new_source_id='COPY',reason='کپی مصنوعی')['data'];assert v['architecture_detail']['geometry']['physical_space_id']!='SKIRT-ROOM-1';assert v['architecture_detail']['pieces'][0]['stock_id']==v['architecture_detail']['stocks'][0]['id'];assert not result(v)['ready'];a.aec_workflow().delete_roof('P',kind,'L1','COPY',expected_revision=1,reason='حذف مصنوعی');a.store.close();return
 a.review_roof_system('P',kind,'L1','S1',expected_revision=1,reviewer='بازبین',note='کنترل مصنوعی');a.commit_aec_system('P',kind,'L1','S1',expected_revision=2);before=deepcopy(a.open_project('P'));assert len(before['boq'])==1 and before['boq'][0]['quantity']==4
 illegal=deepcopy(before);next(iter(illegal['reviewed_aec_systems'].values()))['data']['axis']='illegal'
 with pytest.raises(ValueError):a.store.save('P',illegal)
 d=deepcopy(a.get_aec_system('P',kind,'L1','S1')['data']);d.pop('roof_review');ar=d['architecture_detail'];ar['runs'][0].update(layout_status='length_only',length_m='4');ar['pieces']=[];ar['stocks']=[]
 if case=='unit':ar['geometry']['unit']='cm'
 if case=='identity':ar['geometry']['physical_space_id']='CHANGED'
 e=tmp_path/'new.txt';e.write_text('EXPLICIT SYNTHETIC cover reduced from net 5 m2 to net 4 m2; last strip removed; procurement no longer certified.');kw=dict(expected_revision=2,created_by='تهیه‌کننده',reason='کاهش مستند سطح مصنوعی',evidence=dict(evidence_path=str(e),evidence_sha256=sha256(e.read_bytes()).hexdigest(),evidence_reference='دیتایل مصنوعی'))
 if case in ('unit','identity'):
  with pytest.raises(ValueError):a.create_roof_amendment('P',kind,'L1','S1',d,**kw)
 else:
  am=a.create_roof_amendment('P',kind,'L1','S1',d,**kw);assert Decimal(str(am['delta']['aec:'+kind+':L1:S1:R1']))==-1
  if case=='same_reviewer':
   with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='تهیه‌کننده',note='نامجاز')
  elif case=='evidence':
   e.write_text('tampered')
   with pytest.raises(ValueError):a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='دیگری',note='کنترل')
  else:
   a.review_beam_amendment('P',am['id'],expected_revision=1,reviewer='دیگری',note='مستقل')
   if case=='financial':
    p=a.open_project('P');p['contract']={'id':'locked'};a.store.save('P',p);locked=deepcopy(a.open_project('P'))
    with pytest.raises(ValueError):a.apply_beam_amendment('P',am['id'],expected_revision=1)
    assert a.open_project('P')==locked
   else:
    a.apply_beam_amendment('P',am['id'],expected_revision=1);assert a.open_project('P')['takeoffs']==before['takeoffs'];assert a.open_project('P')['boq'][0]['quantity']==3;a.store.close();a=StructuralProApp(tmp_path/'db');assert a.get_aec_system('P',kind,'L1','S1')['revision']==3 and a.store.db.execute('pragma integrity_check').fetchone()[0]=='ok'
 if case=='valid':
  from core.reports.architecture_detail_report import export
  export(a,'P',kind,'L1','S1',tmp_path/'amended.csv',format='csv');assert 'وضعیت جدید: فاقد ردیف اطلاعاتی فعال' in (tmp_path/'amended.csv').read_text(encoding='utf-8-sig')
 a.store.close()



def test_four_reports_preserve_exact_long_length(tmp_path):
 from core.platform.application import StructuralProApp
 from core.reports.architecture_detail_report import export
 from openpyxl import load_workbook
 from docx import Document
 import pymupdf
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');d=sample();ar=d['architecture_detail'];ar['runs'][0].update(length_m='5.000000000000000000001',layout_status='length_only');ar['stocks']=[];ar['pieces']=[];a.save_aec_system_draft('P',d,expected_revision=0);a.review_roof_system('P','floor_finish','L1','S1',expected_revision=1,reviewer='بازبین',note='کنترل');a.commit_aec_system('P','floor_finish','L1','S1',expected_revision=2);assert Decimal(str(a.open_project('P')['boq'][0]['quantity']))==Decimal('4.000000000000000000001')
 for fmt in ('pdf','xlsx','docx','csv'):export(a,'P','floor_finish','L1','S1',tmp_path/('skirting.'+fmt),format=fmt)
 b=load_workbook(tmp_path/'skirting.xlsx');assert all(s.sheet_view.rightToLeft for s in b);assert any(c.value=='4.000000000000000000001' for s in b for row in s for c in row);b.close();doc=Document(tmp_path/'skirting.docx');assert all(t._tbl.tblPr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}bidiVisual') is not None for t in doc.tables);pdf=pymupdf.open(tmp_path/'skirting.pdf');assert len(pdf)>0;pdf.close();text=(tmp_path/'skirting.csv').read_text(encoding='utf-8-sig');assert '4.000000000000000000001' in text and 'تعداد قطعات این ضلع نامعلوم' in text;a.store.close()


def test_floor_cannot_silently_become_skirting(tmp_path):
 from core.platform.application import StructuralProApp
 from test_floor_specialist_work import sample as floor_sample
 a=StructuralProApp(tmp_path/'db');a.create_project('مصنوعی','P');old=floor_sample();old['system_id']='S1';a.save_aec_system_draft('P',old,expected_revision=0)
 with pytest.raises(ValueError):a.save_aec_system_draft('P',sample(),expected_revision=1)
 a.store.close()


def test_known_zero_cuts_preserved_in_documented_layout():
 d=sample();d['architecture_detail']['stocks'][0]['length_m']='2';d['architecture_detail']['pieces'][0]['piece_type']='full';r=result(d);assert r['ready'];assert next(v for v in r['rows'] if v['item_code']=='skirting_pieces')['params']['cut_count']==0
