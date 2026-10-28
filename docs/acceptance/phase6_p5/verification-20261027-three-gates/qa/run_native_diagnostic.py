"""Reproduce the first bounded-current stopping point without altering a dialog."""
from pathlib import Path
import os, subprocess, sys, tempfile, json
root=Path.cwd();sys.path.insert(0,str(root))
from scripts.run_quarantined_workflow_qa import prepare_source
out=Path(__file__).resolve().parent
node='tests/test_manual_formula_fivefloor_closure.py::test_real_qt_fourteen_operations_five_floors_and_all_reports'
with tempfile.TemporaryDirectory(prefix='structuralpro_native_diagnostic_') as d:
    staged=prepare_source(root,Path(d))
    command=[sys.executable,'-m','pytest','-vv','-s','-o','faulthandler_timeout=30',node]
    timed_out=False
    try:
        proc=subprocess.run(command,cwd=staged,env=dict(os.environ,PYTHONPATH=str(staged),QT_QPA_PLATFORM='offscreen'),capture_output=True,text=True,timeout=75)
    except subprocess.TimeoutExpired as exc:
        timed_out=True
        decode=lambda x:x.decode(errors='replace') if isinstance(x,bytes) else x or ''
        proc=subprocess.CompletedProcess(command,124,decode(exc.stdout),decode(exc.stderr))
    (out/'native-diagnostic.log').write_text(proc.stdout+'\n'+proc.stderr)
    (out/'native-diagnostic.json').write_text(json.dumps({'test':node,'exit_code':proc.returncode,'timed_out':timed_out,'timeout_seconds':75},indent=2)+'\n')
    print(proc.returncode,timed_out)
    sys.exit(proc.returncode)
