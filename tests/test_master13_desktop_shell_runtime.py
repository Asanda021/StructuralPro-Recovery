"""Run the actual desktop shell; verify navigation and calendar behavior, not source text."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_actual_shell_navigation_calendar_and_ribbon(tmp_path):
    if importlib.util.find_spec('PySide6') is None:
        pytest.skip('Desktop dependency is exercised by comprehensive CI and Windows verification')
    script = r'''
import sys
from pathlib import Path
from PySide6.QtCore import QCalendar, QDate, QLocale, Qt
from PySide6.QtWidgets import QApplication, QMainWindow, QTabBar, QStackedWidget, QPushButton, QTreeWidget, QDialog, QCalendarWidget
Path.home = classmethod(lambda cls: Path(sys.argv[1]))
from app.main import main
original_exec = QApplication.exec
calendar_seen = []
def inspect_calendar(dialog):
    calendar = dialog.findChild(QCalendarWidget)
    assert calendar.calendar().name() == 'Jalali'
    assert calendar.selectedDate() == QDate.currentDate()
    assert calendar.locale().language() == QLocale.Language.Persian
    calendar_seen.append(True)
    return 0
QDialog.exec = inspect_calendar
def inspect_shell(app):
    window = next(w for w in app.topLevelWidgets() if isinstance(w, QMainWindow))
    tabs = window.findChild(QTabBar, 'MainNavigationTabs')
    pages = window.findChild(QStackedWidget)
    assert tabs and pages
    assert tabs.count() == pages.count() == 23
    assert tabs.layoutDirection() == Qt.LayoutDirection.RightToLeft
    assert not window.findChildren(QTreeWidget)
    assert window.findChild(QPushButton, 'RibbonPrimary')
    targets = [tabs.tabData(i) for i in range(tabs.count())]
    assert set(targets) == set(range(pages.count()))
    for i, target in enumerate(targets):
        tabs.setCurrentIndex(i)
        assert pages.currentIndex() == target
        assert tabs.tabToolTip(i)
    for target in reversed(targets):
        pages.setCurrentIndex(target)
        assert tabs.tabData(tabs.currentIndex()) == target
    date = window.findChild(QPushButton, 'SystemPersianDate')
    locale = QLocale(QLocale.Language.Persian, QLocale.Country.Iran)
    assert date.text() == locale.toString(QDate.currentDate(), QLocale.FormatType.LongFormat, QCalendar(QCalendar.System.Jalali))
    date.click()
    assert calendar_seen == [True]
    return original_exec()
QApplication.exec = inspect_shell
raise SystemExit(main())
'''
    environment = os.environ.copy()
    environment.update(QT_QPA_PLATFORM='offscreen', STRUCTURALPRO_SMOKE='1')
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1], env=environment,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
