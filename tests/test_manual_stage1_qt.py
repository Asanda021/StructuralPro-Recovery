import os,subprocess,sys
from pathlib import Path

def test_real_manual_multirow_fivefloor_native_qt(tmp_path):
    script=Path(__file__).with_name('manual_stage1_qt_probe.py')
    result=subprocess.run([sys.executable,str(script),str(tmp_path)],cwd=script.parents[1],env={**os.environ,'QT_QPA_PLATFORM':'offscreen'},capture_output=True,text=True,timeout=40)
    assert result.returncode==0,result.stdout+result.stderr
