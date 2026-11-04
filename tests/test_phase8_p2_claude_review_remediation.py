"""Regression for Claude PR47 findings F01-F04, F05-F11 (synthetic only).

Original source engineering, vendor-object semantics and payable geometry remain
NO-GO.  Tests intentionally contain no private CAD, handles or SHA receipts.
"""
from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import sys
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from core.drawings.dwg_converter import (
    DWGConversionError, OfflineDWGConverter, _independent_source_coverage,
)
from core.drawings.dwg_source_display_integrity import audit_named_dictionary_links
from core.drawings.dwg_opaque_source_receipt import (
    summarize_raw_records, validate_object_map_entries, opaque_recovery_decision,
)
from core.drawings.dwg_opaque_conversion_diff import audit_opaque_conversion_loss
from tools.audit_phase8_p2_opaque_source_bytes import (
    private_output_destination, write_private_report, read_private_config,
)


def native_unit_audit(monkeypatch, native_unit, dxf_unit=6):
    dxf = ezdxf.new('R2018')
    dxf.header['$INSUNITS'] = dxf_unit
    line = dxf.modelspace().add_line((0, 0), (1, 2))
    handle = int(line.dxf.handle, 16)
    raw_entity = SimpleNamespace(handle=handle, dxftype='LINE')
    raw = SimpleNamespace(
        version='AC1018', units=native_unit,
        modelspace=lambda: SimpleNamespace(iter_entities=lambda: iter([raw_entity])))
    prev_spec = importlib.util.find_spec
    prev_version = importlib.metadata.version
    monkeypatch.setattr(importlib.util, 'find_spec',
                        lambda n: SimpleNamespace() if n == 'ezdwg' else prev_spec(n))
    monkeypatch.setattr(importlib.metadata, 'version',
                        lambda n: '0.17.0' if n == 'ezdwg' else prev_version(n))
    monkeypatch.setitem(sys.modules, 'ezdwg', SimpleNamespace(read=lambda _: raw))
    return _independent_source_coverage('synthetic.dwg', dxf, 'AC1018')


@pytest.mark.parametrize('unknown', [None, 'unitless', 'unknown_99', ''])
def test_f01_no_unknown_source_unit_ever_reports_matched(monkeypatch, unknown):
    r = native_unit_audit(monkeypatch, unknown)
    assert r['status'] == 'NOT_VERIFIED_UNIT'
    assert r['source_unit_code'] is None
    assert r['quantity_approved'] is False


def test_f01_valid_explicit_unit_match(monkeypatch):
    r = native_unit_audit(monkeypatch, 'meters', 6)
    assert r['status'] == 'MATCHED_INDEPENDENT_MODELSPACE_ROSTER'
    assert r['source_unit_code'] == 6


def test_f01_known_source_mismatched_header_rejected(monkeypatch):
    with pytest.raises(DWGConversionError, match='واحد'):
        native_unit_audit(monkeypatch, 'millimeters', 6)


class DictionaryStub(dict):
    def __init__(self, handle):
        super().__init__()
        self.dxf = SimpleNamespace(handle=handle)

    def dxftype(self):
        return 'DICTIONARY'


def fake_dictionary_doc(*, root_value=None, target=None, declared_class=None):
    root = DictionaryStub('1')
    namespace = DictionaryStub('2')
    root['Autodesk_MAP'] = namespace if root_value is None else root_value
    entitydb = {'1': root, '2': namespace}
    if target is not None:
        namespace['PAYLOAD'] = 'AA'
        entitydb['AA'] = target
    doc = SimpleNamespace(
        rootdict=root, objects=[root, namespace], entitydb=entitydb,
        classes=([SimpleNamespace(dxf=SimpleNamespace(name=declared_class))]
                 if declared_class else []))
    return doc


def test_f02_absent_namespaces_are_not_green():
    d = ezdxf.new('R2018')
    got = audit_named_dictionary_links(d)
    assert got['converted_dxf_namespace_integrity_status'] == 'NAMESPACES_ABSENT_NO_EVIDENCE'
    assert got['source_coverage_verified'] is False
    assert got['financial_quantity_approved'] is False


