"""Synthetic P8/P2 legacy SHX tests. No private source, raw text or handles."""
from types import SimpleNamespace
import pytest

from core.cad.persian_text_v1 import is_legacy_shx_text_candidate
from core.drawings.dwg_shx_source_audit import validate_private_shx_ledger, classify_shx_record


@pytest.mark.parametrize('sample', [
    'Xµ‰؛',        # Arabic punctuation is NOT a decoded Arabic letter.
    'Q\u200c،',     # ZWNJ plus Arabic comma are NOT a glyph-mapping oracle.
    'Q—‰،',       # Mixed legacy bytes/display punctuation.
])
def test_legacy_shx_flags_are_not_cleared_by_arabic_punctuation(sample):
    assert is_legacy_shx_text_candidate(sample, 2) is True


def test_native_text_with_arabic_letters_does_not_trigger_specific_legacy_heuristic():
    assert is_legacy_shx_text_candidate('سلام دنیا', 2) is False
    # Non-candidate is still NOT proof of an SHX mapping.


@pytest.mark.parametrize('flag', [0, 1, 4, None, 'unknown'])
def test_nonlegacy_generation_flags_do_not_assert_legacy_candidate(flag):
    assert is_legacy_shx_text_candidate('Xµ‰؛', flag) is False


def sample_record():
    return {
        'handle': 'A1',
        'source_sha256': 'a' * 64,
        'entity_type': 'TEXT',
        'style_handle': '1A',
        'font_file': 'EXAMPLE.shx',
        'raw_tv_hex': 'aabbcc',
        'raw_tv_byte_count': '3',
        'decoded_unicode': 'Xµ‰؛',
        'glyph_mapping': 'UNKNOWN_ORIGINAL_SHX_NOT_PRESENT',
    }


def test_private_roster_validate_without_approving_glyph():
    ledger = validate_private_shx_ledger([sample_record()], source_sha256='a' * 64)
    assert ledger[0]['handle'] == 'A1'
    assert ledger[0]['glyph_mapping'] == 'UNKNOWN_ORIGINAL_SHX_NOT_PRESENT'


@pytest.mark.parametrize('field,value', [
    ('source_sha256', 'f' * 64), ('raw_tv_hex', 'bad!'),
    ('raw_tv_byte_count', '2'), ('font_file', 'example.ttf'),
    ('glyph_mapping', 'VERIFIED'), ('entity_type', 'LINE'),
])
def test_private_shx_source_ledger_rejects_untrusted_evidence(field, value):
    row = sample_record()
    row[field] = value
    with pytest.raises(ValueError):
        validate_private_shx_ledger([row], source_sha256='a' * 64)


def test_duplicate_handles_rejected():
    with pytest.raises(ValueError, match='Duplicate'):
        validate_private_shx_ledger([sample_record(), sample_record()], source_sha256='a' * 64)


class TextEntity:
    def __init__(self, text, owner='2'):
        self.dxf = SimpleNamespace(get=lambda k, default=None: {'text': text, 'owner': owner}.get(k, default))

    def dxftype(self):
        return 'TEXT'


def test_native_direct_modelspace_string_match_never_approves_mapping():
    native = TextEntity('Xµ‰؛')
    converted = TextEntity('Xµ‰؛')
    got = classify_shx_record(sample_record(), native, converted,
                              modelspace_record_handle='2')
    assert got['source_location_status'] == 'NATIVE_DIRECT_MODELSPACE_RAW_TEXT_MATCHED_GLYPHS_UNVERIFIED'
    assert got['native_text_equal_ledger'] is True
    assert got['glyph_mapping_verified'] is False
    assert got['financial_quantity_approved'] is False


def test_text_in_dxf_block_definition_not_falsely_reported_as_dropped():
    got = classify_shx_record(sample_record(), None, TextEntity('Xµ‰؛', owner='CA'),
                              modelspace_record_handle='2')
    assert got['source_location_status'] == 'DXF_NON_MODELSPACE_DEFINITION_ONLY'
    assert got['dxf_owner_is_modelspace'] is False
    assert got['dimension_reference_approved'] is False


