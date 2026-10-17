"""Independent synthetic issued-statement immutability and preview input gates."""
from copy import deepcopy
import pytest
from core.platform.application import StructuralProApp

def priced(tmp_path):
    a=StructuralProApp(tmp_path/'db');a.create_project('منبع مصنوعی صریح','P')
    a.add_takeoff('P','building','wall',source_id='manual:W1',system='L1',length=10,height=3,count=1,openings=0,price_code='W',unit_price=100)
    f=tmp_path/'prices.csv';f.write_text('year,group,chapter,code,description,unit,unit_price\n1405,ابنیه,01,W,دیوار,m2,100\n')
    a.import_project_pricebook('P',f,year=1405,approved_by='synthetic-independent-reviewer');return a

@pytest.mark.parametrize('change',['remove_period','change_amount','change_lines','change_takeoff','change_assembly'])
def test_issued_history_and_measurement_cannot_be_overwritten(tmp_path,change):
    a=priced(tmp_path);a.save_statement_period('P',current_quantities={'W':2})
    before=a.open_project('P');revisions=len(a.store.revisions('P'));p=deepcopy(before)
    if change=='remove_period':p['statement_periods']=[]
    elif change=='change_amount':p['statement_periods'][0]['gross_current']=999
    elif change=='change_lines':p['statement_periods'][0]['lines'][0]['current_quantity']=9
    elif change=='change_takeoff':p['takeoffs'][0]['params']['length']=999
    else:p['takeoff_assemblies']=[{'id':'unverified-change'}]
    with pytest.raises(ValueError,match='اصلاحیه'):a.store.save('P',p)
    assert a.open_project('P')==before and len(a.store.revisions('P'))==revisions
    assert not a.store.db.in_transaction;a.store.close()

def test_new_period_and_independent_actual_cost_are_still_allowed(tmp_path):
    a=priced(tmp_path);first=a.save_statement_period('P',current_quantities={'W':2})
    a.add_project_cost('P','مصالح',25)
    second=a.save_statement_period('P',current_quantities={'W':3})
    assert second['gross_current']==300 and second['lines'][0]['cumulative_quantity']==5
    a.store.close();a=StructuralProApp(tmp_path/'db')
    assert a.statement_periods('P')[0]==first and a.statement_periods('P')[1]==second
    assert a.project_cost_summary('P')['actual_cost']==25;a.store.close()

@pytest.mark.parametrize('value',[True,float('nan'),float('inf'),-1])
def test_previous_payment_cannot_be_unknown_or_nonfinite(tmp_path,value):
    a=priced(tmp_path);p=a.open_project('P');p['boq'][0]['current_quantity']=2;a.store.save('P',p)
    before=a.open_project('P')
    with pytest.raises(ValueError):a.build_statement('P',previous_paid=value)
    assert a.open_project('P')==before;a.store.close()

def test_statement_preview_requires_explicit_period_work(tmp_path):
    a=priced(tmp_path);before=a.open_project('P')
    with pytest.raises(ValueError):a.build_statement('P')
    assert a.open_project('P')==before
    p=a.open_project('P');p['boq'][0]['current_quantity']=0;a.store.save('P',p)
    assert a.build_statement('P')['gross_current']==0;a.store.close()


def test_estimate_report_does_not_invent_unspecified_period_work(tmp_path):
    import csv
    a=priced(tmp_path);a.recalculate_estimate('P');before=a.open_project('P')
    target=tmp_path/'estimate.csv';a.report('P','csv',target)
    with target.open(encoding='utf-8-sig',newline='') as f:
        lines=list(csv.reader(f))
    assert lines[0]==['منبع مصنوعی صریح']
    header_index=next(i for i,row in enumerate(lines) if 'مقدار قرارداد' in row)
    rows=[dict(zip(lines[header_index],row)) for row in lines[header_index+1:] if row]
    assert len(rows)==1 and float(rows[0]['مقدار قرارداد'])==30
    assert float(rows[0]['مبلغ قرارداد'])==3000
    assert rows[0]['منابع متره']=='manual:W1'
    assert 'این دوره' not in rows[0] and 'مبلغ این دوره' not in rows[0]
    assert a.open_project('P')==before and not a.statement_periods('P');a.store.close()
