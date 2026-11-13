"""Read-only DWG opaque-record audit; keep sensitive parameters off argv."""
import argparse
import json
import os
import stat
from pathlib import Path

from core.drawings.dwg_opaque_source_receipt import audit_original_opaque_records


def _no_symlink_ancestors(path):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Private receipt/config path cannot traverse symlinks')


def _private_directory_guard(directory):
    if os.name == 'nt':
        # Actual token owner + protected native DACL, not POSIX chmod fiction.
        from core.platform.windows_private_acl import verify_private_dacl
        try:
            verify_private_dacl(directory, directory=True)
        except ValueError as exc:
            raise ValueError('WINDOWS_PRIVATE_ACL_NOT_VERIFIED') from exc
        return
    if not directory.is_dir() or (directory.stat().st_mode & 0o077):
        raise ValueError('Private evidence directory must be accessible only to its owner (0700)')


def private_output_destination(path, *, project_root=None):
    """Reject public/repository paths or pre-existing artifacts before reading CAD."""
    requested = Path(path).expanduser()
    if not requested.is_absolute():
        raise ValueError('Private receipt needs an absolute output path')
    project = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    destination = requested.resolve(strict=False)
    if destination.suffix.lower() != '.json':
        raise ValueError('Private receipt must be a JSON file')
    if destination == project or project in destination.parents:
        raise ValueError('Private CAD evidence must stay outside repository')
    if destination.exists() or requested.is_symlink():
        raise ValueError('Never overwrite an existing private audit artifact')
    for ancestor in (destination.parent, *destination.parents):
        if (ancestor / '.git').exists() or ancestor.name == '.git':
            raise ValueError('Private CAD receipt cannot be written inside a git repository')
    if any(p.lower() in {'public', 'artifacts', 'dist', 'docs'}
           for p in destination.parts):
        raise ValueError('Public build, document or artifact directories are forbidden')
    _no_symlink_ancestors(requested)
    return destination


def read_private_config(path, *, project_root=None):
    """Read handles and source SHA from a 0600 private JSON; never from argv."""
    private = Path(path).expanduser()
    if not private.is_absolute() or private.suffix.lower() != '.json':
        raise ValueError('Absolute private JSON config required')
    if not private.is_file():
        raise ValueError('Private handles config not found')
    project = Path(project_root or Path(__file__).resolve().parents[1]).resolve()
    resolved = private.resolve(strict=True)
    if project == resolved or project in resolved.parents:
        raise ValueError('Private handles config must not be in repository')
    _no_symlink_ancestors(private)
    _private_directory_guard(resolved.parent)
    if os.name == 'nt':
        # Reading a private config is now allowed only after two native DACL
        # validations: parent directory and the config file itself.
        from core.platform.windows_private_acl import verify_private_dacl
        verify_private_dacl(resolved, directory=False)
    if os.name != 'nt' and resolved.stat().st_mode & 0o077:
        raise ValueError('Private handles config must be 0600')
    if resolved.stat().st_size > 16384:
        raise ValueError('Private handles config exceeds 16 KiB')
    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(resolved, flags)
    with os.fdopen(fd, 'r', encoding='utf-8') as stream:
        content = stream.read(16385)
    if len(content) > 16384:
        raise ValueError('Private handles config too large')
    config = json.loads(content)
    if not isinstance(config, dict) or set(config) != {'handles', 'expected_original_sha256'}:
        raise ValueError('Expected handles and source SHA in private JSON config')
    handles = config['handles']
    digest = config['expected_original_sha256']
    from core.drawings.dwg_opaque_source_receipt import _handles
    _handles(handles)
    if (not isinstance(digest, str) or len(digest) != 64
            or any(ch not in '0123456789abcdefABCDEF' for ch in digest)):
        raise ValueError('Invalid private source SHA')
    return handles, digest.lower()


def write_private_report(path, result, *, project_root=None):
    dest = private_output_destination(path, project_root=project_root)
    if not dest.parent.exists():
        # Do not create an unknown hierarchy of world-readable ancestors.
        if not dest.parent.parent.is_dir():
            raise ValueError('Private parent directory must already exist')
        dest.parent.mkdir(mode=0o700)
    _private_directory_guard(dest.parent)
    # Revalidate after creating the directory to exclude changed path identities.
    dest = private_output_destination(dest, project_root=project_root)
    if os.name == 'nt':
        # The native SDDL security descriptor is attached atomically by
        # CreateFileW/CREATE_NEW before the first private byte is written.
        from core.platform.windows_private_acl import create_private_output_fd
        fd = create_private_output_fd(dest)
    else:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        if hasattr(os, 'O_NOFOLLOW'):
            flags |= os.O_NOFOLLOW
        fd = os.open(dest, flags, 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == 'nt':
            from core.platform.windows_private_acl import verify_private_dacl
            verify_private_dacl(dest, directory=False)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_dwg')
    parser.add_argument('converted_dxf')
    parser.add_argument('output_json', help='Absolute private output JSON outside Git')
    parser.add_argument('--private-config', required=True,
                        help='0600 private JSON containing handles and source SHA (not on argv)')
    args = parser.parse_args()
    try:
        destination = private_output_destination(args.output_json)
        handles, original_sha = read_private_config(args.private_config)
        report = audit_original_opaque_records(
            args.original_dwg, args.converted_dxf, handles,
            expected_original_sha256=original_sha)
        write_private_report(destination, report)
    except Exception as exc:
        # On both POSIX and Windows, third-party readers may embed private
        # file names, raw object identities or byte snippets in exceptions.
        # Never print exception text from an original-DWG forensic audit.
        print('BLOCKED_NO_SAFE_SOURCE_RECEIPT:', type(exc).__name__)
        return 2
    print(report['status'], 'source record count', report['source_record_count'],
          'broken DXF link count', report['converted_dxf_dangling_ref_count'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
