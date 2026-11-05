"""Synthetic safety tests only. Private DWG bytes and class names not included."""
import pytest
from core.drawings.dwg_opaque_source_receipt import (
  _handles,summarize_raw_records,opaque_recovery_decision,
  summarize_converted_opaque_identity_coverage)


def sample():
    return [(0x101,100,2,514,[12,22,24,33,44,55]),(0x102,200,1,515,[8,4,2,1,9])]


def links(count=2):
    return {'policy':'p8p2_dxf_named_dictionary_links_v1',
            'financial_quantity_approved':False,'dangling_or_invalid_count':count,
            'converted_dxf_namespace_integrity_status':'BROKEN_DXF_DICTIONARY_LINKS',
            'dangling_or_invalid_references':[{'target_handle':'101'}]*(count or 0)}


def test_exact_independent_record_receipts_are_only_hashes():
    receipts=summarize_raw_records(sample(),['101','102'])
    assert [r['handle'] for r in receipts]==['101','102']
    assert all(len(r['raw_record_sha256'])==64 and r['proprietary_payload_semantics_verified'] is False for r in receipts)
    assert all(not isinstance(v, (bytes,bytearray,list,tuple)) for r in receipts for v in r.values())


@pytest.mark.parametrize('records',[
    sample()[:1], sample()+sample()[:1],
    [(0x101,100,12,514,[12,256])]+sample()[1:],
    [(0x101,-100,12,514,[12,22])]+sample()[1:],
    [(0x101,100,12,514,[])]+sample()[1:],
    [(0x101,100,12,514,[True])]+sample()[1:],
    [(0x101,100,12,514,'private')]+sample()[1:],
    [(0x999,100,12,514,[12])]+sample()[1:],
])
def test_reject_untrusted_raw_record_shape(records):
    with pytest.raises(ValueError): summarize_raw_records(records,['101','102'])


@pytest.mark.parametrize('handles', [['101','101'],['ZZ'],[],[0],['-1'],[True],['0'],list(range(70))])
def test_reject_invalid_handles(handles):
    with pytest.raises(ValueError):_handles(handles)


def test_missing_dxf_links_never_authorizes_automatic_patch():
    x=opaque_recovery_decision(summarize_raw_records(sample(),['101','102']),links(),
                               expected_source_sha256='a'*64,converted_dxf_sha256='b'*64)
    assert x['source_record_count']==2
    assert x['converted_dxf_dangling_ref_count']==2
    assert x['automatic_patch_authorized'] is False
    assert x['financial_quantity_approved'] is False
    assert x['engineering_acceptance']=='PARTIAL_NO_GO'


def test_no_dangling_links_does_not_prove_source_completeness():
    x=opaque_recovery_decision(summarize_raw_records(sample(),['101','102']),links(0),
                               expected_source_sha256='a'*64,converted_dxf_sha256='b'*64)
    assert x['automatic_patch_authorized'] is False
    assert x['full_source_graph_verified'] is False


def test_indeterminate_dictionary_graph_blocks_repair():
    x=opaque_recovery_decision(summarize_raw_records(sample(),['101','102']),links(None),
                               expected_source_sha256='a'*64,converted_dxf_sha256='b'*64)
    assert x['status']=='INDETERMINATE_DXF_DICTIONARY_GRAPH'
    assert x['automatic_patch_authorized'] is False


def test_fake_green_approval_rejected():
    bad=links();bad['financial_quantity_approved']=True
    with pytest.raises(ValueError):opaque_recovery_decision([{'handle':'101'}],bad,
                       expected_source_sha256='a'*64,converted_dxf_sha256='b'*64)

def test_source_opaque_identity_loss_is_reported_without_handles_or_repair():
    from types import SimpleNamespace
    source = [{'handle': '10'}, {'handle': '20'}]
    dxf = SimpleNamespace(entitydb={'10': object()})
    got = summarize_converted_opaque_identity_coverage(source, dxf)
    assert got['source_opaque_identity_count'] == 2
    assert got['converted_dxf_identity_present_count'] == 1
    assert got['converted_dxf_identity_missing_count'] == 1
    assert got['converted_dxf_opaque_identity_status'] == 'SOURCE_OPAQUE_OBJECT_IDENTITIES_MISSING_NO_GO'
    assert got['automatic_reconstruction_authorized'] is False
    assert got['financial_quantity_approved'] is False
    assert '10' not in str(got) and '20' not in str(got)


def test_source_opaque_identity_present_does_not_validate_payload():
    from types import SimpleNamespace
    source = [{'handle': '000A'}]
    # A totally different DXF type with the same ID must NOT be called recovered.
    dxf = SimpleNamespace(entitydb={'A': object()})
    got = summarize_converted_opaque_identity_coverage(source, dxf)
    assert got['converted_dxf_identity_missing_count'] == 0
    assert got['converted_dxf_opaque_identity_status'] == 'SOURCE_IDENTITIES_PRESENT_PAYLOAD_UNVERIFIED_NO_GO'
    assert got['converted_opaque_payload_bytes_independently_verified'] is False
    assert got['financial_quantity_approved'] is False


@pytest.mark.parametrize('bad', [
    [], [{}], [{'handle': '0'}], [{'handle': 'GG'}],
    [{'handle': 'A'}, {'handle': '0A'}],
    [{'handle': 10}], ['A'], [None], [{'handle': ''}],
])
def test_invalid_source_opaque_identity_coverage_fails_closed(bad):
    from types import SimpleNamespace
    with pytest.raises(ValueError):
        summarize_converted_opaque_identity_coverage(
            bad, SimpleNamespace(entitydb={}))


