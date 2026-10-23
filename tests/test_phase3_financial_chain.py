from scripts.phase3_statement_ledger_probe import run

def test_five_floor_two_period_financial_chain(tmp_path):
    result=run(tmp_path)
    assert result['periods']==2 and result['issued_first_preserved'] and result['reopen_equal']
