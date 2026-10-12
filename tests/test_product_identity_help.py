from core.help.content import topic


def test_about_help_topic_contains_official_identity():
    about = topic("about")
    text = " ".join((about.title, about.summary, *about.steps))
    assert "StructuralPro" in text
    assert "مهندس محمد سلطانی" in text
    assert "ERVIRA.ir" in text
    assert "۱۴۰۵/۰۷/۱۴" in text
