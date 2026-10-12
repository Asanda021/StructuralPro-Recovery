from pathlib import Path

def test_commercial_ui_design_tokens_exist():
    css=Path("app/theme.py").read_text(encoding="utf-8")
    for token in ("#PrimaryAction","#SecondaryAction","#KpiCard","#PageTitle","#NavButton"):
        assert token in css

def test_dashboard_and_graphical_takeoff_modules_exist():
    assert Path("app/dashboard.py").exists()
    assert Path("app/graphical_takeoff.py").exists()


def test_operational_pages_use_primary_actions():
    from pathlib import Path
    src=Path("app/main.py").read_text(encoding="utf-8")
    for marker in ("# Pricing","# BOQ","# Reports","# Commercial statement"):
        assert marker in src
    assert src.count('setObjectName("PrimaryAction")') >= 4


def test_priority8_rtl_and_accessibility_tokens():
    css=Path("app/theme.py").read_text(encoding="utf-8")
    assert "font-family" in css and "QToolTip" in css and "#NavigationPanel" in css
    src=Path("app/main.py").read_text(encoding="utf-8")
    assert "setLayoutDirection(Qt.LayoutDirection.RightToLeft)" in src
