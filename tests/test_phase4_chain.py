from pathlib import Path
import importlib.util

def test_five_floor_control_acceptance(tmp_path):
    assert importlib.util.find_spec('scripts.phase4_project_controls_probe'),'five-floor acceptance probe absent'
    from scripts.phase4_project_controls_probe import run
    result=run(tmp_path)
    assert result['synthetic'] and result['floors']==5 and result['activities']==15
    assert result['critical_ids']==['S1','S2','S3','S4','S5','A5','M5']
    assert result['actual_periods']==['12.500000','45.000000','75.000000']
    assert result['baseline_preserved'] and result['reopen_equal'] and result['sqlite_integrity']=='ok'
    assert len(result['exports'])==20

def test_standalone_probe_clean_exit(tmp_path):
    import subprocess,sys,os,json
    result=subprocess.run([sys.executable,'scripts/phase4_project_controls_probe.py',str(tmp_path)],env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=120)
    assert result.returncode==0,result.stdout[-1000:]+result.stderr[-1000:]
    assert json.loads((tmp_path/'receipt.json').read_text())['reopen_equal']
