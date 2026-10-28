"""Diagnostic font-rendering evidence for Windows Qt. No product-state mutations.

A font merely being listed is not proof it can rasterize Persian. These probes
log actual Qt font properties and save raw-font and QLabel renders for inspection.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_qt_glyph_capability_and_render_diagnostics(tmp_path):
    pytest.importorskip("PySide6")
    code = r"""
import json, os, sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QImage, QPainter, QRawFont
from PySide6.QtWidgets import QApplication, QLabel
from app.desktop_preferences import _preferred_persian_font
app=QApplication([])
selected, arabic_supported = _preferred_persian_font()
raw=QRawFont.fromFont(QFont(selected, 16))
characters='StructuralPro 0123456789 ۰۱۲۳۴۵۶۷۸۹ کارگاه متره'
font=QFont(selected, 18)
metrics=QFontMetrics(font)
glyphs={ch: bool(raw.supportsCharacter(ord(ch))) for ch in set(characters) if not ch.isspace()}
result=dict(platform=sys.platform, qpa=os.environ.get('QT_QPA_PLATFORM'), family=selected,
            arabic_supported=arabic_supported, glyphs=glyphs,
            raw_valid=raw.isValid(), font_metrics_width=metrics.horizontalAdvance(characters),
            available_fonts=QFontDatabase.families()[:100])
print('PHASE6_FONT_DIAGNOSTIC '+json.dumps(result,ensure_ascii=False),flush=True)
assert selected and raw.isValid()
assert arabic_supported, 'No installed font passed Persian/Latin coverage validation'
assert all(glyphs.values()), 'Qt selected font lacks printable glyphs, see diagnostic'
dest=Path(os.environ.get('STRUCTURALPRO_P6_FONT_DIR', '.'))
dest.mkdir(parents=True,exist_ok=True)
image=QImage(680,140,QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.white)
painter=QPainter(image)
painter.setPen(Qt.GlobalColor.black);painter.setFont(font)
painter.drawText(12,70,characters);painter.end()
assert image.save(str(dest/'font-direct.png'))
label=QLabel(characters)
label.setFont(font);label.resize(680,140)
label.setAlignment(Qt.AlignmentFlag.AlignCenter)
label.show()
assert label.grab().save(str(dest/'font-label.png'))
"""
    env={**os.environ,'STRUCTURALPRO_P6_FONT_DIR':str(tmp_path)}
    result=subprocess.run([sys.executable,"-c",code],cwd=ROOT,env=env,
                          capture_output=True,text=True,timeout=55)
    print(result.stdout)
    assert result.returncode==0, result.stderr
    assert (tmp_path/"font-direct.png").is_file()
    assert (tmp_path/"font-label.png").is_file()
    output=os.environ.get("STRUCTURALPRO_P6_FONT_DIR")
    if output:
        target=Path(output); target.mkdir(parents=True,exist_ok=True)
        for img in ("font-direct.png","font-label.png"):
            (target/img).write_bytes((tmp_path/img).read_bytes())
