"""Local presentation preferences; never part of a project or financial snapshot."""
from pathlib import Path
from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QPushButton
from app.theme import APP_STYLESHEET

DARK_STYLESHEET = APP_STYLESHEET + r"""
QMainWindow, QWidget { background: #142033; color: #e6edf7; }
QLabel { background: transparent; color: #e6edf7; }
#TopShell { background: rgba(12,24,43,240); }
#ContentPage { background: #142033; }
#DashboardSection, #DashboardSummary, #DashboardCard, #KpiCard, QGroupBox { background: #1d2e46; color: #e6edf7; border-color: #425977; }
#DashboardAction, #DashboardNotice, #HelpPanel { background: #233b58; color: #ecf4ff; border-color: #526d8e; }
#PageTitle, #SectionTitle, #DashboardSection QLabel { color: #ecf4ff; }
#PageDescription { color: #b9cce2; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QPlainTextEdit, QListWidget { background: #101d30; color: #ecf4ff; border-color: #526d8e; }
QPushButton { background: #2c4564; color: #ecf4ff; border-color: #597798; }
QPushButton:hover { background: #3a5c82; }
QPushButton:disabled { background: #223248; color: #98a9bd; }
QTableWidget { background: #17273d; color: #ecf4ff; alternate-background-color: #223751; gridline-color: #526d8e; selection-background-color: #345f8a; selection-color: white; }
QHeaderView::section, QTabBar::tab { background: #243d59; color: #ecf4ff; }
QTabBar::tab:selected { background: #345f8a; color: white; }
#CommandRibbon { background: rgba(25,42,64,240); }
#CommandRibbon QPushButton#RibbonAction, #CommandRibbon QPushButton#RibbonPrimary { background: #2b486a; color: #ecf4ff; }
QDockWidget::title { background: #243d59; color: #ecf4ff; padding: 5px; }
"""


class DesktopPreferences(QObject):
    def __init__(self, app, path, parent=None):
        super().__init__(parent or app)
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.app = app
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.theme = self.settings.value('theme', 'light')
        if self.theme not in ('light', 'dark'): self.theme = 'light'
        self.animations = self.settings.value('animations', True, type=bool)
        self.apply()

    def apply(self):
        self.app.setStyleSheet(DARK_STYLESHEET if self.theme == 'dark' else APP_STYLESHEET)
        self.app.setProperty('structuralproTheme', self.theme)
        self.app.setProperty('structuralproAnimationsEnabled', self.animations)

    def add_controls(self, layout):
        self.theme_button = QPushButton(); self.theme_button.setObjectName('ThemeToggle')
        self.motion_button = QPushButton(); self.motion_button.setObjectName('MotionToggle')
        self.theme_button.setToolTip('تغییر واقعی تم روز و شب؛ مستقل از داده پروژه')
        self.motion_button.setToolTip('فعال یا خاموش کردن حرکت‌های نمایشی؛ مقادیر متره تغییر نمی‌کنند')
        def labels():
            self.theme_button.setText('تم روز' if self.theme == 'dark' else 'تم شب')
            self.motion_button.setText('حرکت: فعال' if self.animations else 'حرکت: خاموش')
        def theme():
            self.theme = 'light' if self.theme == 'dark' else 'dark'
            self.settings.setValue('theme', self.theme); self.settings.sync(); self.apply(); labels()
        def motion():
            self.animations = not self.animations
            self.settings.setValue('animations', self.animations); self.settings.sync(); self.apply(); labels()
        self.theme_button.clicked.connect(theme); self.motion_button.clicked.connect(motion)
        labels(); layout.addWidget(self.theme_button); layout.addWidget(self.motion_button)
