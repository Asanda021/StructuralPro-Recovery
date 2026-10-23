from scripts.phase3_financial_probe import run


def test_effective_amendment_prices_and_reports_survive_reopen(tmp_path):
    result=run(tmp_path/'synthetic')
    assert result['floors']==5 and result['active_floors']==['L1','L2']
    assert result['base']=='2080.40' and result['total']=='2402.86200'
    assert result['reopen_equal'] and result['sqlite_integrity']=='ok'
