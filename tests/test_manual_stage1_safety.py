from decimal import Decimal
import pytest
from core.takeoff.formulas import evaluate
from core.takeoff.manual_workbench import ManualTakeoffWorkbench

TEXT='ستون: تعداد=1، عرض=0.4، عمق=0.4، ارتفاع=3'

def test_formula_preserves_decimal_literal_and_variable():
    v='0.12345678901234567890123456789'
    assert Decimal(str(evaluate(v+'*2',{})))==Decimal('0.24691357802469135780246913578')
    assert Decimal(str(evaluate('a*2',{'a':v})))==Decimal('0.24691357802469135780246913578')

@pytest.mark.parametrize('bad',[True,None,'NaN','Infinity'])
def test_formula_invalid_variable_is_not_a_number(bad):
    with pytest.raises(ValueError):evaluate('x+1',{'x':bad})

def test_row_formula_dependencies_units_and_cycles():
    from core.takeoff.formulas import evaluate_rows
    rows={'A':{'expression':'2*3','variables':{},'unit':'m2'},'B':{'expression':'a-1','variables':{},'unit':'m2','references':{'a':'A'}}}
    assert evaluate_rows(rows)['B']==5
    rows['B']['unit']='m3'
    with pytest.raises(ValueError,match='واحد'):evaluate_rows(rows)
    rows['B']['unit']='m2';rows['A'].update(expression='b+1',references={'b':'B'})
    with pytest.raises(ValueError,match='حلق'):evaluate_rows(rows)

def test_atomic_copy_delete_and_update_keep_identity_and_versions():
    w=ManualTakeoffWorkbench('P');a=w.add_text(TEXT,floor_id='L1');b=w.add_text(TEXT.replace('تعداد=1','تعداد=2'),floor_id='L1')
    copied=w.copy_records([a.record_id,b.record_id],floor_id='L2');assert len(copied)==2 and len(w.records)==4
    w.undo();assert w.records==(a,b);w.redo();assert len(w.records)==4
    before=w.records
    with pytest.raises(KeyError):w.remove_records([a.record_id,'missing'])
    assert w.records==before
    changed=w.update_text(a.record_id,TEXT.replace('ارتفاع=3','ارتفاع=4'),expected_revision=1)
    assert changed.record_id==a.record_id and changed.revision==2 and changed.quantity> a.quantity
    before=w.records
    with pytest.raises(RuntimeError):w.update_text(a.record_id,TEXT,expected_revision=1)
    assert w.records==before
    with pytest.raises(ValueError):w.update_text(a.record_id,'ستون تعداد=1',expected_revision=2)
    assert w.records==before
    w.remove_records([a.record_id,b.record_id]);assert len(w.records)==2
    w.undo();assert w.records==before

def test_manual_dimension_precision_is_never_silently_lost():
    from core.takeoff.manual_input import parse_manual_entry
    with pytest.raises(ValueError,match='دقت'):
        parse_manual_entry('ستون تعداد=1 عرض=0.12345678901234567890123456789 عمق=1 ارتفاع=3')
    entry=parse_manual_entry('ستون تعداد=1 عرض=12.3456cm عمق=1 ارتفاع=3')
    assert Decimal(str(entry.params['width']))==Decimal('0.123456')
