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
        with tempfile.NamedTemporaryFile(prefix=".db-backup-",suffix=".tmp",
                                     dir=target_path.parent,delete=False) as temporary:
            temp_path=Path(temporary.name)
        target=sqlite3.connect(temp_path)
        try:
            source.backup(target)
            target.commit()
            _require_database_integrity(target, label="backup")
        finally:
            target.close()
        if target_path.exists():
            raise RecoveryError("backup destination appeared during backup")
        os.replace(temp_path,target_path)
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