def test_f02_one_missing_namespace_stays_incomplete():
    d = fake_dictionary_doc()
    got = audit_named_dictionary_links(d)
    assert got['converted_dxf_namespace_integrity_status'] == 'NAMESPACES_INCOMPLETE_NO_EVIDENCE'
    assert got['unverified_namespace_count'] == 1


def test_f03_proxy_reference_is_indeterminate_not_resolved():
    proxy = SimpleNamespace(dxf=SimpleNamespace(handle='AA'),
                            dxftype=lambda: 'ACAD_PROXY_OBJECT')
    got = audit_named_dictionary_links(fake_dictionary_doc(target=proxy))
    assert got['converted_dxf_namespace_integrity_status'] == 'INDETERMINATE_DXF_DICTIONARY_TARGETS'
    assert got['dangling_or_invalid_count'] == 0
    assert got['unverified_target_count'] == 1
    assert got['unverified_target_references'][0]['reason'] == 'PROXY_TARGET_UNVERIFIED'
    assert got['automatic_patch_authorized'] is False


@pytest.mark.parametrize('class_declared,expected', [
    (None, 'TARGET_CLASS_NOT_DECLARED'),
    ('VENDOR_CUSTOM', 'CUSTOM_TARGET_UNVERIFIED'),
])
def test_f03_custom_class_targets_never_green(class_declared, expected):
    custom = SimpleNamespace(dxf=SimpleNamespace(handle='AA'),
                             dxftype=lambda: 'VENDOR_CUSTOM')
    got = audit_named_dictionary_links(
        fake_dictionary_doc(target=custom, declared_class=class_declared))
    assert got['unverified_target_references'][0]['reason'] == expected
    assert got['dangling_or_invalid_count'] == 0
    assert got['unverified_target_count'] == 1
    assert got['converted_dxf_namespace_integrity_status'] == 'INDETERMINATE_DXF_DICTIONARY_TARGETS'


def test_f04_string_root_is_resolved_from_entitydb():
    got = audit_named_dictionary_links(fake_dictionary_doc(root_value='2'))
    assert got['dangling_or_invalid_count'] == 0
    assert got['namespaces']['Autodesk_MAP'] == 'DICTIONARY_PRESENT'


def test_f04_missing_string_root_is_reported():
    got = audit_named_dictionary_links(fake_dictionary_doc(root_value='BADD'))
    assert got['dangling_or_invalid_references'][0]['reason'] == 'ROOT_TARGET_UNRESOLVED'


@pytest.mark.parametrize('branch,collision', [('dwg2dxf', 'out'), ('ODAFileConverter', 'out/oda')])
def test_f07_converter_never_runs_or_deletes_preexisting_same_stem(
    tmp_path, monkeypatch, branch, collision
):
    src = tmp_path / 'drawing.dwg'
    src.write_bytes(b'AC1018_mock_source_data')
    out = tmp_path / 'out'
    parent = tmp_path / collision
    parent.mkdir(parents=True)
    existing = parent / ('DRAWING.DXF' if branch == 'ODAFileConverter' else 'drawing.dxf')
    existing.write_bytes(b'private-user-data')
    monkeypatch.setattr(OfflineDWGConverter, '_run',
                        lambda *args, **kwargs: pytest.fail('converter must not run'))
    with pytest.raises(DWGConversionError, match='موجود'):
        OfflineDWGConverter(branch).convert(src, out)
    assert existing.read_bytes() == b'private-user-data'