def test_text_missing_dxf_is_not_certified():
    got = classify_shx_record(sample_record(), TextEntity('Xµ‰؛'), None,
                              modelspace_record_handle='2')
    assert got['source_location_status'] == 'MISSING_OR_RETYPE_CONVERTED_DXF'
    assert got['financial_quantity_approved'] is False


def test_source_text_changed_no_false_approval():
    got = classify_shx_record(sample_record(), TextEntity('DIFFERENT'),
                              TextEntity('Xµ‰؛'), modelspace_record_handle='2')
    assert got['source_location_status'] == 'SOURCE_TEXT_OR_OWNER_MISMATCH_UNVERIFIED'
    assert got['native_text_equal_ledger'] is False

class StyledTextEntity:
    def __init__(self, text, *, owner='2', style='EXAMPLE'):
        values = {'text': text, 'owner': owner, 'style': style}
        self.dxf = SimpleNamespace(get=lambda k, default=None: values.get(k, default))

    def dxftype(self):
        return 'TEXT'


def _styled_shx_ledger():
    row = sample_record()
    row['style_name'] = 'EXAMPLE'
    return row


def test_real_dxf_unicode_escape_syntax_not_counted_as_changed_shx_text():
    row = _styled_shx_ledger()
    native = StyledTextEntity('Xµ‰؛')
    converted = StyledTextEntity(r'Xµ‰\U+061B')
    result = classify_shx_record(
        row, native, converted, modelspace_record_handle='2',
        dxf_style_font_file=r'C:\fonts\EXAMPLE.SHX',
    )
    assert result['dxf_raw_text_equal_ledger'] is False
    assert result['dxf_text_matches_ledger_after_unicode_escape_decoding'] is True
    assert result['dxf_unicode_escape_normalization_only'] is True
    assert result['dxf_style_name_matches_ledger'] is True
    assert result['dxf_style_font_matches_ledger_filename'] is True
    assert result['source_location_status'] == 'NATIVE_DIRECT_MODELSPACE_RAW_TEXT_MATCHED_GLYPHS_UNVERIFIED'
    assert result['glyph_mapping_verified'] is False
    assert result['financial_quantity_approved'] is False


def test_genuinely_changed_dxf_unicode_content_rejected_despite_native_match():
    row = _styled_shx_ledger()
    result = classify_shx_record(
        row, StyledTextEntity('Xµ‰؛'),
        StyledTextEntity(r'Xµ‰\U+061C'),
        modelspace_record_handle='2', dxf_style_font_file='EXAMPLE.shx',
    )
    assert result['native_text_equal_ledger'] is True
    assert result['dxf_text_matches_ledger_after_unicode_escape_decoding'] is False
    assert result['source_location_status'] == 'CONVERTED_DXF_TEXT_DIFFERENT_FROM_SOURCE_LEDGER_NO_GO'
    assert not result['financial_quantity_approved']


@pytest.mark.parametrize('style,font', [
    ('DIFFERENT', 'EXAMPLE.shx'),
    ('EXAMPLE', 'OTHER.shx'),
    ('EXAMPLE', None),
])
def test_dxf_style_or_font_drift_cannot_get_text_preservation_status(style, font):
    row = _styled_shx_ledger()
    result = classify_shx_record(
        row, StyledTextEntity('Xµ‰؛'),
        StyledTextEntity(r'Xµ‰\U+061B', style=style),
        modelspace_record_handle='2', dxf_style_font_file=font,
    )
    assert result['dxf_text_matches_ledger_after_unicode_escape_decoding'] is True
    assert result['source_location_status'] == 'CONVERTED_DXF_STYLE_OR_FONT_MISMATCH_UNVERIFIED'
    assert result['glyph_mapping_verified'] is False


def test_non_modelspace_definition_with_unicode_escapes_remains_non_modelspace():
    row = _styled_shx_ledger()
    result = classify_shx_record(
        row, None, StyledTextEntity(r'Xµ‰\U+061B', owner='3'),
        modelspace_record_handle='2', dxf_style_font_file='EXAMPLE.shx',
    )
    assert result['source_location_status'] == 'DXF_NON_MODELSPACE_DEFINITION_ONLY'
    assert result['dxf_text_matches_ledger_after_unicode_escape_decoding'] is True
    assert result['financial_quantity_approved'] is False
