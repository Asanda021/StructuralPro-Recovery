"""Native Windows Qt shell smoke: isolated synthetic UI only, never CAD approval.

The probe executes the real QApplication event loop with the real Windows Qt
platform plugin. Screenshots contain an empty, isolated project dashboard only.
No private DWG, source receipts, binaries or installers are read/generated.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import traceback

parser = argparse.ArgumentParser()
parser.add_argument("--evidence", required=True, type=Path)
args = parser.parse_args()
dest = args.evidence.resolve()
dest.mkdir(parents=True, exist_ok=True)
home = dest / "empty-test-home"
home.mkdir(parents=True, exist_ok=True)

if sys.platform != "win32" or os.environ.get("QT_QPA_PLATFORM") != "windows":
    raise SystemExit("BLOCKED: Windows native Qt backend is mandatory")
if os.environ.get("STRUCTURALPRO_SMOKE"):
    raise SystemExit("BLOCKED: need an actual visible event loop, not timer smoke")

os.environ["APPDATA"] = str(home / "AppData" / "Roaming")
os.environ["LOCALAPPDATA"] = str(home / "AppData" / "Local")
for variable in ("APPDATA", "LOCALAPPDATA"):
    Path(os.environ[variable]).mkdir(parents=True, exist_ok=True)
Path.home = classmethod(lambda cls: home)

from PySide6.QtCore import Qt, QTimer, QCoreApplication, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTabBar, QStackedWidget, QPushButton, QLabel,
)
from app.main import main

real_exec = QApplication.exec
result = {"ok": False, "error": "native Qt interaction did not finish"}


def exercise(app: QApplication) -> None:
    assert app.platformName().lower() == "windows", app.platformName()
    windows = [w for w in app.topLevelWidgets() if isinstance(w, QMainWindow)]
    assert len(windows) == 1, "One real StructuralPro main window expected"
    window = windows[0]
    assert window.isVisible(), "Native main window not visible"
    assert window.windowHandle() is not None and window.windowHandle().isExposed(), (
        "Qt reports native window is not exposed by the Windows compositor"
    )
    assert window.layoutDirection() == Qt.LayoutDirection.RightToLeft
    tabs = window.findChild(QTabBar, "MainNavigationTabs")
    pages = window.findChild(QStackedWidget)
    assert tabs is not None and pages is not None
    assert tabs.count() == pages.count() == 23
    assert tabs.layoutDirection() == Qt.LayoutDirection.RightToLeft

    brand = window.findChild(QLabel, "BrandTitle")
    assert brand is not None and brand.isVisible() and "StructuralPro" in brand.text()
    panel_button = window.findChild(QPushButton, "E5PanelMenu")
    assert panel_button is not None and panel_button.isVisible()
    assert panel_button.menu() is not None
    panel_commands = [a.text() for a in panel_button.menu().actions()]
    assert any("گزارش" in label for label in panel_commands)
    assert any("تاریخچه تغییرات" in label for label in panel_commands)
    # The first native Windows screenshots showed a stray top menu strip.
    # Keep dock actions in a normal RTL shell control instead.
    assert window.menuWidget() is None, "Unexpected bare native top menu strip"

    shots = []
    for width, height in ((1180, 760), (1560, 900)):
        window.resize(width, height)
        app.processEvents()
        shot = window.grab()
        assert not shot.isNull() and shot.width() >= 500 and shot.height() >= 400
        name = f"empty-shell-{width}x{height}.png"
        assert shot.save(str(dest / name), "PNG"), name
        shots.append(name)

    # Exercise the actual QTabBar -> QStackedWidget synchronizer.
    for index in range(tabs.count()):
        tabs.setCurrentIndex(index)
        app.processEvents()
        assert pages.currentIndex() == tabs.tabData(index), (
            "Main navigation mismatch", index, tabs.tabText(index),
            pages.currentIndex(), tabs.tabData(index),
        )

    routes = [
        ("پروژه جدید", "پروژه‌ها"),
        ("متره", "متره سریع"),
        ("BOQ و برآورد", "برآورد و صورت‌مقادیر"),
        ("فهرست‌بها", "فهرست‌بها"),
        ("صورت‌وضعیت", "صورت‌وضعیت"),
        ("گزارش‌ها", "گزارشات"),
        ("اسناد پروژه", "اسناد پروژه"),
        ("هوش مصنوعی", "هوش مصنوعی آفلاین"),
    ]
    observed = []
    for action, target_label in routes:
        pages.setCurrentIndex(0)
        app.processEvents()
        dashboard = pages.widget(0)
        button = next(
            (b for b in dashboard.findChildren(QPushButton)
             if b.objectName() == "DashboardAction" and action in b.text()),
            None,
        )
        assert button is not None and button.isVisible(), ("Dashboard action absent", action)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        app.processEvents()
        expected = next(
            (tabs.tabData(i) for i in range(tabs.count())
             if target_label in tabs.tabText(i)),
            None,
        )
        assert expected is not None
        assert pages.currentIndex() == expected, (
            "Dashboard button routed to wrong page", action,
            pages.currentIndex(), expected, target_label,
        )
        observed.append(action)

    theme = window.findChild(QPushButton, "ThemeToggle")
    assert theme is not None and theme.isVisible()
    before = app.property("structuralproTheme")
    QTest.mouseClick(theme, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert app.property("structuralproTheme") != before
    dark = window.grab()
    assert not dark.isNull() and dark.save(str(dest / "empty-shell-theme-toggle.png"), "PNG")
    QTest.mouseClick(theme, Qt.MouseButton.LeftButton)
    assert app.property("structuralproTheme") == before

    # Evidence describes only a synthetic GUI smoke, never Windows user
    # acceptance, native Autodesk semantics or payable takeoff.
    evidence = {
        "source": "public_synthetic_empty_shell",
        "native_qpa": app.platformName(),
        "qt_scale_factor_requested": os.environ.get("QT_SCALE_FACTOR", "1"),
        "screen_device_pixel_ratio": app.primaryScreen().devicePixelRatio(),
        "main_window_visible": True,
        "main_window_exposed": True,
        "rtl": True,
        "navigation_tabs_checked": tabs.count(),
        "dock_commands_accessible": panel_commands,
        "stray_top_menubar": False,
        "dashboard_actions_clicked": observed,
        "theme_toggle_checked": True,
        "screenshots": shots + ["empty-shell-theme-toggle.png"],
        "real_user_desktop_acceptance": False,
        "original_private_dwg_tested": False,
        "native_autodesk_object_enabler_tested": False,
        "financial_quantity_rows_approved": 0,
        "geometry_approved_for_financial_takeoff": False,
        "engineering_status": "PARTIAL_NO_GO",
    }
    (dest / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def wrapped_exec(app: QApplication) -> int:
    def perform():
        try:
            exercise(app)
            result["ok"] = True
            result["error"] = ""
        except BaseException:
            result["error"] = traceback.format_exc()
            print(result["error"], file=sys.stderr, flush=True)
        finally:
            for widget in app.topLevelWidgets():
                if widget.isVisible():
                    widget.close()
            QTimer.singleShot(100, app.quit)

    QTimer.singleShot(150, perform)
    QTimer.singleShot(45_000, app.quit)
    real_exec()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    return 0 if result["ok"] else 2


QApplication.exec = wrapped_exec
raise SystemExit(main())
