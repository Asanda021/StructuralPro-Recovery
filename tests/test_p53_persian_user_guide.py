from pathlib import Path

from core.help.content import topics


def test_persian_help_catalog_has_user_workflow_topics():
    keys = {item.key for item in topics()}
    assert {"start", "takeoff", "reports", "recovery", "ai"} <= keys


def test_desktop_menu_integrates_searchable_persian_help():
    source = Path("app/main.py").read_text(encoding="utf-8")
    expected_sections = [
        "داشبورد", "پروژه‌ها", "متره سریع", "متره از نقشه", "فهرست‌بها",
        "برآورد و BOQ", "صورت‌وضعیت", "گزارشات", "اسناد پروژه",
        "ابزارهای حرفه‌ای", "کنترل کیفیت", "هوش مصنوعی آفلاین", "تنظیمات", "راهنما",
    ]
    for section in expected_sections:
        assert section in source
    assert "from core.help.content import topics as help_topics, search as search_help_topics" in source
    assert 'help_search.setPlaceholderText("جستجو در راهنما؛ مثال: متره، گزارش، پشتیبان")' in source
    assert "help_topic.addItem" in source
