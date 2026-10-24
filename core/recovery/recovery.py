"""Reliability and recovery primitives for StructuralPro persistence."""
from __future__ import annotations
import hashlib, json, os, sqlite3, tempfile, time
from pathlib import Path
from typing import Any

class RecoveryError(RuntimeError): pass

def payload_checksum(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _require_database_integrity(connection: sqlite3.Connection, *, label: str) -> None:
    """Do not accept a structurally damaged SQLite database as a valid backup."""
    try:
        results=connection.execute("PRAGMA integrity_check").fetchall()
    except sqlite3.DatabaseError as exc:
        raise RecoveryError(f"{label} database integrity check could not run") from exc
    if len(results) != 1 or results[0][0] != "ok":
        raise RecoveryError(f"{label} database integrity check failed: corrupt SQLite data")


def require_project_history_consistency(connection: sqlite3.Connection, *, allow_empty_schema: bool = False) -> None:
    """Reject a sound SQLite page tree with invalid JSON or torn project revisions."""
    try:
        names={row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name IN ('projects','revisions')")}
        if not names and allow_empty_schema:
            return
        if names != {'projects','revisions'}:
            raise RecoveryError('project database schema and revision history are incomplete')
        projects=connection.execute(
            'SELECT id,name,version,CAST(payload AS BLOB) FROM projects').fetchall()
        for pid,name,version,raw in projects:
            if not isinstance(pid,str) or not pid or type(version) is not int or version < 1 or not isinstance(raw,bytes):
                raise RecoveryError('project identity, version or payload is invalid')
            try:
                def reject_nonfinite(value):
                    raise ValueError('non-finite JSON token '+value)
                active=json.loads(raw.decode('utf-8',errors='strict'),parse_constant=reject_nonfinite)
            except (UnicodeError,ValueError,TypeError) as exc:
                raise RecoveryError('active project JSON is unreadable or invalid') from exc
            if not isinstance(active,dict) or str(active.get('name',''))!=name:
                raise RecoveryError('active project JSON conflicts with its project metadata')
            if active.get('id') not in (None,pid) or active.get('project_id') not in (None,pid):
                raise RecoveryError('active project belongs to a different identity')
            tail=connection.execute(
                'SELECT CAST(payload AS BLOB) FROM revisions WHERE project_id=? AND version=?',
                (pid,version)).fetchone()
            if tail is None or tail[0]!=raw:
                raise RecoveryError('active project differs from its committed revision')
            lo,hi,count=connection.execute(
                'SELECT MIN(version),MAX(version),COUNT(*) FROM revisions WHERE project_id=?',
                (pid,)).fetchone()
            if (lo,hi,count)!=(1,version,version):
                raise RecoveryError('project revision chain is missing or inconsistent')
        orphan=connection.execute(
            'SELECT 1 FROM revisions AS r LEFT JOIN projects AS p ON r.project_id=p.id '
            'WHERE p.id IS NULL LIMIT 1').fetchone()
        if orphan is not None:
            raise RecoveryError('orphan revision history exists')
    except sqlite3.DatabaseError as exc:
        raise RecoveryError('project/revision history could not be verified') from exc


def backup_database(db_path: str | Path, backup_path: str | Path) -> dict[str, Any]:
    source_path=Path(db_path)
    if not source_path.is_file(): raise RecoveryError("source database does not exist")
    target_path=Path(backup_path)
    if source_path.resolve() == target_path.resolve():
        raise RecoveryError("backup must not overwrite its source database")
    if target_path.exists():
        raise RecoveryError("backup destination already exists; use a new path")
    target_path.parent.mkdir(parents=True,exist_ok=True)
    temp_path=None
    source=None
    try:
        source=sqlite3.connect(source_path.resolve().as_uri()+"?mode=ro", uri=True)
        _require_database_integrity(source, label="source")
        require_project_history_consistency(source)
        with tempfile.NamedTemporaryFile(prefix=".db-backup-",suffix=".tmp",
                                     dir=target_path.parent,delete=False) as temporary:
            temp_path=Path(temporary.name)
        target=sqlite3.connect(temp_path)
        try:
            source.backup(target)
            target.commit()
            _require_database_integrity(target, label="backup")
            require_project_history_consistency(target)
        finally:
            target.close()
        # Atomic no-replace publication. os.replace() can overwrite a competing
        # backup between the exists() check and the rename. Fail closed on
        # filesystems that do not permit a same-directory hard link.
        try:
            os.link(temp_path, target_path)
        except FileExistsError as exc:
            raise RecoveryError("backup destination appeared during backup") from exc
        except OSError as exc:
            raise RecoveryError("cannot atomically publish backup without overwrite") from exc
        temp_path.unlink()
        temp_path=None
        return {"path":str(target_path),"size":target_path.stat().st_size,
                "created_at":time.time()}
    finally:
        if source is not None: source.close()
        if temp_path is not None: temp_path.unlink(missing_ok=True)

def verify_database(db_path: str | Path) -> dict[str, Any]:
    source_path=Path(db_path)
    if not source_path.is_file(): raise RecoveryError("database does not exist")
    con=sqlite3.connect(source_path.resolve().as_uri()+"?mode=ro", uri=True)
    try:
        row=con.execute("PRAGMA integrity_check").fetchone()
        result=str(row[0]) if row else ""
        counts={}
        for table in ("projects","revisions"):
            counts[table]=int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        return {"ok":result.lower()=="ok","integrity_check":result,"counts":counts}
    finally: con.close()

def export_project(project: dict[str, Any], path: str | Path) -> dict[str, Any]:
    if not isinstance(project,dict) or not project.get("id"):
        raise RecoveryError("project must contain an id")
    target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
    envelope={"format":"StructuralPro Project Backup","schema_version":1,
              "exported_at":time.time(),"project":project}
    raw=json.dumps(envelope,ensure_ascii=False,sort_keys=True,indent=2)
    target.write_text(raw,encoding="utf-8")
    return {"path":str(target),"sha256":payload_checksum(raw),"bytes":len(raw.encode("utf-8"))}

def import_project(path: str | Path) -> dict[str, Any]:
    raw=Path(path).read_text(encoding="utf-8")
    try: envelope=json.loads(raw)
    except json.JSONDecodeError as exc: raise RecoveryError("invalid backup JSON") from exc
    if envelope.get("format")!="StructuralPro Project Backup" or envelope.get("schema_version")!=1:
        raise RecoveryError("unsupported project backup format")
    project=envelope.get("project")
    if not isinstance(project,dict) or not str(project.get("id","")).strip():
        raise RecoveryError("backup does not contain a valid project")
    return project
