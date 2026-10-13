import pytest
from core.takeoff.engine import TakeoffEngine
from core.takeoff.assembly import calculate_assembly
from core.platform.application import StructuralProApp


def test_floor_template_contract_deducts_opening_for_each_repeat():
    result = TakeoffEngine().calculate('building', 'slab', count=2, length=10, width=4, openings=5)
    assert result.quantity == (10 * 4 - 5) * 2 == 70
    assert result.unit == 'm2'


def test_floor_assembly_uses_same_per_repeat_contract():
    result = calculate_assembly('floor_finish', count=2, length=10, width=4, openings=5, openings_scope='per_repeat')
    assert result.components[0].quantity == 70


@pytest.mark.parametrize('item,inputs,expected,unit',[
    ('cable_tray', {'length':4, 'count':3}, 12, 'm'),
    ('steel_roof_composite_concrete', {'length':4, 'width':3, 'thickness':.2, 'count':2},4.8,'m3'),
    ('stair_concrete', {'sloped_length':4, 'width':1.2, 'waist_thickness':.15, 'count':2},1.44,'m3')])
def test_engine_quantities_persist_and_reopen(tmp_path,item,inputs,expected,unit):
    app=StructuralProApp(tmp_path);app.create_project('مقادیر مستقل','p')
    domain='electrical' if item=='cable_tray' else 'building'
    app.add_takeoff('p',domain,item,source_id='reference-'+item,**inputs)
    app.store.close();app=StructuralProApp(tmp_path)
    row=app.open_project('p')['takeoffs'][0];q=row['quantities'][0]
    assert q['amount']==pytest.approx(expected) and q['unit']==unit
    assert row['params']==inputs
    app.store.close()


@pytest.mark.parametrize('inputs',[
    {'count':2,'length':10,'width':4,'openings':41},
    {'count':1.5,'length':10,'width':4,'openings':0},
    {'count':2,'length':float('nan'),'width':4,'openings':0},
    {'count':True,'length':10,'width':4,'openings':0}])
def test_floor_rejects_invalid_contract(inputs):
    with pytest.raises(ValueError):TakeoffEngine().calculate('building','slab',**inputs)


@pytest.mark.parametrize('count',[-1,1.5,float('nan'),True])
def test_cable_tray_rejects_invalid_count(count):
    with pytest.raises(ValueError):TakeoffEngine().calculate('electrical','cable_tray',length=4,count=count)


@pytest.mark.parametrize('key,item,inputs,expected,unit',[
    ('structural_concrete','stair_concrete',{'sloped_length':4,'width':1.2,'waist_thickness':.15,'count':2},1.44,'m3'),
    ('structural_steel','steel_roof_composite_concrete',{'length':4,'width':3,'thickness':.2,'count':2},4.8,'m3'),
    ('electrical','cable_tray',{'length':4,'count':3},12,'m')])
def test_actual_aec_button_commits_correct_geometry(tmp_path,key,item,inputs,expected,unit,monkeypatch):
    from PySide6.QtWidgets import QApplication,QComboBox,QDoubleSpinBox,QLineEdit,QPushButton,QMessageBox
    from app.aec_workspace import build_aec_workspace
    qt=QApplication.instance() or QApplication([])
    app=StructuralProApp(tmp_path);app.create_project('فرم واقعی','p')
    domain='electrical' if key=='electrical' else 'building'
    w=build_aec_workspace(app,None,title='متره',description='ورودی مستقل',domain=domain,key=key)
    w.findChild(QLineEdit,'TakeoffProject').setText('p')
    w.findChild(QLineEdit,'TakeoffFloor').setText('L1')
    w.findChild(QLineEdit,'TakeoffLocation').setText('synthetic-explicit-'+item)
    combo=w.findChild(QComboBox,'TakeoffItem');combo.setCurrentIndex(combo.findData(item))
    for name,value in inputs.items():w.findChild(QDoubleSpinBox,'TakeoffField_'+name).setValue(value)
    # Corrugated composite decks cannot be priced from a flat rectangular
    # L×W×t volume: profile, troughs and approved concrete regions are missing.
    # This negative GUI case is as important as valid stair/tray computations.
    warnings=[]
    if item=='steel_roof_composite_concrete':
        monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    w.findChild(QPushButton,'PrimaryAction').click();qt.processEvents()
    app.store.close();app=StructuralProApp(tmp_path)
    if item=='steel_roof_composite_concrete':
        assert warnings and 'دیتایل‌های واقعی' in str(warnings[0][2])
        assert app.open_project('p')['takeoffs']==[]
        assert app.open_project('p')['boq']==[]
    else:
        q=app.open_project('p')['takeoffs'][0]['quantities'][0]
        assert q['amount']==pytest.approx(expected) and q['unit']==unit
    app.store.close();w.close()
