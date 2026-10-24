"""Forensic, fail-closed recovery of a damaged Phase-4 SQLite *copy*.

This is an explicit QA / owner-controlled tool, not an automatic fallback at
application startup. It NEVER edits the input file, never uses the broken
projects.payload as recovery data and never hides a failed integrity_check.

Usage: python scripts/phase4_sqlite_rescue.py SOURCE.db NEW_OUTPUT.db
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from typing import Any


class RescueError(RuntimeError):
    """Unverifiable data: do not recover and do not overwrite source."""


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_evidence(con: sqlite3.Connection) -> tuple[list[tuple], list[tuple]]:
    """Validate the FULL revision chain; no deleted or invented revisions."""
    try:
        root_rows = con.execute(
            'SELECT id,name,version,updated_at FROM projects ORDER BY id'
        ).fetchall()
        revision_rows = con.execute(
            'SELECT project_id,version,created_at,CAST(payload AS BLOB) '
            'FROM revisions ORDER BY project_id,version'
        ).fetchall()
    except sqlite3.DatabaseError as exc:
        raise RescueError('Cannot read intact project metadata and revisions') from exc
    if not root_rows or not revision_rows:
        raise RescueError('No projects or revisions available to verify')
    if len({row[0] for row in root_rows}) != len(root_rows):
        raise RescueError('Duplicate project identities')
    groups: dict[str, list[tuple]] = {}
    for pid, version, created_at, raw in revision_rows:
        if not isinstance(pid, str) or not pid or not isinstance(raw, bytes):
            raise RescueError('Missing project identity or original revision bytes')
        if type(version) is not int or version < 1:
            raise RescueError(f'Invalid revision: {pid}, {version}')
        try:
            payload = json.loads(raw.decode('utf-8', errors='strict'))
        except (ValueError, UnicodeError) as exc:
            raise RescueError(f'Damaged revision: {pid}, {version}') from exc
        if not isinstance(payload, dict):
            raise RescueError(f'Invalid revision payload type: {pid}, {version}')
        if '_meta' in payload:
            raise RescueError(f'Uncommitted metadata found: {pid}, {version}')
        if payload.get('id') not in (None, pid) or payload.get('project_id') not in (None, pid):
            raise RescueError(f'Revision belongs to another project: {pid}, {version}')
        groups.setdefault(pid, []).append((version, created_at, raw, payload))
    if set(groups) != {row[0] for row in root_rows}:
        raise RescueError('Mismatch between project identities and history')
    reconstructed=[]
    for pid, name, project_version, updated_at in root_rows:
        rows=groups[pid]
        if [v for v,_,_,_ in rows] != list(range(1, project_version+1)):
            raise RescueError(f'Incomplete revision chain: {pid}')
        version, _, raw, payload=rows[-1]
        if payload.get('name', '') != name:
            raise RescueError(f'Project name differs from last revision: {pid}')
        reconstructed.append((pid,name,version,updated_at,raw))
    return reconstructed, [(pid, ver, created, raw)
                           for pid, ver, created, raw in revision_rows]


def rescue(source: str | Path, destination: str | Path) -> dict[str, Any]:
    source = Path(source).resolve(strict=True)
    dest = Path(destination).resolve()
    if not source.is_file() or not source.stat().st_size:
        raise RescueError('Invalid source file')
    if source == dest or dest.exists():
        raise RescueError('The output must be a new path, different from source')
    if not dest.parent.is_dir():
        raise RescueError('The output directory must already exist')
    source_hash = _digest(source.read_bytes())
    con = None
    temp_path = None
    try:
        # immutable is read-only and avoids locking or writing -wal/-shm.
        # Suitable ONLY for a closed diagnostic copy, not a live database.
        con=sqlite3.connect(source.as_uri()+'?mode=ro&immutable=1',uri=True)
        check = con.execute('PRAGMA integrity_check').fetchone()[0]
        if check == 'ok':
            raise RescueError('Source is healthy; forensic rescue is not needed')
        projects, revisions = _read_evidence(con)
        with tempfile.NamedTemporaryFile(dir=dest.parent, prefix='.rescue-', suffix='.db', delete=False) as tmp:
            temp_path=Path(tmp.name)
        out=sqlite3.connect(temp_path)
        try:
            out.executescript('''
            CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1, updated_at REAL NOT NULL,
                payload TEXT NOT NULL);
            CREATE TABLE revisions (project_id TEXT NOT NULL, version INTEGER NOT NULL,
                created_at REAL NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY(project_id,version));
            ''')
            out.text_factory=bytes
            for pid,name,ver,updated,raw in projects:
                out.execute('INSERT INTO projects VALUES(?,?,?,?,CAST(? AS TEXT))',
                            (pid,name,ver,updated,raw))
            for pid,ver,created,raw in revisions:
                out.execute('INSERT INTO revisions VALUES(?,?,?,CAST(? AS TEXT))',
                            (pid,ver,created,raw))
            out.commit()
            result=out.execute('PRAGMA integrity_check').fetchone()[0]
            if result != b'ok':
                raise RescueError(f'Recovered copy failed SQLite integrity check: {result!r}')
            for pid, _, ver, _, raw in projects:
                stored=out.execute('SELECT CAST(payload AS BLOB) FROM projects WHERE id=?',(pid,)).fetchone()[0]
                if stored != raw:
                    raise RescueError(f'Recovered project differs from authoritative revision: {pid}')
                last=out.execute('SELECT CAST(payload AS BLOB) FROM revisions WHERE project_id=? AND version=?',(pid,ver)).fetchone()[0]
                if last != raw:
                    raise RescueError(f'Recovered revision differs from evidence: {pid}')
            count=out.execute('SELECT COUNT(*) FROM revisions').fetchone()[0]
            if count != len(revisions):
                raise RescueError('Recovered revision count differs from evidence')
        finally:
            out.close()
        if _digest(source.read_bytes()) != source_hash:
            raise RescueError('Source changed during examination; no result may be trusted')
        # Atomic no-replace publication. An exclusive placeholder followed by
        # os.replace() may overwrite another writer that raced into that path.
        try:
            os.link(temp_path, dest)
        except FileExistsError as exc:
            raise RescueError('Output appeared while recovering; refusing overwrite') from exc
        except OSError as exc:
            raise RescueError('Cannot atomically publish rescue without overwrite') from exc
        temp_path.unlink()
        temp_path=None
        with sqlite3.connect(dest.as_uri()+'?mode=ro&immutable=1',uri=True) as reread:
            if reread.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise RescueError('Post-rename integrity failed')
        return {'status':'RECOVERED_COPY_ONLY','root_cause':'UNRESOLVED',
                'source_sha256':source_hash,'output_sha256':_digest(dest.read_bytes()),
                'projects':len(projects),'revisions':len(revisions),
                'source_integrity_check':str(check),'output_integrity_check':'ok',
                'project_versions':{pid:ver for pid,_,ver,_,_ in projects},
                'source_unchanged':True,'output_path':str(dest)}
    finally:
        if con is not None: con.close()
        if temp_path is not None: temp_path.unlink(missing_ok=True)


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',help='Closed-off copy of corrupted SQLite database')
    parser.add_argument('destination',help='New, non-existing recovered database path')
    args=parser.parse_args()
    try:
        receipt=rescue(args.source,args.destination)
    except (RescueError, sqlite3.Error, OSError) as exc:
        parser.exit(2,f'BLOCKED (no recovery claimed): {exc}\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
