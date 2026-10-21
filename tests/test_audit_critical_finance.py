import pytest
from core.platform.application import StructuralProApp


def priced_app(tmp_path):
    app=StructuralProApp(tmp_path);app.create_project('برآورد مستقل','p')
    app.add_takeoff('p','building','slab',count=1,length=2,width=1,price_code='A',unit_price=100,source_id='A')
    app.add_takeoff('p','building','slab',count=1,length=3,width=1,price_code='B',unit_price=20,source_id='B')
    prices=tmp_path/'synthetic-user-prices.csv'
    prices.write_text('year,group,chapter,code,description,unit,unit_price\n1404,ابنیه,01,A,سطح اول,m2,100\n1404,ابنیه,01,B,سطح دوم,m2,20\n')
    app.import_project_pricebook('p',prices,year=1404,approved_by='explicit-synthetic-price-reviewer')
    return app


def test_report_and_snapshot_retain_explicit_factor_rates(tmp_path):
    app=priced_app(tmp_path)
    assert app.recalculate_estimate('p',factors={'سربار':.1,'منطقه':.05})['cost']['grand_total']==pytest.approx(300.3)
    assert app.build_commercial_snapshot('p')['estimate']['cost']['grand_total']==pytest.approx(300.3)
    for fmt in ['xlsx','pdf']:
        app.report('p',fmt,tmp_path/f'گزارش.{fmt}')
        assert (tmp_path/f'گزارش.{fmt}').stat().st_size>0
    app.store.close();app=StructuralProApp(tmp_path)
    assert app.open_project('p')['estimate']['cost']['grand_total']==pytest.approx(300.3)
    # An explicitly empty mapping still means the user deliberately removed factors.
    assert app.recalculate_estimate('p',factors={})['cost']['grand_total']==260
    app.store.close()


@pytest.mark.parametrize('rate',[-.1,float('nan'),float('inf'),True,1.1])
@pytest.mark.parametrize('field',['retention_rate','advance_recovery_rate','tax_rate','insurance_rate'])
def test_invalid_statement_rate_is_not_persisted(tmp_path,field,rate):
    app=priced_app(tmp_path)
    with pytest.raises(ValueError):app.save_statement_period('p',current_quantities={'A':1},**{field:rate})
    assert app.statement_periods('p')==[]
    app.store.close()


def test_statement_preview_save_report_reopen_agree(tmp_path):
    app=priced_app(tmp_path)
    args={'period_no':1,'current_quantities':{'A':2,'B':3},'retention_rate':.1,'advance_recovery_rate':.05,'tax_rate':.09,'insurance_rate':.07}
    preview=app.save_statement_period('p',persist=False,**args)
    assert app.statement_periods('p')==[]
    period=app.save_statement_period('p',**args)
    assert period==preview and period['gross_current']==260
    assert period['retention']==26 and period['payable_current']==pytest.approx(225.42)
    app.report('p','xlsx',tmp_path/'دوره.xlsx',period_no=1)
    app.report('p','pdf',tmp_path/'دوره.pdf',period_no=1)
    app.store.close();app=StructuralProApp(tmp_path)
    assert app.statement_periods('p')[0]==period
    app.store.close()


@pytest.mark.parametrize('quantities',[{'UNKNOWN':1},{'A':True}])
def test_unknown_or_boolean_statement_work_is_rejected(tmp_path,quantities):
    app=priced_app(tmp_path)
    with pytest.raises(ValueError):app.save_statement_period('p',current_quantities=quantities)
    assert app.statement_periods('p')==[];app.store.close()
