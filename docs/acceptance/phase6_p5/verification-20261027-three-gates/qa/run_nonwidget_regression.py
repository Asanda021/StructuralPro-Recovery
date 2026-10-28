"""Bounded supplementary regression; explicit omissions are recorded, never skips."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile

root = Path.cwd()
sys.path.insert(0, str(root))
from scripts.run_quarantined_workflow_qa import HISTORICAL_TESTS, prepare_source, junit_summary
out = Path(__file__).resolve().parent
selected, excluded = [], {}
for path in sorted((root / 'tests').glob('test_*.py')):
    name = str(path.relative_to(root))
    text = path.read_text()
    if name in HISTORICAL_TESTS:
        excluded[name] = 'historical contract: executed independently'
    elif 'QApplication' in text or 'PySide6.QtWidgets' in text:
        excluded[name] = 'direct native widget usage: outside supplementary nonwidget selection'
    else:
        selected.append(name)
with tempfile.TemporaryDirectory(prefix='structuralpro_nonwidget_') as d:
    staged = prepare_source(root, Path(d))
    command = [sys.executable, '-m', 'pytest', '-vv', '-o', 'faulthandler_timeout=30', '--junitxml', str(out / 'nonwidget.xml'), *selected]
    environment = dict(os.environ, PYTHONPATH=str(staged), QT_QPA_PLATFORM='offscreen')
    timed_out = False
    try:
        proc = subprocess.run(command, cwd=staged, env=environment, capture_output=True, text=True, timeout=180)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        decode = lambda x: x.decode(errors='replace') if isinstance(x, bytes) else x or ''
        proc = subprocess.CompletedProcess(command, 124, decode(exc.stdout), decode(exc.stderr))
    (out / 'nonwidget.log').write_text(proc.stdout + '\n' + proc.stderr)
    result = {'scope': 'supplementary selection by direct native widget imports; not full current suite', 'selected_modules': selected, 'excluded_modules': excluded, 'exit_code': proc.returncode, 'timed_out': timed_out, 'timeout_seconds': 180, 'stats': junit_summary(out / 'nonwidget.xml') if (out / 'nonwidget.xml').exists() else {'error': 'JUnit missing: incomplete run'}}
    (out / 'nonwidget.json').write_text(json.dumps(result, indent=2) + '\n')
    print({k:v for k,v in result.items() if k not in ('selected_modules','excluded_modules','stats')})
    if 'passed' in result['stats']: print({k:v for k,v in result['stats'].items() if k in ('passed','failed','skipped','collected')})
    sys.exit(proc.returncode)
