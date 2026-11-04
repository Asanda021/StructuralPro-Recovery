"""Source-bound, fail-closed *private* LibreDWG native-C-API trace executor.

This runner does not repair, export, approve or alter DWG/DXF. It runs a
separately compiled C helper, which calls the actual dwg_read_file and prints
its RETURN VALUE. A matching exit code or text log is NOT that return value.

No original drawings, stderr, handles, source hashes, or file paths belong in
public CI/GitHub. The caller must give a private (0700) evidence directory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from core.drawings.libredwg_error_mask import decode_libredwg_error_mask

_MAGIC = re.compile(r"^STRUCTURALPRO_C_API_MASK=([0-9]{1,10})$")
_OBJECTS = re.compile(r"^STRUCTURALPRO_C_API_OBJECTS=([0-9]{1,15})$")
_COMMIT = re.compile(r"^STRUCTURALPRO_LIBREDWG_COMMIT=([0-9a-f]{7,40})(-exp100k)?$")
# Only the explicitly pinned diagnostic change may be selected. The upstream
# commit remains a pure hex identity, separate from the build variant.
_BUILD_VARIANTS = {
    'upstream': ('', 50000),
    'sortentstable_100k': ('-exp100k', 100000),
}
_MAX_LOG_BYTES = 128 * 1024 * 1024


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def _is_hex_hash(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r'[0-9a-fA-F]{64}', value) is not None


def _private_folder(directory: Path) -> None:
    if os.name != 'posix':
        raise ValueError('WINDOWS_PRIVATE_ACL_UNVERIFIED')
    if not directory.is_absolute() or not directory.is_dir() or directory.is_symlink():
        raise ValueError('Existing absolute private evidence directory required')
    if directory.stat().st_mode & 0o077:
        raise ValueError('Private evidence directory must be 0700')
    for p in (directory, *directory.parents):
        if p.is_symlink() or (p / '.git').exists() or p.name.lower() in {'artifacts', 'public', 'dist'}:
            raise ValueError('Private evidence directory cannot be a public/git path')


def _read_config(path: Path) -> dict:
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError('Absolute existing private configuration JSON required')
    _private_folder(path.parent)
    if path.stat().st_mode & 0o077 or path.stat().st_size > 16384:
        raise ValueError('Private config must have mode 0600 and be <=16KiB')
    data = json.loads(path.read_text(encoding='utf-8'))
    required = {'source_sha256', 'helper_sha256', 'library_sha256', 'libredwg_commit'}
    allowed = required | {'build_variant'}
    if not isinstance(data, dict) or not required.issubset(data) or not set(data).issubset(allowed):
        raise ValueError('Private config must specify pinned provenance identities and optional build variant')
    if data.get('build_variant', 'upstream') not in _BUILD_VARIANTS:
        raise ValueError('Unrecognized pinned LibreDWG build variant')
    if not all(_is_hex_hash(data[k]) for k in required - {'libredwg_commit'}):
        raise ValueError('Missing valid 64-digit provenance digests')
    if not re.fullmatch(r'[0-9a-f]{7,40}', str(data['libredwg_commit'])):
        raise ValueError('Pinned LibreDWG commit required')
    return data


def parse_helper_stdout(output: str, expected_commit: str,
                        expected_build_variant: str = 'upstream') -> dict:
    """Exactly one unambiguous observed C API mask and matching compiled label."""
    if not isinstance(output, str) or len(output) > 8192:
        raise ValueError('Unexpected helper output length')
    if expected_build_variant not in _BUILD_VARIANTS:
        raise ValueError('Unrecognized pinned LibreDWG build variant')
    lines = output.strip().splitlines()
    if len(lines) != 3:
        raise ValueError('Unexpected C API summary line count')
    matches = [(_COMMIT.fullmatch(x), _MAGIC.fullmatch(x), _OBJECTS.fullmatch(x)) for x in lines]
    commit = [(m[0].group(1), m[0].group(2) or '') for m in matches if m[0]]
    masks = [m[1].group(1) for m in matches if m[1]]
    objects = [m[2].group(1) for m in matches if m[2]]
    expected_suffix, _ = _BUILD_VARIANTS[expected_build_variant]
    if (len(commit) != 1 or len(masks) != 1 or len(objects) != 1
            or commit[0] != (expected_commit, expected_suffix)):
        raise ValueError('Missing, conflicting or unpinned C API summary')
    parsed = int(masks[0])
    if parsed > 2**31 - 1 or int(objects[0]) > 10_000_000:
        raise ValueError('C API mask or object count outside safe range')
    return {'c_api_return_mask': parsed, 'native_object_count': int(objects[0]),
            'observed_upstream_commit': commit[0][0],
            'observed_build_variant': expected_build_variant,
            'observed_compiled_commit_label': ''.join(commit[0])}


def _verify_linked_library(helper: Path, library: Path) -> None:
    """Require actual dynamic loader binding, not only a claimed .so pathname."""
    if library.is_symlink() or not library.is_file() or not helper.is_file():
        raise ValueError('Pinned helper and real library file are required')
    ld_env = dict(os.environ)
    ld_env['LD_LIBRARY_PATH'] = str(library.parent)
    ld = subprocess.run(['/usr/bin/ldd', str(helper)], capture_output=True,
                        text=True, env=ld_env, timeout=10, check=False)
    if ld.returncode != 0:
        raise ValueError('Native helper shared-library linkage not verified')
    paths = []
    for line in ld.stdout.splitlines():
        if 'libredwg.so' not in line:
            continue
        m = re.search(r'libredwg\.so[^\s]*\s*=>\s*(/[^\s]+)', line)
        if m:
            paths.append(Path(m.group(1)).resolve())
    if len(paths) != 1 or paths[0] != library.resolve():
        raise ValueError('Actual libredwg dynamic loader location is unverified')


def _execute_native_filtered(helper: Path, source: Path, env: dict,
                             stderr_file, timeout: int):
    """Stream massive stderr through GNU grep; never buffer raw multi-GB trace.

    Only selected error/warning lines and their original trace-line numbers
    are stored privately. This cannot replace a full instrumented source trace
    and never provides drawing approval.
    """
    if not Path('/usr/bin/grep').is_file():
        raise ValueError('Pinned native trace requires local grep executable')
    needle = (r'VALUEOUTOFBOUNDS|out.of.bounds|out.of.range|overflow|overrun|'
              r'CRITICAL|ERROR:|WARN:|WARNING:|invalid .*value|exceeds? .*limit|too large|'
              r'Unhandled Class')
    native = subprocess.Popen([str(helper), str(source)], stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    filter_proc = None
    try:
        filter_proc = subprocess.Popen(['/usr/bin/grep', '-anEi', needle],
                                       stdin=native.stderr, stdout=stderr_file,
                                       stderr=subprocess.DEVNULL)
        native.stderr.close()
        stdout, _ = native.communicate(timeout=timeout)
        filter_status = filter_proc.wait(timeout=timeout)
        if filter_status not in (0, 1):
            raise ValueError('Native trace filter failed')
        return subprocess.CompletedProcess([str(helper), str(source)],
                                           native.returncode, stdout=stdout)
    except BaseException:
        native.kill()
        if filter_proc is not None:
            filter_proc.kill()
        native.wait()
        if filter_proc is not None:
            filter_proc.wait()
        raise


def diagnose_private_source(source: str | Path, private_config: str | Path,
                            helper: str | Path, library: str | Path,
                            private_output: str | Path, *, timeout=120) -> dict:
    """Run once; preserve exact log privately and never claim causal source proof."""
    source = Path(source)
    config_path = Path(private_config)
    helper = Path(helper)
    library = Path(library)
    output = Path(private_output)
    _private_folder(output)
    config = _read_config(config_path)
    if source.is_symlink() or not source.is_file() or source.suffix.lower() != '.dwg':
        raise ValueError('Original regular DWG required')
    if source.stat().st_size > 50 * 1024 * 1024 or source.read_bytes()[:6] != b'AC1018':
        raise ValueError('Expected bounded original AC1018 DWG')
    if _sha_file(source).lower() != config['source_sha256'].lower():
        raise ValueError('Original DWG SHA mismatches frozen private evidence')
    if not helper.is_absolute() or not helper.is_file() or not os.access(helper, os.X_OK):
        raise ValueError('PINNED_NATIVE_C_API_HELPER_UNAVAILABLE')
    if not library.is_absolute() or not library.is_file():
        raise ValueError('PINNED_LIBREDWG_LIBRARY_UNAVAILABLE')
    if _sha_file(helper).lower() != config['helper_sha256'].lower():
        raise ValueError('Native helper binary SHA unverified')
    if _sha_file(library).lower() != config['library_sha256'].lower():
        raise ValueError('LibreDWG library SHA unverified')
    _verify_linked_library(helper, library)
    if any((output / name).exists() for name in ('libredwg_native_errors.private.log',
                                                  'libredwg_native_receipt.private.json')):
        raise ValueError('Existing private evidence must not be overwritten')
    before = source.stat()
    env = dict(os.environ)
    env['LIBREDWG_TRACE'] = '9'
    env['LD_LIBRARY_PATH'] = str(library.parent)
    stderr_path = output / 'libredwg_native_errors.private.log'
    fd = os.open(stderr_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stderr_file:
            result = _execute_native_filtered(helper, source, env, stderr_file, timeout)
        if result.returncode != 0:
            raise ValueError('Native C API helper execution failed')
        if stderr_path.stat().st_size > _MAX_LOG_BYTES:
            raise ValueError('Private filtered native trace exceeds safety limit')
        build_variant = config.get('build_variant', 'upstream')
        parsed = parse_helper_stdout(result.stdout.decode('ascii', 'strict'),
                                     config['libredwg_commit'], build_variant)
        if _sha_file(source).lower() != config['source_sha256'].lower() or (
            before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns
        ) != (lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns))(source.stat()):
            raise ValueError('DWG source changed during native C API diagnostic')
        filtered_text = stderr_path.read_text(encoding='utf-8', errors='replace')
        # This emitted diagnostic is traced to VALUEOUTOFBOUNDS(num_ents,50000)
        # in pinned GNU LibreDWG src/dwg2.spec, expanded in src/spec.h.
        guard = [int(v) for v in re.findall(
            r'ERROR: Invalid SORTENTSTABLE\.num_ents ([0-9]{1,12})',
            filtered_text)]
        _, guard_threshold = _BUILD_VARIANTS[build_variant]
        guard_exceeded = bool(guard) and all(v > guard_threshold for v in guard)
        report = {
            'policy': 'structuralpro_p8p2_private_native_c_api_trace_v2',
            'native_c_api_actually_executed': True,
            'exact_libredwg_return_mask': parsed['c_api_return_mask'],
            'native_object_count': parsed['native_object_count'],
            'c_api_mask_diagnostic': decode_libredwg_error_mask(parsed['c_api_return_mask']),
            'linked_library_and_helper_sha_verified': True,
            'source_sha_verified_before_after': True,
            'object_level_error_cause_verified': False,
            'value_out_of_bounds_object_cause_verified': False,
            'map_aec_causation_verified': False,
            'stderr_log_is_private': True,
            'stderr_trace_is_filtered_not_full': True,
            'libredwg_upstream_commit': parsed['observed_upstream_commit'],
            'libredwg_build_variant': parsed['observed_build_variant'],
            'sortentstable_guard_threshold_in_pinned_source': guard_threshold,
            'observed_sortentstable_counts_above_guard': guard if guard_exceeded else [],
            'bit64_has_confirmed_sortentstable_guard_trigger': bool(
                (parsed['c_api_return_mask'] & 64) and guard_exceeded),
            'all_other_possible_bit64_sources_excluded': False,
            'financial_quantity_approved': False,
            'verdict': 'PARTIAL_NO_GO',
        }
        target = output / 'libredwg_native_receipt.private.json'
        desc = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(desc, 'w', encoding='utf-8') as fp:
            json.dump(report, fp, ensure_ascii=False, indent=2)
            fp.write('\n')
            fp.flush()
            os.fsync(fp.fileno())
        return report
    except BaseException:
        # On failure do not retain partial or unattributed private evidence.
        stderr_path.unlink(missing_ok=True)
        (output / 'libredwg_native_receipt.private.json').unlink(missing_ok=True)
        raise