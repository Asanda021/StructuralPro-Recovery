"""Local presentation preferences; never part of a project or financial snapshot."""
from pathlib import Path
from PySide6.QtCore import QObject, QSettings
from PySide6.QtWidgets import QPushButton
from PySide6.QtGui import QFont, QFontDatabase
from app.theme import APP_STYLESHEET

# Qt alpha compositing supplies glass-like panels without Windows-only APIs.
# Users on constrained hardware can select fully opaque toolbar backgrounds.
OPAQUE_GLASS_FALLBACK = r"""
#TopShell { background: #10233f; }
#MainNavigationTabs { background: #10233f; border: 1px solid #486381; }
#MainNavigationTabs::tab { background: #213d5d; border: 1px solid #486381; }
#MainNavigationTabs::tab:selected { background: #245a91; }
#CommandRibbon { background: #f3f6fa; border-top: 1px solid #cad6e4; border-bottom: 1px solid #cad6e4; }
"""

DARK_OPAQUE_GLASS_FALLBACK = r"""
#TopShell { background: #0c182b; }
#MainNavigationTabs { background: #0c182b; border: 1px solid #486381; }
#MainNavigationTabs::tab { background: #213d5d; border: 1px solid #486381; }
#MainNavigationTabs::tab:selected { background: #245a91; }
#CommandRibbon { background: #192a40; border-top: 1px solid #486381; border-bottom: 1px solid #486381; }
"""

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


# Qt stylesheet font-family lists are not reliable platform fallbacks.
# Prefer an actually installed font with Arabic/Persian glyph coverage.
def _preferred_persian_font():
    families = QFontDatabase.families()
    by_name = {name.casefold(): name for name in families}
    preferred = ('Vazirmatn', 'Tahoma', 'Segoe UI', 'Noto Sans Arabic',
                 'Noto Naskh Arabic', 'DejaVu Sans', 'Arial')
    arabic = QFontDatabase.WritingSystem.Arabic
    for name in preferred:
        chosen = by_name.get(name.casefold())
        if chosen and arabic in QFontDatabase.writingSystems(chosen):
            return chosen, True
    for chosen in families:
        if arabic in QFontDatabase.writingSystems(chosen):
            return chosen, True
    fallback = QFontDatabase.systemFont(QFontDatabase.SystemFont.GeneralFont).family()
    return fallback, False


class DesktopPreferences(QObject):
    def __init__(self, app, path, parent=None):
        super().__init__(parent or app)
        path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
        self.app = app
        self.settings = QSettings(str(path), QSettings.Format.IniFormat)
        self.theme = self.settings.value('theme', 'light')
        if self.theme not in ('light', 'dark'): self.theme = 'light'
        self.animations = self.settings.value('animations', True, type=bool)
        self.glass_enabled = self.settings.value('glass_enabled', True, type=bool)
        self.font_family, self.arabic_supported = _preferred_persian_font()
        self.apply()

    def apply(self):
        style = DARK_STYLESHEET if self.theme == 'dark' else APP_STYLESHEET
        if not self.glass_enabled:
            style += (DARK_OPAQUE_GLASS_FALLBACK if self.theme == 'dark'
                      else OPAQUE_GLASS_FALLBACK)
        self.app.setFont(QFont(self.font_family))
        style = style.replace('font-family: "Vazirmatn","Segoe UI",Tahoma,sans-serif;',
                              'font-family: "' + self.font_family.replace('"', '') + '";')
        self.app.setStyleSheet(style)
        self.app.setProperty('structuralproTheme', self.theme)
        self.app.setProperty('structuralproAnimationsEnabled', self.animations)
        self.app.setProperty('structuralproGlassEnabled', self.glass_enabled)
        self.app.setProperty('structuralproFontFamily', self.font_family)
        self.app.setProperty('structuralproFontArabicSupported', self.arabic_supported)

    def add_controls(self, layout):
        self.theme_button = QPushButton(); self.theme_button.setObjectName('ThemeToggle')
        self.motion_button = QPushButton(); self.motion_button.setObjectName('MotionToggle')
        self.glass_button = QPushButton(); self.glass_button.setObjectName('GlassToggle')
        self.theme_button.setToolTip('تغییر واقعی تم روز و شب؛ مستقل از داده پروژه')
        self.motion_button.setToolTip('فعال یا خاموش کردن حرکت‌های نمایشی؛ مقادیر متره تغییر نمی‌کنند')
        self.glass_button.setToolTip('شیشه‌ای یا ساده کردن نوارهای رابط برای سیستم‌های ضعیف')
        for button, name in ((self.theme_button, 'تم روز و شب'),
                             (self.motion_button, 'کاهش حرکت رابط'),
                             (self.glass_button, 'نمای شیشه‌ای رابط')):
            button.setAccessibleName(name)
        def labels():
            self.theme_button.setText('تم روز' if self.theme == 'dark' else 'تم شب')
            self.motion_button.setText('حرکت: فعال' if self.animations else 'حرکت: خاموش')
            self.glass_button.setText('نمای ساده' if self.glass_enabled else 'نمای شیشه‌ای')
        def theme():
            self.theme = 'light' if self.theme == 'dark' else 'dark'
            self.settings.setValue('theme', self.theme); self.settings.sync(); self.apply(); labels()
        def motion():
            self.animations = not self.animations
            self.settings.setValue('animations', self.animations); self.settings.sync(); self.apply(); labels()
        def glass():
            self.glass_enabled = not self.glass_enabled
            self.settings.setValue('glass_enabled', self.glass_enabled)
            self.settings.sync(); self.apply(); labels()
        self.theme_button.clicked.connect(theme)
        self.motion_button.clicked.connect(motion)
        self.glass_button.clicked.connect(glass)
        labels()
        layout.addWidget(self.theme_button)
        layout.addWidget(self.motion_button)
        layout.addWidget(self.glass_button)
