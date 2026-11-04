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
    def fake_run(cmd, **kwargs):
        assert cmd == [str(helper), str(src)]
        assert kwargs['env']['LIBREDWG_TRACE'] == '9'
        assert kwargs['stdin'] == subprocess.DEVNULL
        kwargs['stderr'].write(b'synthetic trace not real C API\n')
        return SimpleNamespace(returncode=0,
             stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
                    b'STRUCTURALPRO_C_API_MASK=68\n'
                    b'STRUCTURALPRO_C_API_OBJECTS=7\n')
    monkeypatch.setattr(m.subprocess, 'run', fake_run)
    r = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert r['exact_libredwg_return_mask'] == 68
    assert r['financial_quantity_approved'] is False
    assert r['object_level_error_cause_verified'] is False
    assert r['value_out_of_bounds_object_cause_verified'] is False
    assert (output / 'libredwg_native_receipt.private.json').stat().st_mode & 0o077 == 0
    assert (output / 'libredwg_native_stderr.private.log').stat().st_mode & 0o077 == 0


def test_synthetic_repeated_object_masks_not_inferred_from_stderr(tmp_path, monkeypatch):
    if os.name != 'posix':
        pytest.skip('Windows private ACL is intentionally not verified')
    src, cfg, helper, lib, output = sample(tmp_path)
    monkeypatch.setattr(m, '_verify_linked_library', lambda *_: None)
    monkeypatch.setattr(m.subprocess, 'run', lambda *args, **kwargs:
         SimpleNamespace(returncode=0,
             stdout=b'STRUCTURALPRO_LIBREDWG_COMMIT=a835758\n'
                    b'STRUCTURALPRO_C_API_MASK=4\n'
                    b'STRUCTURALPRO_C_API_OBJECTS=7\n'))
    result = m.diagnose_private_source(src, cfg, helper, lib, output)
    assert result['exact_libredwg_return_mask'] == 4
    assert result['map_aec_causation_verified'] is False
    assert result['verdict'] == 'PARTIAL_NO_GO'