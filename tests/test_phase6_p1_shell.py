"""Phase 6 priority 1: real RTL shell, live controls, saved presentation state."""
from pathlib import Path
import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_shell_source_is_accessible_and_has_no_new_project_data_path():
    shell = (ROOT / 'app/desktop_shell.py').read_text(encoding='utf-8')
    main = (ROOT / 'app/main.py').read_text(encoding='utf-8')
    prefs = (ROOT / 'app/desktop_preferences.py').read_text(encoding='utf-8')
    assert 'ContextRibbonController' in shell
    assert 'ribbon_collapsed' in shell and 'settings.sync()' in shell
    assert 'QPropertyAnimation' in shell and 'preferences.animations' in shell
    assert 'QScrollArea' in main and "setObjectName('CommandRibbonScroll')" in main
    assert 'setAccessibleName' in main
    assert "QKeySequence('Ctrl+Shift+R')" in main
    assert "QKeySequence('Ctrl+1')" in main
    assert "QKeySequence('Ctrl+2')" in main
    assert 'glass_enabled' in prefs and 'OPAQUE_GLASS_FALLBACK' in prefs
    assert 'service.store.save' not in shell


def test_phase6_p1_offscreen_real_qt_toggle_nav_ribbon_and_persistence(tmp_path):
    if importlib.util.find_spec('PySide6') is None:
        pytest.skip('PySide6 required: this test runs in phase 6 Qt CI')
    script = r'''
import sys
import os
from pathlib import Path
from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QScrollArea, QTabBar, QStackedWidget
Path.home = classmethod(lambda cls: Path(sys.argv[1]))
from app.main import main
real_exec = QApplication.exec

def inspect(app):
    window = next(x for x in app.topLevelWidgets() if isinstance(x, QMainWindow))
    tabs = window.findChild(QTabBar, 'MainNavigationTabs')
    stack = window.findChild(QStackedWidget)
    ribbon = window.findChild(QScrollArea, 'CommandRibbonScroll')
    theme = window.findChild(QPushButton, 'ThemeToggle')
    motion = window.findChild(QPushButton, 'MotionToggle')
    glass = window.findChild(QPushButton, 'GlassToggle')
    toggle = window.findChild(QPushButton, 'RibbonToggle')
    assert all(x is not None for x in (tabs, stack, ribbon, theme, motion, glass, toggle))
    assert tabs.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert tabs.count() == stack.count() == 23
    assert tabs.accessibleName() and toggle.accessibleName()
    assert ribbon.isVisible() and not toggle.isChecked()
    screenshot_dir = os.getenv('STRUCTURALPRO_P6_SCREENSHOT_DIR')
    if screenshot_dir:
        dest = Path(screenshot_dir)
        dest.mkdir(parents=True, exist_ok=True)
        app.processEvents()
        assert window.grab().save(str(dest / ('p6-p1-' + sys.platform + '-light.png')))
    initial_theme = app.property('structuralproTheme')
    theme.click()
    assert app.property('structuralproTheme') != initial_theme
    if screenshot_dir:
        app.processEvents()
        assert window.grab().save(str(dest / ('p6-p1-' + sys.platform + '-dark.png')))
    motion.click()
    assert app.property('structuralproAnimationsEnabled') is False
    glass.click()
    assert app.property('structuralproGlassEnabled') is False
    assert '#CommandRibbon { background: #f3f6fa;' in app.styleSheet() if app.property('structuralproTheme') == 'light' else '#CommandRibbon { background: #192a40;' in app.styleSheet()
    toggle.click()
    assert not ribbon.isVisible() and toggle.isChecked()
    stack.setCurrentIndex(1)
    assert tabs.tabData(tabs.currentIndex()) == 1
    assert not ribbon.isVisible()
    toggle.click()
    assert ribbon.isVisible() and not toggle.isChecked()
    actions = ribbon.findChildren(QPushButton)
    assert any(a.objectName() == 'RibbonPrimary' and a.isEnabled() for a in actions)
    first = next(a for a in actions if a.objectName() == 'RibbonPrimary')
    assert first.accessibleName() and first.toolTip()
    toggle.click()
    settings = QSettings(str(Path(sys.argv[1]) / '.structuralpro' / 'ui.ini'), QSettings.Format.IniFormat)
    assert settings.value('theme') != initial_theme
    assert settings.value('animations', type=bool) is False
    assert settings.value('glass_enabled', type=bool) is False
    assert settings.value('ribbon_collapsed', type=bool) is True
    QTimer.singleShot(0, window.close)
    return real_exec()

QApplication.exec = inspect
raise SystemExit(main())
'''
    env = {**os.environ, 'QT_QPA_PLATFORM': 'offscreen', 'STRUCTURALPRO_SMOKE': '0'}
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)], cwd=ROOT,
                            capture_output=True, text=True, env=env, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
