from decimal import Decimal
import pytest
from core.pricing.factors import FactorRegistry, FactorSet
from core.takeoff.estimate import compare_estimates, build_estimate
from core.pricing.import_service import PricebookImportService


def test_snapshot_delta_preserves_sub_float_precision():
    old={'cost':{'grand_total':'10000000000000000.000000000000000001'}}
    new={'cost':{'grand_total':'10000000000000000.000000000000000003'}}
    assert Decimal(str(compare_estimates(old,new)['delta'])) == Decimal('0.000000000000000002')


def test_factor_registry_preserves_source_digits():
    rate='0.12345678901234567890123456789'
    registry=FactorRegistry([FactorSet(1405,'fixture',{'overhead':rate})])
    assert Decimal(str(registry.rates(1405,'fixture')['overhead'])) == Decimal(rate)


def test_boolean_factor_is_not_a_rate():
    with pytest.raises(ValueError):
        FactorRegistry([FactorSet(1405,'fixture',{'overhead':True})])


def test_unpriced_estimate_cannot_be_finalized():
    estimate=build_estimate([{'description':'fixture','item_code':'A','quantity':2,'unit':'m'}])
    assert not estimate['finalizable']


@pytest.mark.parametrize('suffix',['.xlsx','.xlsm'])
def test_incomplete_excel_row_fails_without_partial_import(tmp_path,suffix):
    from openpyxl import Workbook
    path=tmp_path/('fixture'+suffix)
    wb=Workbook();ws=wb.active
    ws.append(['code','description','unit','unit_price'])
    ws.append(['A','valid fixture','m','12.34'])
    ws.append(['B',None,'m','56.78'])
    wb.save(path)
    service=PricebookImportService()
    with pytest.raises(ValueError): service.import_file(path,year=1405)
    assert not service.catalog._items


def test_pricebook_replacement_requires_explicit_permission_and_cas(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('fixture','P')
    p=tmp_path/'prices.csv';p.write_text('code,description,unit,unit_price\nA,fixture,m,1\n')
    original=app.import_project_pricebook('P',p,year=1405,approved_by='reviewer')
    before=app.store.current_digest('P')
    p.write_text('code,description,unit,unit_price\nA,fixture,m,2\n')
    with pytest.raises(ValueError):app.import_project_pricebook('P',p,year=1405,approved_by='reviewer')
    assert app.store.current_digest('P')==before
    review=app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRR',source_version='R2',replace_approved=True,expected_digest=before)
    assert review['currency']=='IRR' and review['source_version']=='R2'
    assert app.open_project('P')['pricebook_review_history']==[original]
    with pytest.raises(RuntimeError):app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',expected_digest=before)
    app.store.close()


def test_pricebook_currency_is_not_implicitly_converted(tmp_path):
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('fixture','P')
    p=tmp_path/'prices.csv';p.write_text('code,description,unit,unit_price\nA,fixture,m,100\n')
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='unknown')
    assert app.store.current_digest('P')==before
    review=app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRT',source_version='fixture-R1')
    assert review['rows_by_code']['A']['unit_price']==100
    app.store.close()


def test_reviewed_factor_document_and_estimate_history(tmp_path):
    import json,hashlib
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('synthetic','P')
    app.add_takeoff('P','building','wall',source_id='fixture:phase3:wall',length=3,height=2,openings=0,count=1,price_code='A',unit_price=100)
    p=tmp_path/'prices.csv';p.write_text('code,description,unit,unit_price\nA,fixture,m2,100\n')
    app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRR',source_version='R1')
    doc=tmp_path/'factors.json'
    data={'version':'R1','year':1405,'currency':'IRR','effective_date':'2026-10-23','basis':'sequential_compound','factors':[{'name':'overhead','rate':'0.1234567890123456789'}]}
    doc.write_text(json.dumps(data))
    sha=hashlib.sha256(doc.read_bytes()).hexdigest();digest=app.store.current_digest('P')
    reviewed=app.review_project_factors('P',doc,sha256=sha,author='author',reviewer='reviewer',expected_digest=digest)
    result=app.recalculate_estimate('P')
    assert Decimal(str(result['cost']['grand_total'])) == Decimal('674.0740734074074073400')
    assert result['factor_review_sha256']==sha
    assert reviewed['basis']=='sequential_compound'
    first=app.open_project('P')['estimate']
    app.recalculate_estimate('P')
    assert app.open_project('P')['estimate_history']==[first]
    before=app.store.current_digest('P');doc.write_text('{}')
    with pytest.raises(ValueError):app.recalculate_estimate('P')
    assert app.store.current_digest('P')==before
    app.store.close();app=StructuralProApp(tmp_path/'app')
    assert app.open_project('P')['estimate_history']==[first]
    assert app.store.integrity_check()['ok'];app.store.close()


@pytest.mark.parametrize('fault',['author','year','currency','basis','rate','duplicate','sha','cas'])
def test_invalid_factor_evidence_is_atomic(tmp_path,fault):
    import json,hashlib
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('fixture','P')
    p=tmp_path/'p.csv';p.write_text('code,description,unit,unit_price\nA,test,m,1\n')
    app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRR')
    data={'version':'R1','year':1405,'currency':'IRR','effective_date':'2026-10-23','basis':'sequential_compound','factors':[{'name':'z','rate':'0.1'}]}
    if fault in {'year','currency','basis'}:data[fault]={'year':1404,'currency':'IRT','basis':'guessed'}[fault]
    if fault=='rate':data['factors'][0]['rate']=True
    if fault=='duplicate':data['factors']*=2
    doc=tmp_path/'f.json';doc.write_text(json.dumps(data));sha=hashlib.sha256(doc.read_bytes()).hexdigest()
    before=app.store.current_digest('P')
    with pytest.raises((ValueError,RuntimeError)):
        app.review_project_factors('P',doc,sha256='0'*64 if fault=='sha' else sha,author='reviewer' if fault=='author' else 'author',reviewer='reviewer',expected_digest='stale' if fault=='cas' else before)
    assert app.store.current_digest('P')==before
    app.store.close()


def test_reviewed_factors_use_document_order_after_sqlite_reopen(tmp_path):
    import json,hashlib
    from core.platform.application import StructuralProApp
    app=StructuralProApp(tmp_path/'app');app.create_project('fixture','P')
    app.add_takeoff('P','building','wall',source_id='fixture:order:wall',length=3,height=2,openings=0,count=1,price_code='A',unit_price=100)
    p=tmp_path/'p.csv';p.write_text('code,description,unit,unit_price\nA,test,m2,100\n')
    app.import_project_pricebook('P',p,year=1405,approved_by='reviewer',currency='IRR')
    data={'version':'R1','year':1405,'currency':'IRR','effective_date':'2026-10-23','basis':'sequential_compound','factors':[{'name':'z','rate':'0.1'},{'name':'a','rate':'0.2'}]}
    doc=tmp_path/'f.json';doc.write_text(json.dumps(data));sha=hashlib.sha256(doc.read_bytes()).hexdigest()
    app.review_project_factors('P',doc,sha256=sha,author='author',reviewer='reviewer',expected_digest=app.store.current_digest('P'))
    app.store.close();app=StructuralProApp(tmp_path/'app')
    estimate=app.recalculate_estimate('P')
    assert [x['name'] for x in estimate['cost']['factor_sequence']]==['z','a']
    project=app.open_project('P');project['factor_review']['rates']['z']=999
    app.store.save('P',project)
    before=app.store.current_digest('P')
    with pytest.raises(ValueError):app.recalculate_estimate('P')
    assert app.store.current_digest('P')==before
    app.store.close()
