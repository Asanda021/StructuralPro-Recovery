from core.estimate.item_code_normalization_v1 import normalize_item_code, code_key

def test_digit_normalization():
    assert normalize_item_code(' ۱۲-٠٣ ') == '12-03'

def test_unicode_dash_and_spaces():
    assert normalize_item_code('12 – 03') == '12-03'

def test_leading_zero_preserved():
    assert normalize_item_code('0012') == '0012'

def test_unit_is_separate_key():
    assert code_key('۱۲۳','m3') == ('123','m3')
