from core.ui.ux import DEFAULT_ACTIONS,navigation_groups,quick_status

def test_ux_actions_have_unique_shortcuts_and_labels():
    assert len({x.key for x in DEFAULT_ACTIONS})==len(DEFAULT_ACTIONS)
    assert len({x.shortcut for x in DEFAULT_ACTIONS})==len(DEFAULT_ACTIONS)
    assert all(x.label and x.tooltip for x in DEFAULT_ACTIONS)

def test_navigation_groups_cover_current_core_sections():
    names={n for _,items in navigation_groups() for n in items}
    assert {"داشبورد","پروژه‌ها","متره سریع","متره از نقشه","برآورد و BOQ","راهنما"} <= names

def test_quick_status_is_persian_and_deterministic():
    assert quick_status(project_name="Demo",dirty=True)=="Demo  |  ● تغییر ذخیره‌نشده  |  حالت آفلاین"


def test_theme_exposes_accessible_focus_and_help_styles():
    from app.theme import APP_STYLESHEET
    assert "#NavGroupLabel" in APP_STYLESHEET
    assert "#HelpPanel" in APP_STYLESHEET
    assert "QPushButton:focus" in APP_STYLESHEET
    assert "QPushButton:disabled" in APP_STYLESHEET

def test_navigation_groups_are_ordered_for_desktop_workflow():
    groups=navigation_groups()
    assert [name for name,_ in groups]==["شروع","متره و برآورد","مدیریت پروژه","کنترل و ابزار","سیستم"]
    assert groups[1][1]==("متره سریع","متره از نقشه","فهرست‌بها","برآورد و BOQ")
