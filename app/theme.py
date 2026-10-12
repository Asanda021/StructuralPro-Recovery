"""StructuralPro professional RTL desktop theme."""
APP_STYLESHEET = r"""
* { font-family: "Vazirmatn","Segoe UI",Tahoma,sans-serif; font-size: 10.5pt; }
QMainWindow, QWidget { background: #f4f7fb; color: #172033; }
QWidget:focus { outline: none; }
QPushButton:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus, QTableWidget:focus, QListWidget:focus { border: 1px solid #2d6da3; }
QScrollBar:vertical { background: #eef3f8; width: 10px; margin: 2px; border-radius: 5px; }
QScrollBar::handle:vertical { background: #aebfd2; min-height: 28px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #8fa8c0; }
QScrollBar:horizontal { background: #eef3f8; height: 10px; margin: 2px; border-radius: 5px; }
QScrollBar::handle:horizontal { background: #aebfd2; min-width: 28px; border-radius: 5px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
#TopShell { background: rgba(16,35,63,238); border-bottom: 1px solid rgba(214,226,240,110); }
#NavigationPanel { background: #10233f; border-left: 1px solid #d6deea; }
#NavGroupLabel { color: #8fa9c7; font-size: 8.5pt; font-weight: 700; padding: 10px 14px 2px; }
#NavigationPanel QToolTip { background: #0d1b2f; color: #ffffff; }
#BrandTitle { color: white; font-size: 20pt; font-weight: 800; padding: 2px 4px; }
#EditionBadge { color: #dbe7f7; background: #1b385f; border: 1px solid #315a82; border-radius: 14px; padding: 5px 12px; font-weight: 700; }
#ShellStatus { color: #dbe7f7; padding: 4px 8px; }
#MainNavigationTabs { background: rgba(16,35,63,178); min-height: 48px; border: 1px solid rgba(214,226,240,85); border-radius: 12px; padding: 3px; }
#MainNavigationTabs::pane { border: 0; }
#MainNavigationTabs::tab { color: #e6eff9; background: rgba(255,255,255,18); border: 1px solid rgba(255,255,255,24); border-radius: 8px; padding: 10px 14px; min-height: 24px; font-weight: 600; }
#MainNavigationTabs::tab:hover { background: rgba(120,183,232,70); color: white; border-color: rgba(190,220,245,95); }
#MainNavigationTabs::tab:selected { background: rgba(36,90,145,205); color: white; border: 1px solid rgba(120,183,232,180); border-bottom: 3px solid #78b7e8; font-weight: 800; }
#DashboardSection { background: white; border: 1px solid #dce4ef; border-radius: 12px; }
#DashboardAction { background: #f7fafc; border: 1px solid #cbd8e6; border-radius: 9px; color: #173b5f; font-weight: 700; }
#DashboardAction:hover { background: #e7f1fa; border-color: #7fa8c8; }
#DashboardSummary { background: #f7fafc; border: 1px solid #dce4ef; border-radius: 8px; padding: 12px; }
#DashboardNotice { background: #eef5fb; border: 1px solid #d2e1ee; border-radius: 8px; padding: 10px; color: #294c6b; }
#NavigationPanel QLabel { color: #dbe7f7; }
#NavButton { color: #dbe7f7; background: transparent; border: 0; border-radius: 8px; padding: 10px 14px; text-align: right; }
#NavButton:hover { background: #1b385f; }
#NavButton:pressed { background: #214b78; }
#NavButton:focus { border: 1px solid #5d91bd; }
#NavButton:checked { background: #245a91; color: white; font-weight: 700; }
#ContentPage { background: #f7f9fc; }
#HelpPanel { background: white; border: 1px solid #dce4ef; border-radius: 10px; padding: 16px; }
#PageTitle { color: #12233f; font-size: 20pt; font-weight: 800; }
#PageDescription { color: #62708a; font-size: 10.5pt; }
#KpiCard { background: white; border: 1px solid #dce4ef; border-radius: 10px; padding: 12px; }
#SectionTitle { color: #17345b; font-size: 13pt; font-weight: 700; padding-top: 6px; }
#DashboardCard, QGroupBox { background: white; border: 1px solid #dce4ef; border-radius: 10px; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { background: white; border: 1px solid #cbd6e4; border-radius: 7px; padding: 7px; selection-background-color: #2d6da3; min-height: 20px; }
QPushButton { background: #e8eef6; border: 1px solid #cbd6e4; border-radius: 7px; padding: 8px 13px; min-height: 34px; font-weight: 600; }
QPushButton:disabled { background: #eef2f6; color: #9aa7b7; border-color: #e1e7ee; }
QPushButton:hover { background: #dce8f5; }
#PrimaryAction { background: #1769aa; color: white; border: 0; font-weight: 700; }
#PrimaryAction:hover { background: #0f5b97; }
#SecondaryAction { background: white; border: 1px solid #8aa8c5; color: #204e76; font-weight: 600; }
QTableWidget { background: white; border: 1px solid #d6dfeb; border-radius: 8px; gridline-color: #e5ebf3; alternate-background-color: #f7fafd; selection-background-color: #dcecf8; selection-color: #132b44; }
QHeaderView::section { background: #e9eff7; color: #253957; padding: 9px 8px; border: 0; border-bottom: 1px solid #d4deea; font-weight: 700; }
QStatusBar { background: #10233f; color: #e7f0fb; }
QToolTip { background: #172b47; color: white; border: 0; padding: 6px; }
#WorkspaceHero { background: #ffffff; border: 1px solid #d7e2ee; border-radius: 14px; padding: 8px; }
#AECWorkspace QGroupBox { margin-top: 8px; padding: 18px 14px 12px; font-weight: 700; color: #17345b; }
#AECWorkspace QGroupBox::title { subcontrol-origin: margin; right: 14px; padding: 0 7px; background: #ffffff; }
#AECWorkspace QDoubleSpinBox:disabled { background: #f2f5f8; color: #9aa7b7; }
#AECWorkspace QTableWidget { min-height: 240px; }
#AECWorkspace QPushButton#PrimaryAction { min-height: 42px; border-radius: 9px; }
QTabBar::tab { background: #e8eef6; padding: 9px 16px; border: 1px solid #d1dbe8; }
QTabBar::tab:selected { background: white; font-weight: 700; }
#PlanSwiftNavigation { background: #10233f; color: #dbe7f7; border: 0; border-left: 1px solid #d6deea; padding: 10px 7px; }
#PlanSwiftNavigation::item { padding: 9px 10px; margin: 2px 3px; border-radius: 7px; }
#PlanSwiftNavigation::item:hover { background: #1b385f; }
#PlanSwiftNavigation::item:selected { background: #245a91; color: white; font-weight: 800; }
#PlanSwiftNavigation::branch { background: #10233f; }
#CommandRibbon { background: rgba(247,249,252,235); border-top: 1px solid rgba(217,224,234,210); border-bottom: 1px solid rgba(217,224,234,210); border-radius: 0 0 10px 10px; }
#CommandRibbon QPushButton { min-height: 34px; padding: 5px 13px; border-radius: 6px; font-weight: 600; }
#CommandRibbon QPushButton#RibbonAction { background: #ffffff; border: 1px solid #cbd5e1; }
#CommandRibbon QPushButton#RibbonAction:hover { background: #eef4fb; }
#CommandRibbon QPushButton#RibbonPrimary { background: #e9f2ff; border: 1px solid #8fb7e8; }
#CommandRibbon QPushButton#RibbonPrimary:hover { background: #dcecff; }
"""
