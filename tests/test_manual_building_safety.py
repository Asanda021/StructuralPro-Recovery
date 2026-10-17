"""Regression evidence for manual geometry and actual AEC persistence paths."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from types import SimpleNamespace
import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QLineEdit, QPushButton, QCheckBox, QMessageBox
from app.aec_workspace import build_aec_workspace
from core.platform.application import StructuralProApp
from core.takeoff.modules.building import calculate_building_item
from core.takeoff.assembly import calculate_assembly
from core.takeoff.manual_workbench import ManualTakeoffWorkbench


@pytest.mark.parametrize('item,params',[
 ('column',dict(width=0,depth=.4,height=3,count=1)),
 ('joist_block_roof',dict(length=5,width=4,topping_thickness=.05,joist_spacing=.4,joist_width=.6,joist_depth=.2)),
 ('waffle_roof',dict(length=5,width=4,top_thickness=.05,spacing_x=.4,spacing_y=.5,rib_width=.6,rib_depth=.2)),
 ('hollow_core_roof',dict(length=5,width=4,thickness=.2,void_diameter=.3,void_count=1)),
])
def test_impossible_member_or_roof_geometry_is_rejected(item,params):
 with pytest.raises(ValueError):calculate_building_item(item,**params)


def test_cobiax_bounding_box_is_not_actual_void_volume():
 with pytest.raises(ValueError):
  calculate_building_item('cobiax_roof',length=10,width=10,thickness=.28,void_length=.5,void_width=.25,void_height=.2,void_count=100)


def test_cobiax_verified_void_volume_is_used_without_shape_guess():
 row=calculate_building_item('cobiax_roof',length=10,width=10,thickness=.28,void_volume=.02,void_spec_ref='SYNTHETIC-VOID-DATA-001',void_count=100,count=2)
 assert row.quantity==pytest.approx(52) and row.unit=='m3'


def test_rebar_cut_length_includes_explicit_bends_hooks_and_laps():
 row=calculate_building_item('rebar',length=3,bend_length=.2,hook_length=.3,lap_length=.5,diameter_mm=16,unit_weight=1.58,count=10,detail_ref='SYNTHETIC-BAR-001')
 assert row.quantity==pytest.approx(63.2) and row.unit=='kg'
 with pytest.raises(ValueError):calculate_building_item('rebar',length=3,bend_length=.2,unit_weight=1.58,count=10)


def test_beam_rebar_rate_without_detail_cannot_be_billed_as_exact():
 with pytest.raises(ValueError):
  calculate_assembly('concrete_beam',count=2,length=5,width=.3,depth=.5,rebar_kg_per_m3=120)


def test_beam_schedule_uses_explicit_bar_detail_independently_of_concrete_volume():
 detail=dict(count=10,length=3,unit_weight=1.58,diameter_mm=16,bend_length=.2,hook_length=.3,lap_length=.5,detail_ref='SYNTHETIC-BAR-001')
 result=calculate_assembly('concrete_beam',count=2,length=5,width=.3,depth=.5,rebar_schedule=[detail])
 assert next(x.quantity for x in result.components if x.code=='reinforcement')==pytest.approx(63.2)


def test_manual_text_rebar_detail_is_not_silently_ignored():
 text='آرماتور: تعداد=10، طول=3، وزن واحد=1.58، قطر=16mm، خم=0.2، قلاب=0.3، وصله=0.5، مرجع دیتایل=SYNTHETIC-BAR-001'
 row=ManualTakeoffWorkbench('p').add_text(text,floor_id='L1')
 assert row.quantity==pytest.approx(63.2)
 assert row.params['diameter_mm']==16 and row.params['detail_ref']=='SYNTHETIC-BAR-001'


@pytest.fixture
def ui(tmp_path,monkeypatch):
 qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path);app.create_project('فرم واقعی','p')
 messages=[]
 for method in ['warning','critical','information']:
  monkeypatch.setattr(QMessageBox,method,lambda parent,title,message:messages.append(str(message)))
 catalog=SimpleNamespace(resolve=lambda code:{'status':'ok','unit_price':100,'item':SimpleNamespace(unit='kg')})
 widgets=[]
 def make(key,domain='building'):
  w=build_aec_workspace(app,catalog,title='متره',description='آزمون',domain=domain,key=key);widgets.append(w)
  w.findChild(QLineEdit,'TakeoffProject').setText('p')
  for name,value in [('TakeoffFloor','L1'),('TakeoffLocation','A1'),('TakeoffReviewer','synthetic-explicit-reviewer')]:
   x=w.findChild(QLineEdit,name)
   if x:x.setText(value)
  return w
 yield app,make,messages
 for w in widgets:w.close();w.deleteLater()
 qt.processEvents();app.store.close()


def select(w,code,params):
 c=w.findChild(QComboBox,'TakeoffItem');c.setCurrentIndex(c.findData(code))
 for key,value in params.items():w.findChild(QDoubleSpinBox,'TakeoffField_'+key).setValue(value)


def click(w):w.findChild(QPushButton,'PrimaryAction').click()


@pytest.mark.parametrize('key,code,params,quantity,unit',[
 ('architecture','facade',dict(length=4,height=3,openings=2,count=1),10,'m2'),
 ('architecture','wall',dict(length=4,height=3,openings=2,count=2),20,'m2'),
 ('architecture','ceiling',dict(length=4,width=3,count=2),24,'m2'),
 ('renovation','demolition',dict(length=4,width=3,height=.2,count=2),4.8,'m3'),
 ('renovation','screed',dict(length=4,width=3,thickness=.1,count=2),2.4,'m3'),
 ('structural_steel','steel_sandwich_roof',dict(length=4,width=3,count=2),24,'m2'),
])
def test_real_form_routes_existing_operations_to_correct_engine(ui,key,code,params,quantity,unit):
 app,make,messages=ui;w=make(key);select(w,code,params);click(w)
 app.store._cache.clear();p=app.open_project('p')
 assert len(p['takeoffs'])==1,messages
 q=p['takeoffs'][0]['quantities'][0];assert q['amount']==pytest.approx(quantity) and q['unit']==unit


def test_form_rejects_incompatible_pricebook_unit(ui):
 app,make,messages=ui;w=make('structural_concrete');select(w,'column',dict(width=.4,depth=.4,height=3,count=1))
 price=next(x for x in w.findChildren(QLineEdit) if x.placeholderText().startswith('اختیاری؛'));price.setText('WRONG')
 click(w);assert not app.open_project('p')['takeoffs'] and messages
 assert any('واحد فهرست‌بها' in m for m in messages)


def test_block_assembly_real_button_saves_atomically_and_rejects_repeat(ui):
 app,make,messages=ui;w=make('masonry')
 select(w,'block_wall',dict(length=4,height=3,thickness=.2,openings=0,block_length=.4,block_height=.2,block_thickness=.2,joint_thickness=.01,cement_parts=1,sand_parts=4,block_waste_factor=0,mortar_waste_factor=0))
 w.findChild(QCheckBox).setChecked(True);click(w)
 p=app.open_project('p');assert len(p.get('takeoff_assemblies',[]))==1,messages
 assert len(p['takeoffs'])==5
 click(w);assert len(app.open_project('p')['takeoffs'])==5 and messages


def test_nonfinish_assembly_explicit_location_rejects_cross_instance_duplicate(tmp_path):
 app=StructuralProApp(tmp_path);app.create_project('شناسه پایدار','p')
 params=dict(count=1,width=.4,depth=.4,height=3)
 app.add_assembly_takeoff('p','concrete_column',params,floor_id='L1',location_id='C1',approved_by='synthetic-explicit-reviewer')
 other=StructuralProApp(tmp_path)
 with pytest.raises(ValueError):other.add_assembly_takeoff('p','concrete_column',params,floor_id='L1',location_id='C1',approved_by='synthetic-explicit-reviewer')
 assert len(other.open_project('p')['takeoffs'])==1
 other.store.close();app.store.close()


def test_assembly_component_price_is_explicit_unit_checked_and_atomic(tmp_path):
 app=StructuralProApp(tmp_path);app.create_project('نگاشت مستقل اجزا','p')
 params=dict(count=1,width=.4,depth=.4,height=3)
 with pytest.raises(ValueError):
  app.add_assembly_takeoff('p','concrete_column',params,floor_id='L1',location_id='C1',approved_by='synthetic-explicit-reviewer',component_prices={'concrete':dict(price_code='C',unit='kg',unit_price=100)})
 assert not app.open_project('p')['takeoffs']
 saved=app.add_assembly_takeoff('p','concrete_column',params,floor_id='L1',location_id='C1',approved_by='synthetic-explicit-reviewer',component_prices={'concrete':dict(price_code='C',unit='m3',unit_price=100)})
 assert saved['rows'][0]['quantities'][0]['price_code']=='C'
 assert app.open_project('p')['boq'][0]['total']==pytest.approx(48)
 app.store.close()


def test_actual_manual_dialog_keeps_rebar_detail_through_save_and_reopen(tmp_path):
 from app.manual_takeoff import ManualTakeoffDialog
 qt=QApplication.instance() or QApplication([]);app=StructuralProApp(tmp_path);app.create_project('دیتایل دستی','p')
 dialog=ManualTakeoffDialog(app,'p');dialog.floor_id.setText('L1');dialog.element_label.setText('BAR-001')
 dialog.entry_text.setPlainText('آرماتور: تعداد=10، طول=3، وزن واحد=1.58، قطر=16mm، خم=0.2، قلاب=0.3، وصله=0.5، مرجع دیتایل=SYNTHETIC-BAR-001')
 dialog.add_button.click();assert dialog.table.rowCount()==1
 dialog.save_button.click();dialog.save_button.click()
 dialog.close();dialog.deleteLater();qt.processEvents();app.store.close()
 app=StructuralProApp(tmp_path);p=app.open_project('p');assert len(p['takeoffs'])==1
 row=p['takeoffs'][0];assert row['params']['detail_ref']=='SYNTHETIC-BAR-001'
 assert row['quantities'][0]['amount']==pytest.approx(63.2) and p['boq'][0]['quantity']==pytest.approx(63.2)
 app.store.close()


def test_failed_assembly_transaction_leaves_no_partial_components(ui,monkeypatch):
 app,make,messages=ui;w=make('masonry');select(w,'block_wall',dict(length=4,height=3,thickness=.2,openings=0,block_length=.4,block_height=.2,block_thickness=.2,joint_thickness=.01,cement_parts=1,sand_parts=4,block_waste_factor=0,mortar_waste_factor=0))
 w.findChild(QCheckBox).setChecked(True)
 original=app.store.save
 def invalid(*args,**kwargs):raise RuntimeError('explicit simulated transaction failure')
 monkeypatch.setattr(app.store,'save',invalid);click(w);monkeypatch.setattr(app.store,'save',original)
 app.store._cache.clear();p=app.open_project('p');assert not p['takeoffs'] and not p['boq'] and not p.get('takeoff_assemblies')
 assert messages


def test_manual_revision_preserves_identity_price_and_cannot_move_onto_existing_member(tmp_path):
 app=StructuralProApp(tmp_path);app.create_project('نسخه پایدار','p')
 params=dict(width=.4,depth=.4,height=3,count=1)
 for source,location in [('A','C1'),('B','C2')]:
  app.add_takeoff('p','building','column',source_id=source,system='L1',manual_location_id=location,price_code='C',unit_price=100,**params)
 row=app.revise_takeoff('p','A',expected_revision=1,domain='building',item='column',system='L1',**{**params,'height':4})
 assert row['params']['manual_location_id']=='C1' and row['quantities'][0]['unit_price']==100
 with pytest.raises(ValueError):app.add_takeoff('p','building','column',source_id='new-session',system='L1',manual_location_id='C1',approved_by='synthetic-explicit-reviewer',**params)
 with pytest.raises(ValueError):app.revise_takeoff('p','A',expected_revision=2,domain='building',item='column',system='L1',manual_location_id='C2',**params)
 assert len(app.open_project('p')['takeoffs'])==2;app.store.close()
