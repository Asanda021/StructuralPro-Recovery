def test_extended_five_floor_site_operations(tmp_path):
    from scripts.phase4_site_operations_probe import run
    result=run(tmp_path/'site')
    assert result['prior']['actual_periods']==['12.500000','45.000000','75.000000']
    assert result['prior']['duration_baseline']==18 and result['prior']['duration_current']==20
    assert result['immutable_originals'] and result['reopen_equal']