@pytest.mark.parametrize('dictionary_case, expected_veto', [
    ('valid_target', False),
    ('dangling_target', True),
    ('missing_namespaces', True),
    ('proxy_target', True),
])
def test_f08_dictionary_integrity_veto_changes_with_verified_roster(
    tmp_path, monkeypatch, dictionary_case, expected_veto
):
    from core.drawings import dwg_converter
    src = tmp_path / 'drawing.dwg'
    src.write_bytes(b'AC1018_mock_source_data')
    def fake_run(self, command, **kwargs):
        d = ezdxf.new('R2018')
        d.modelspace().add_line((0, 0), (1, 2))
        if dictionary_case != 'missing_namespaces':
            m = d.rootdict.add_new_dict('Autodesk_MAP')
            d.rootdict.add_new_dict('AEC_VARS')
            if dictionary_case == 'valid_target':
                m['TARGET'] = d.objects.add_xrecord()
            elif dictionary_case == 'dangling_target':
                m['TARGET'] = 'BADF00D'
            else:
                # These registered DXF proxies must not pass as proven objects.
                m['TARGET'] = d.objects.new_entity('ACAD_PROXY_OBJECT',
                                                     dxfattribs={})
        d.saveas(command[2])
        return SimpleNamespace(returncode=0, stdout='SUCCESS', stderr='')
    monkeypatch.setattr(OfflineDWGConverter, '_run', fake_run)
    monkeypatch.setattr(
        dwg_converter, '_independent_source_coverage',
        lambda *args: {'status': 'MATCHED_INDEPENDENT_MODELSPACE_ROSTER',
                       'quantity_approved': False})
    receipt = OfflineDWGConverter('dwg2dxf').convert(src, tmp_path / 'out')
    assert receipt.financial_veto is True  # Final financial authority stays blocked.
    assert receipt.source_coverage['converter_integrity_veto'] is expected_veto
    assert receipt.source_coverage['financial_quantity_approved'] is False


