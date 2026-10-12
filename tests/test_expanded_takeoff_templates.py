from core.takeoff.templates import DEFAULT_TEMPLATES, TemplateLibrary


def test_template_catalog_has_core_aec_manual_takeoff_coverage():
    library = TemplateLibrary()
    codes = {template.code for template in library.search()}
    assert {
        "WALL-AREA", "FLOOR-AREA", "COLUMN-VOL", "BEAM-VOL", "FOOT-VOL",
        "SHEAR-WALL-VOL", "EXCAVATION-VOL", "REBAR-WEIGHT", "STEEL-WEIGHT",
        "STAIR-VOL", "JOIST-BLOCK", "JOIST-FOAM", "MASONRY-BLOCK",
    } <= codes


def test_every_template_declares_inputs_and_a_unit():
    for template in DEFAULT_TEMPLATES:
        assert template.fields, template.code
        assert template.formula, template.code
        assert template.unit, template.code
        assert len(set(template.fields)) == len(template.fields), template.code


def test_search_is_case_insensitive_and_searches_persian_names():
    library = TemplateLibrary()
    assert library.get("COLUMN-VOL").name == "ستون بتنی"
    assert "MASONRY-BLOCK" in {item.code for item in library.search("بلوک")}


def test_unknown_template_fails_closed():
    library = TemplateLibrary()
    try:
        library.get("NOT-A-TEMPLATE")
    except KeyError as exc:
        assert "ناشناخته" in str(exc)
    else:
        raise AssertionError("unknown template must be rejected")


def test_duplicate_template_codes_are_rejected():
    duplicate = DEFAULT_TEMPLATES[0]
    try:
        TemplateLibrary((duplicate, duplicate))
    except ValueError as exc:
        assert "تکراری" in str(exc)
    else:
        raise AssertionError("duplicate template codes must be rejected")
