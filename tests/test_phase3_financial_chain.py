from scripts.phase3_statement_ledger_probe import run

def test_five_floor_two_period_financial_chain(tmp_path):
    result=run(tmp_path)
    assert result['periods']==2 and result['issued_first_preserved'] and result['reopen_equal']


def test_five_floor_probe_standalone_process_exits_cleanly(tmp_path):
    import subprocess,sys,os
    from pathlib import Path
    script=Path(__file__).resolve().parents[1]/'scripts/phase3_statement_ledger_probe.py'
    result=subprocess.run([sys.executable,'-X','faulthandler',str(script),str(tmp_path/'scenario')],capture_output=True,text=True,env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},timeout=60)
    assert result.returncode==0,result.stderr
