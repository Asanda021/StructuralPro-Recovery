from core.takeoff.manual_input import parse_manual_batch, parse_manual_entry
import pytest

def test_persian_column_quick_entry():
    r=parse_manual_entry("۱۲ ستون 50cmx50cm ارتفاع 3m")
    assert r.code=="column"
    assert r.params["count"]==12
    assert r.params["width"]==0.5
    assert r.params["depth"]==0.5
    assert r.params["height"]==3
    assert r.complete

def test_named_column_entry_needs_only_missing_geometry():
    r=parse_manual_entry("ستون: تعداد=12، عرض=0.5، عمق=0.5")
    assert r.code=="column"
    assert r.missing==("height",)

def test_manual_batch_accepts_multiple_operations():
    rows=parse_manual_batch("ستون: تعداد=12، عرض=0.5، عمق=0.5، ارتفاع=3; تیر: تعداد=18، طول=5.2، عرض=0.3، عمق=0.5")
    assert len(rows)==2
    assert rows[0].complete and rows[1].complete

def test_manual_input_never_invents_missing_values():
    r=parse_manual_entry("پله: تعداد=1، عرض=1.2")
    assert not r.complete
    assert "sloped_length" in r.missing
    assert "waist_thickness" in r.missing


def test_compact_dimensions_do_not_supply_missing_column_count():
    entry = parse_manual_entry("ستون 50cmx50cm ارتفاع 3m")
    assert "count" in entry.missing
    assert "count" not in entry.params


def test_height_is_not_misread_as_column_count():
    entry = parse_manual_entry("ستون ارتفاع 3")
    assert "count" not in entry.params


def test_fractional_count_is_rejected():
    with pytest.raises(ValueError, match="صحیح"):
        parse_manual_entry("ستون تعداد=1.5 عرض=0.3 عمق=0.4 ارتفاع=3")


def test_named_dimensions_convert_each_explicit_unit_independently():
    entry = parse_manual_entry("ستون تعداد=2 عرض=30cm عمق=400mm ارتفاع=3m")
    assert entry.params == {"count": 2, "width": .3, "depth": .4, "height": 3}
    assert entry.complete


def test_long_labels_do_not_overwrite_other_geometry_fields():
    entry = parse_manual_entry("تیرچه بلوک تعداد=1 طول=5 عرض=4 ضخامت رویه=0.05 فاصله تیرچه=0.5 عرض تیرچه=0.1 عمق تیرچه=0.2")
    assert entry.params["width"] == 4
    assert entry.params["joist_width"] == .1
    assert entry.params["joist_depth"] == .2


@pytest.mark.parametrize("text", ["ستون تعداد=2 تعداد=3", "ستون عرض=0,5", "ستون تعداد=2m"])
def test_conflicting_or_ambiguous_manual_values_are_rejected(text):
    with pytest.raises(ValueError):
        parse_manual_entry(text)


def test_invalid_exponent_is_not_truncated_into_a_valid_dimension():
    entry = parse_manual_entry("ستون تعداد=2 عرض=1e999 عمق=0.4 ارتفاع=3")
    assert "width" in entry.missing


def test_compact_mixed_units_do_not_apply_one_global_conversion():
    entry = parse_manual_entry("2 ستون 30cmx400mm ارتفاع=300cm")
    assert entry.params == {"count": 2, "height": 3, "width": .3, "depth": .4}


def test_compact_dimensions_and_named_dimensions_cannot_conflict():
    with pytest.raises(ValueError, match="متعارض"):
        parse_manual_entry("2 ستون 30cmx40cm عرض=0.5 ارتفاع=3")