def test_reused_opaque_handle_as_standard_line_is_not_preserved_custom_object():
    from types import SimpleNamespace
    source = [{'handle': '10'}]
    line = SimpleNamespace(dxftype=lambda: 'LINE')
    got = summarize_converted_opaque_identity_coverage(
        source, SimpleNamespace(entitydb={'10': line}))
    assert got['converted_dxf_identity_present_count'] == 1
    assert got['converted_dxf_identity_missing_count'] == 0
    assert got['converted_dxf_identity_reused_as_standard_type_count'] == 1
    assert got['converted_dxf_opaque_identity_status'] == 'SOURCE_OPAQUE_IDENTITIES_REUSED_AS_STANDARD_NO_GO'
    assert got['financial_quantity_approved'] is False
    assert '10' not in str(got)


def test_opaque_handle_proxy_is_replacement_not_semantic_recovery():
    from types import SimpleNamespace
    result = summarize_converted_opaque_identity_coverage(
        [{'handle': 'A'}],
        SimpleNamespace(entitydb={'A': SimpleNamespace(dxftype=lambda: 'ACAD_PROXY_OBJECT')}))
    assert result['converted_dxf_identity_replaced_by_proxy_count'] == 1
    assert result['converted_dxf_opaque_identity_status'] == 'SOURCE_OPAQUE_IDENTITIES_REPLACED_BY_PROXY_NO_GO'
    assert not result['source_record_payload_semantics_verified']


def test_opaque_present_unreadable_type_is_explicitly_unverified():
    from types import SimpleNamespace
    result = summarize_converted_opaque_identity_coverage(
        [{'handle': 'A'}], SimpleNamespace(entitydb={'A': object()}))
    assert result['converted_dxf_identity_type_unreadable_count'] == 1
    assert result['converted_dxf_identity_custom_type_unverified_count'] == 0
    assert result['converted_dxf_opaque_identity_status'] == 'SOURCE_IDENTITIES_PRESENT_PAYLOAD_UNVERIFIED_NO_GO'


def test_opaque_present_unknown_custom_type_still_never_claims_parity():
    from types import SimpleNamespace
    custom = SimpleNamespace(dxftype=lambda: 'DMMAPMANAGER')
    result = summarize_converted_opaque_identity_coverage(
        [{'handle': 'A'}], SimpleNamespace(entitydb={'A': custom}))
    assert result['converted_dxf_identity_custom_type_unverified_count'] == 1
    assert result['converted_dxf_identity_reused_as_standard_type_count'] == 0
    assert not result['converted_opaque_payload_bytes_independently_verified']
    assert not result['financial_quantity_approved']


def test_mixed_opaque_source_loss_collision_and_proxy_counts_without_ids():
    from types import SimpleNamespace
    source = [{'handle': 'A'}, {'handle': 'B'}, {'handle': 'C'}, {'handle': 'D'}]
    dxf = SimpleNamespace(entitydb={
        'A': SimpleNamespace(dxftype=lambda: 'LINE'),
        'B': SimpleNamespace(dxftype=lambda: 'ACAD_PROXY_ENTITY'),
        'C': SimpleNamespace(dxftype=lambda: 'DMMAPMANAGER')})
    result = summarize_converted_opaque_identity_coverage(source, dxf)
    assert result['converted_dxf_identity_present_count'] == 3
    assert result['converted_dxf_identity_missing_count'] == 1
    assert result['converted_dxf_identity_reused_as_standard_type_count'] == 1
    assert result['converted_dxf_identity_replaced_by_proxy_count'] == 1
    assert result['converted_dxf_identity_custom_type_unverified_count'] == 1
    assert result['converted_dxf_opaque_identity_status'] == 'SOURCE_OPAQUE_OBJECT_IDENTITIES_MISSING_NO_GO'
    assert not any(x in str(result) for x in ['DMMAPMANAGER', 'ACAD_PROXY_ENTITY'])
    assert result['automatic_reconstruction_authorized'] is False


@pytest.mark.parametrize('bad_handle', ['1' + '0'*16, 'F'*65, '0'*64, 'F'*64])
def test_opaque_source_handle_outside_64_bit_scope_is_rejected(bad_handle):
    from types import SimpleNamespace
    with pytest.raises(ValueError):
        summarize_converted_opaque_identity_coverage(
            [{'handle': bad_handle}], SimpleNamespace(entitydb={}))


def test_private_map_aec_cli_never_prints_reader_exception_details(monkeypatch, capsys):
    from pathlib import Path
    import sys
    import tools.audit_phase8_p2_opaque_source_bytes as cli
    secret = 'PRIVATE_DWG_PATH_AND_CLASS_HANDLE_SHOULD_NEVER_BE_LOGGED'
    monkeypatch.setattr(sys, 'argv', [
        'p8p2-opaque-audit', '/private/source.dwg', '/private/result.dxf',
        '/private/report.json', '--private-config', '/private/config.json',
    ])
    monkeypatch.setattr(cli, 'private_output_destination', lambda path: Path(path))
    monkeypatch.setattr(cli, 'read_private_config', lambda path: (['A'], 'f'*64))

    def private_source_failure(*args, **kwargs):
        raise ValueError(secret)

    monkeypatch.setattr(cli, 'audit_original_opaque_records', private_source_failure)
    assert cli.main() == 2
    output = capsys.readouterr().out
    assert 'BLOCKED_NO_SAFE_SOURCE_RECEIPT: ValueError' in output
    assert secret not in output
    assert '/private/source.dwg' not in output
    assert '/private/config.json' not in output
