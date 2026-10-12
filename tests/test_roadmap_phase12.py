from core.ui.ux import DEFAULT_ACTIONS, navigation_groups, quick_status
from core.help.content import topics

def test_phase12_persian_navigation_help_and_status_contract():
    assert len({item.key for item in DEFAULT_ACTIONS}) == len(DEFAULT_ACTIONS)
    assert len({item.shortcut for item in DEFAULT_ACTIONS}) == len(DEFAULT_ACTIONS)
    assert all(item.label and item.tooltip for item in DEFAULT_ACTIONS)
    names = {name for _, items in navigation_groups() for name in items}
    assert {"داشبورد", "پروژه‌ها", "متره سریع", "متره از نقشه", "برآورد و BOQ", "راهنما"} <= names
    assert {"start", "takeoff", "reports", "recovery", "ai"} <= {item.key for item in topics()}
    assert quick_status(project_name="پروژه نمونه", dirty=True) == (
        "پروژه نمونه  |  ● تغییر ذخیره‌نشده  |  حالت آفلاین"
    )

def test_phase12_accessibility_styles_remain_available():
    from app.theme import APP_STYLESHEET
    assert "QPushButton:focus" in APP_STYLESHEET
    assert "QPushButton:disabled" in APP_STYLESHEET
