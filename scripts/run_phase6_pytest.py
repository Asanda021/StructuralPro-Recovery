"""Retain the original pytest output and exit status, including native Qt hangs."""
import subprocess
import os
import sys
from pathlib import Path

timeout = int(sys.argv[1])
command = [sys.executable, '-c',
    'import sys,faulthandler,pytest; '
    f'faulthandler.dump_traceback_later({timeout},exit=True); '
    'sys.exit(pytest.main(sys.argv[1:]))', *sys.argv[2:]]
try:
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding='utf-8', errors='replace', timeout=timeout+30)
    output, code = result.stdout, result.returncode
except subprocess.TimeoutExpired as exc:
    output = (exc.stdout or b'').decode('utf-8', errors='replace') if isinstance(exc.stdout, bytes) else (exc.stdout or '')
    output += '\nRunner exceeded its external timeout.\n'
    code = 124
Path(os.environ.get('PHASE6_PYTEST_LOG_PATH', 'phase6-pytest.log')).write_text(output, encoding='utf-8')
print(output, end='')
raise SystemExit(code)