def test_f09_private_report_rejects_project_and_git_directories(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    with pytest.raises(ValueError, match='outside repository'):
        private_output_destination(project / 'receipt.json', project_root=project)
    second = tmp_path / 'other'
    (second / '.git').mkdir(parents=True)
    with pytest.raises(ValueError, match='git repository'):
        private_output_destination(second / 'receipt.json', project_root=project)


def test_f09_private_report_is_exclusive_and_restricted(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    dest = tmp_path / 'private_data' / 'receipt.json'
    if os.name == 'nt':
        with pytest.raises(ValueError, match='ACL_NOT_VERIFIED'):
            write_private_report(dest, {'synthetic': True}, project_root=project)
        assert not dest.exists()
        return
    write_private_report(dest, {'synthetic': True}, project_root=project)
    assert dest.exists()
    assert (dest.stat().st_mode & 0o777) == 0o600
    assert (dest.parent.stat().st_mode & 0o777) == 0o700
    with pytest.raises(ValueError, match='overwrite'):
        write_private_report(dest, {'overwritten': True}, project_root=project)


def test_f09_relative_path_is_rejected(tmp_path):
    with pytest.raises(ValueError, match='absolute'):
        private_output_destination('private.json', project_root=tmp_path)


def test_f05_declared_size_is_validated_for_ac1018_framing():
    valid = [(0x101, 100, 2, 514, [10, 20, 30, 40, 50, 60])]
    assert summarize_raw_records(valid, ['101'])[0]['raw_record_stream_bytes'] == 6
    invalid = [(0x101, 100, 999, 514, [10, 20])]
    with pytest.raises(ValueError, match='declared size'):
        summarize_raw_records(invalid, ['101'])


@pytest.mark.parametrize('map_rows', [
    [(1, 10), (1, 20), (2, 30)],
    [(1, 10), (2, 20), (2, 30)],
    [(2, 30)],
])
def test_f06_duplicate_or_missing_native_object_index_handles_rejected(map_rows):
    with pytest.raises(ValueError):
        validate_object_map_entries(map_rows, [1, 2])


def test_f06_object_map_exposes_expected_offsets():
    assert validate_object_map_entries([(1, 10), (2, 30)], [1, 2]) == {1: 10, 2: 30}


def test_f10_status_does_not_claim_proprietary_recovery():
    r = opaque_recovery_decision(
        [{'handle': '101'}],
        {'policy': 'p8p2_dxf_named_dictionary_links_v1',
         'financial_quantity_approved': False,
         'converted_dxf_namespace_integrity_status': 'BROKEN_DXF_DICTIONARY_LINKS',
         'dangling_or_invalid_count': 1, 'dangling_or_invalid_references': []},
        expected_source_sha256='a' * 64,
        converted_dxf_sha256='b' * 64)
    assert 'RECOVERABLE' not in r['status']
    assert r['automatic_patch_authorized'] is False


@pytest.mark.parametrize('declared, extra', [
    (32767, 4), (32768, 6), (40000, 6),
])
def test_n03_ac1018_modular_short_boundary_accepts_correct_framing(declared, extra):
    payload = bytes(declared + extra)
    receipt = summarize_raw_records([(0x101, 7, declared, 514, payload)], ['101'])
    assert receipt[0]['raw_record_stream_bytes'] == declared + extra


@pytest.mark.parametrize('declared, wrong_extra', [
    (32767, 6), (32768, 4), (40000, 4),
])
def test_n03_ac1018_modular_short_boundary_rejects_wrong_framing(declared, wrong_extra):
    with pytest.raises(ValueError, match='declared size'):
        summarize_raw_records([(0x101, 7, declared, 514, bytes(declared + wrong_extra))], ['101'])


def test_n01_real_proxy_state_never_becomes_dangling_receipt():
    proxy = SimpleNamespace(dxf=SimpleNamespace(handle='AA'),
                            dxftype=lambda: 'ACAD_PROXY_OBJECT')
    dictionary = audit_named_dictionary_links(fake_dictionary_doc(target=proxy))
    assert dictionary['dangling_or_invalid_count'] == 0
    assert dictionary['unverified_target_count'] == 1
    decision = opaque_recovery_decision(
        [{'handle': '101'}], dictionary,
        expected_source_sha256='a' * 64,
        converted_dxf_sha256='b' * 64,
    )
    assert decision['converted_dxf_dangling_ref_count'] == 0
    assert decision['converted_dxf_unverified_target_count'] == 1
    assert decision['status'] == 'SOURCE_OPAQUE_RECORD_STREAMS_READ_DXF_TARGETS_INDETERMINATE'
    assert decision['automatic_patch_authorized'] is False


def test_n05_private_config_replaces_sensitive_command_line_options(tmp_path):
    if os.name == 'nt':
        pytest.skip('Windows private ACL verification deliberately remains NO-GO')
    project = tmp_path / 'git_work'
    project.mkdir()
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    config_file = private / 'handles.json'
    import json
    config_file.write_text(json.dumps({
        'handles': ['101', '102'],
        'expected_original_sha256': 'a' * 64,
    }), encoding='utf-8')
    config_file.chmod(0o600)
    assert read_private_config(config_file, project_root=project) == (['101', '102'], 'a' * 64)
    config_file.chmod(0o644)
    with pytest.raises(ValueError, match='0600'):
        read_private_config(config_file, project_root=project)


def test_n05_cli_cannot_expose_private_handles_or_sha_in_argv():
    import importlib
    from tools import audit_phase8_p2_opaque_source_bytes as cli
    import inspect
    source = inspect.getsource(cli.main)
    assert "add_argument('--handles'," not in source
    assert "add_argument('--expected-original-sha256'," not in source
    assert "add_argument('--private-config', required=True" in source


def test_n06_world_readable_private_parent_is_rejected(tmp_path):
    if os.name == 'nt':
        pytest.skip('Windows private ACL verification deliberately remains NO-GO')
    project = tmp_path / 'repo'
    project.mkdir()
    parent = tmp_path / 'insecure_parent'
    parent.mkdir(mode=0o755)
    parent.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        write_private_report(parent / 'result.json', {'synthetic': True},
                             project_root=project)
    assert not (parent / 'result.json').exists()


def test_f11_missing_frozen_named_root_cannot_fallback_to_1a(tmp_path):
    original = tmp_path / 'synthetic.dwg'
    original.write_bytes(b'AC1018_synthetic')
    dxf = tmp_path / 'synthetic.dxf'
    ezdxf.new('R2018').saveas(dxf)
    ledger = {
        'source_sha256': sha256(original.read_bytes()).hexdigest(),
        'policy': 'phase8_p2_opaque_decoder_evidence_v1',
        'verdict': 'PARTIAL_NO_GO', 'quantity_approved': False,
        'objects': [{'handle': '1'}], 'opaque_object_count': 1,
    }
    with pytest.raises(ValueError, match='explicitly name'):
        audit_opaque_conversion_loss(original, dxf, ledger)
