"""Real button interactions and real multi-page Persian report exports."""
from pathlib import Path
import json
import os
import subprocess
import sys


def test_real_preview_save_reopen_and_all_export_pages(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    if sys.platform != "win32":
        environment["QT_QPA_PLATFORM"] = "offscreen"
    process = subprocess.run([sys.executable, str(root / "scripts/recovery_ui_export_probe.py"),
                              "--out-dir", str(tmp_path)], cwd=root, env=environment,
                             capture_output=True, text=True, timeout=90)
    assert process.returncode == 0, process.stdout + process.stderr
    result = json.loads((tmp_path / "ui_exports.json").read_text())
    assert result["qt_preview_save_reopen"]
    assert result["duplicate_save_prevented"]
    assert result["incomplete_geometry_not_persisted"]
    assert result["pdf_pages_rendered"] == len(list(tmp_path.glob("pdf_page_*.png"))) >= 2
    assert result["xlsx_numeric_sum"] == 726
