"""Synthetic tests; zero actual native C-API calls, zero private real DWG in CI."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from core.drawings import libredwg_native_trace_runner as m


def sample(tmp_path):
    private = tmp_path / 'private'
    private.mkdir(mode=0o700)
    if os.name == 'posix':
        private.chmod(0o700)
    src = tmp_path / 'test.dwg'
    src.write_bytes(b'AC1018-synthetic-original-dwg-not-real')
    helper = tmp_path / 'capi'
    helper.write_bytes(b'FAKE_BINARY_FOR_SYNTHETIC_TEST')
    helper.chmod(0o700)
    lib = tmp_path / 'libredwg.so'
    lib.write_bytes(b'FAKE_LIBRARY_FOR_SYNTHETIC_TEST')
    cfg = private / 'config.json'
    cfg.write_text(json.dumps({
        'source_sha256': m._sha_file(src),
        'helper_sha256': m._sha_file(helper),
        'library_sha256': m._sha_file(lib),
        'libredwg_commit': 'a835758',
    }), encoding='utf-8')
    cfg.chmod(0o600)
    return src, cfg, helper, lib, private


def test_exact_two_flag_mask_requires_explicit_c_api_return():
    got = m.parse_helper_stdout('STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
       'STRUCTURALPRO_C_API_MASK=68\nSTRUCTURALPRO_C_API_OBJECTS=101504\n', 'a835758')
    assert got['c_api_return_mask'] == 68
    assert got['native_object_count'] == 101504


@pytest.mark.parametrize('text', [
    'SUCCESS\n',
    'STRUCTURALPRO_C_API_MASK=0\n',
    'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
     'STRUCTURALPRO_C_API_MASK=68\nSTRUCTURALPRO_C_API_MASK=0\n'
     'STRUCTURALPRO_C_API_OBJECTS=7\n',
    'STRUCTURALPRO_LIBREDWG_COMMIT=UNPINNED\n'
     'STRUCTURALPRO_C_API_MASK=68\nSTRUCTURALPRO_C_API_OBJECTS=7\n',
    'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
     'STRUCTURALPRO_C_API_MASK=-1\nSTRUCTURALPRO_C_API_OBJECTS=7\n',
    'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
     'STRUCTURALPRO_C_API_MASK=2147483648\nSTRUCTURALPRO_C_API_OBJECTS=7\n',
    'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
     'STRUCTURALPRO_C_API_MASK=68\nSTRUCTURALPRO_C_API_OBJECTS=10000001\n',
])
def test_malformed_or_fake_c_api_stdout_is_rejected(text):
    with pytest.raises(ValueError):
        m.parse_helper_stdout(text, 'a835758')


def test_wrong_compiled_commit_rejected():
    with pytest.raises(ValueError, match='unpinned'):
        m.parse_helper_stdout('STRUCTURALPRO_LIBREDWG_COMMIT=baaaaaa\n'
          'STRUCTURALPRO_C_API_MASK=68\nSTRUCTURALPRO_C_API_OBJECTS=7\n', 'a835758')


def test_private_config_requires_exact_sha_fields(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL verification intentionally unavailable')
    src, cfg, helper, lib, private = sample(tmp_path)
    assert m._read_config(cfg)['source_sha256'] == m._sha_file(src)
    data = json.loads(cfg.read_text())
    data['source_sha256'] = 'INVALID'
    cfg.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='digests'):
        m._read_config(cfg)


def test_unrestricted_config_is_blocked(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    _, cfg, *_ = sample(tmp_path)
    cfg.chmod(0o644)
    with pytest.raises(ValueError, match='0600'):
        m._read_config(cfg)


def test_unrestricted_private_directory_blocked(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    _, cfg, _, _, directory = sample(tmp_path)
    directory.chmod(0o755)
    with pytest.raises(ValueError, match='0700'):
        m._read_config(cfg)


def test_private_original_source_identity_is_pinned(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    src.write_bytes(b'AC1018-changed-synthetic-original-dwg')
    with pytest.raises(ValueError, match='SHA'):
        m.diagnose_private_source(src, cfg, helper, lib, output)


def test_missing_native_helper_is_not_fake_success(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    helper.unlink()
    with pytest.raises(ValueError, match='NATIVE_C_API_HELPER_UNAVAILABLE'):
        m.diagnose_private_source(src, cfg, helper, lib, output)
    assert not (output / 'libredwg_native_receipt.private.json').exists()


def test_wrong_library_sha_does_not_execute(tmp_path):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    lib.write_bytes(b'TAMPERED')
    with pytest.raises(ValueError, match='library SHA'):
        m.diagnose_private_source(src, cfg, helper, lib, output)


def test_mocked_success_cannot_approve_financial_quantities(tmp_path, monkeypatch):
    """This is a fake subprocess for unit testing, NOT a native decoder run."""
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    def fake_run(mock_helper, mock_source, env, stderr_file, timeout):
        assert mock_helper == helper and mock_source == src
        assert env['LIBREDWG_TRACE'] == '9'
        stderr_file.write(b'ERROR: Invalid SORTENTSTABLE.num_ents 50001\n')
        return SimpleNamespace(returncode=0,
             stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
                    b'STRUCTURALPRO_C_API_MASK=68\n'
                    b'STRUCTURALPRO_C_API_OBJECTS=7\n')
    monkeypatch.setattr(m, '_execute_native_filtered', fake_run)
    r = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert r['exact_libredwg_return_mask'] == 68
    assert r['financial_quantity_approved'] is False
    assert r['object_level_error_cause_verified'] is False
    assert r['value_out_of_bounds_object_cause_verified'] is False
    assert (output / 'libredwg_native_receipt.private.json').stat().st_mode & 0o077 == 0
    assert (output / 'libredwg_native_errors.private.log').stat().st_mode & 0o077 == 0
    assert r['bit64_has_confirmed_sortentstable_guard_trigger'] is True


def test_synthetic_repeated_object_masks_not_inferred_from_stderr(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    monkeypatch.setattr(m, '_execute_native_filtered', lambda *args, **kwargs:
         SimpleNamespace(returncode=0,
             stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
                    b'STRUCTURALPRO_C_API_MASK=4\n'
                    b'STRUCTURALPRO_C_API_OBJECTS=7\n'))
    result = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert result['exact_libredwg_return_mask'] == 4
    assert result['map_aec_causation_verified'] is False
    assert result['verdict'] == 'PARTIAL_NO_GO'



def test_ab_diagnostic_label_requires_exact_variant_and_upstream_commit():
    """The experimental suffix is a build identity, never a Git commit SHA."""
    exp = ('STRUCTURALPRO_LIBREDWG_COMMIT=a835758-exp100k\n'
           'STRUCTURALPRO_C_API_MASK=4\n'
           'STRUCTURALPRO_C_API_OBJECTS=101504\n')
    got = m.parse_helper_stdout(exp, 'a835758', 'sortentstable_100k')
    assert got['observed_upstream_commit'] == 'a835758'
    assert got['observed_build_variant'] == 'sortentstable_100k'
    assert got['c_api_return_mask'] == 4
    for upstream, variant in [
        ('a835758', 'upstream'), ('badbeef', 'sortentstable_100k'),
        ('a835758', 'sortentstable_200k'),
    ]:
        with pytest.raises(ValueError):
            m.parse_helper_stdout(exp, upstream, variant)
    for invalid_label in ('a835758-exp100000', 'a835758-exp100k-extra',
                          'a835758-exp50k', 'a835758-release'):
        with pytest.raises(ValueError):
            m.parse_helper_stdout(exp.replace('a835758-exp100k', invalid_label),
                                  'a835758', 'sortentstable_100k')


def test_experimental_guard_is_not_mislabeled_as_original_50k(tmp_path, monkeypatch):
    """Synthetic A/B observation cannot authorize quantity or silently change threshold."""
    if os.name != 'posix':
        pytest.skip('POSIX private ACL required')
    src, cfg, helper, lib, output = sample(tmp_path)
    contents = json.loads(cfg.read_text(encoding='utf-8'))
    contents['build_variant'] = 'sortentstable_100k'
    cfg.write_text(json.dumps(contents), encoding='utf-8')
    cfg.chmod(0o600)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    def fake_run(mock_helper, mock_source, env, stderr_file, timeout):
        stderr_file.write(b'ERROR: Invalid SORTENTSTABLE.num_ents 50001\n')
        return SimpleNamespace(returncode=0,
            stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758-exp100k\n'
                   b'STRUCTURALPRO_C_API_MASK=4\n'
                   b'STRUCTURALPRO_C_API_OBJECTS=7\n')
    monkeypatch.setattr(m, '_execute_native_filtered', fake_run)
    result = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert result['libredwg_upstream_commit'] == 'a835758'
    assert result['libredwg_build_variant'] == 'sortentstable_100k'
    assert result['sortentstable_guard_threshold_in_pinned_source'] == 100000
    assert result['bit64_has_confirmed_sortentstable_guard_trigger'] is False
    assert result['financial_quantity_approved'] is False
    assert result['verdict'] == 'PARTIAL_NO_GO'


def test_diagnostic_experimental_config_rejects_upstream_binary(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('POSIX private ACL required')
    src, cfg, helper, lib, output = sample(tmp_path)
    contents = json.loads(cfg.read_text(encoding='utf-8'))
    contents['build_variant'] = 'sortentstable_100k'
    cfg.write_text(json.dumps(contents), encoding='utf-8')
    cfg.chmod(0o600)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    monkeypatch.setattr(m, '_execute_native_filtered', lambda *args, **kwargs:
        SimpleNamespace(returncode=0,
            stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
                   b'STRUCTURALPRO_C_API_MASK=0\n'
                   b'STRUCTURALPRO_C_API_OBJECTS=7\n'))
    with pytest.raises(ValueError, match='unpinned'):
        m.diagnose_private_source(src, cfg, helper, lib, output)
    assert not (output / 'libredwg_native_receipt.private.json').exists()
    assert not (output / 'libredwg_native_errors.private.log').exists()


def test_b64_stage_variant_exact_label_rejects_other_builds():
    text = (
        'STRUCTURALPRO_LIBREDWG_COMMIT=a835758-exp100k-b64stage\n'
        'STRUCTURALPRO_C_API_MASK=68\n'
        'STRUCTURALPRO_C_API_OBJECTS=101504\n'
    )
    got = m.parse_helper_stdout(text, 'a835758', 'sortentstable_100k_b64stage')
    assert got['observed_build_variant'] == 'sortentstable_100k_b64stage'
    assert got['c_api_return_mask'] == 68
    for variant in ('upstream', 'sortentstable_100k'):
        with pytest.raises(ValueError, match='unpinned'):
            m.parse_helper_stdout(text, 'a835758', variant)
    with pytest.raises(ValueError, match='unpinned'):
        m.parse_helper_stdout(text.replace('a835758', 'badbeef'),
                              'a835758', 'sortentstable_100k_b64stage')


def test_b64_stage_private_probe_receipt_is_bounded_and_no_go(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('POSIX private ACL required')
    src, cfg, helper, lib, output = sample(tmp_path)
    contents = json.loads(cfg.read_text(encoding='utf-8'))
    contents['build_variant'] = 'sortentstable_100k_b64stage'
    cfg.write_text(json.dumps(contents), encoding='utf-8')
    cfg.chmod(0o600)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    def fake_run(mock_helper, mock_source, env, stderr_file, timeout):
        stderr_file.write(
            b'190:SP_P8P2_B64_STAGE=read_2004_section_handles\n'
            b'191:SP_P8P2_B64_OBJECT_RETURN\n'
            b'192:SP_P8P2_B64_STAGE=read_2004_section_handles\n'
        )
        return SimpleNamespace(
            returncode=0,
            stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758-exp100k-b64stage\n'
                   b'STRUCTURALPRO_C_API_MASK=68\n'
                   b'STRUCTURALPRO_C_API_OBJECTS=7\n',
        )
    monkeypatch.setattr(m, '_execute_native_filtered', fake_run)
    report = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert report['bit64_stage_instrumentation_executed'] is True
    assert report['bit64_diagnostic_stage_names'] == ['read_2004_section_handles']
    assert report['bit64_object_decode_return_markers_bounded'] == 1
    assert report['financial_quantity_approved'] is False
    assert report['all_other_possible_bit64_sources_excluded'] is False
    assert report['verdict'] == 'PARTIAL_NO_GO'


def test_real_stream_filter_retains_error_but_not_unbounded_trace(tmp_path):
    """Real Python subprocess + grep, synthetic lines: no CAD/native library."""
    import sys
    if os.name != 'posix':
        pytest.skip('POSIX native trace filter only')
    mock_helper = tmp_path / 'synthetic_helper.py'
    mock_helper.write_text(
        'import sys\n'
        'for i in range(10000): print("trace irrelevant", file=sys.stderr)\n'
        'print("ERROR: Invalid SORTENTSTABLE.num_ents 50001", file=sys.stderr)\n'
        'print("STRUCTURALPRO_LIBREDWG_COMMIT=a835758")\n'
        'print("STRUCTURALPRO_C_API_MASK=64")\n'
        'print("STRUCTURALPRO_C_API_OBJECTS=3")\n', encoding='utf-8')
    target = tmp_path / 'filtered.private.txt'
    with target.open('wb') as fp:
        out = m._execute_native_filtered(Path(sys.executable), mock_helper,
                                         dict(os.environ), fp, timeout=20)
    assert out.returncode == 0
    assert b'STRUCTURALPRO_C_API_MASK=64' in out.stdout
    saved = target.read_text()
    assert 'Invalid SORTENTSTABLE.num_ents 50001' in saved
    assert 'trace irrelevant' not in saved
    assert len(saved) < 1000