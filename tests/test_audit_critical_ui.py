import os
import subprocess
import sys
import pytest
from pathlib import Path


@pytest.mark.parametrize('mode',['quick','finance','members'])
def test_quick_takeoff_real_button_and_ribbon(tmp_path,mode):
    script = Path(__file__).with_name('audit_critical_ui_probe.py')
    result = subprocess.run([sys.executable, str(script), str(tmp_path),mode],
                            cwd=script.parents[1],
                            env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'STRUCTURALPRO_SMOKE':'1'},
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
