"""Read-only DWG opaque-record audit; private output only, never DXF repair."""
import argparse
import json
import os
from pathlib import Path

from core.drawings.dwg_opaque_source_receipt import audit_original_opaque_records


def private_output_destination(path, *, project_root=None):
    """Reject public/repository paths and existing files before reading CAD.

    An explicit absolute destination outside any git tree is mandatory.
    New files are created exclusively with mode 0600 on POSIX.
    """
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
    if any(parent.is_symlink() for parent in (requested.parent, *requested.parents)):
        raise ValueError('Private receipt location may not traverse symlinks')
    return destination


def write_private_report(path, result, *, project_root=None):
    dest = private_output_destination(path, project_root=project_root)
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Revalidate after directory creation to avoid symlink path changes.
    dest = private_output_destination(dest, project_root=project_root)
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
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return dest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('original_dwg')
    p.add_argument('converted_dxf')
    p.add_argument('output_json', help='Absolute PRIVATE JSON path outside Git repository')
    p.add_argument('--handles', required=True, help='Comma-separated source handles; private')
    p.add_argument('--expected-original-sha256', required=True)
    a = p.parse_args()
    try:
        destination = private_output_destination(a.output_json)
        report = audit_original_opaque_records(
            a.original_dwg, a.converted_dxf, a.handles.split(','),
            expected_original_sha256=a.expected_original_sha256)
        write_private_report(destination, report)
    except Exception as exc:
        print('BLOCKED_NO_SAFE_SOURCE_RECEIPT:', type(exc).__name__, str(exc)[:120])
        return 2
    print(report['status'], 'original records', report['source_record_count'],
          'dangling DXF refs', report['converted_dxf_dangling_ref_count'])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
