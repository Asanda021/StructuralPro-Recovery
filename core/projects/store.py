"""Offline-first project persistence with SQLite, revisions and backups."""
from __future__ import annotations
import json, sqlite3, time
from copy import deepcopy
from pathlib import Path
from typing import Any
from core.platform.concurrency import assert_unchanged, begin_write

class ProjectStore:
    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self._cache: dict[str, tuple[int, dict[str, Any]]] = {}
        self.db.execute("""CREATE TABLE IF NOT EXISTS projects(
            id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
            updated_at REAL NOT NULL, payload TEXT NOT NULL)""")
        self.db.execute("""CREATE TABLE IF NOT EXISTS revisions(
            project_id TEXT NOT NULL, version INTEGER NOT NULL, created_at REAL NOT NULL,
            payload TEXT NOT NULL, PRIMARY KEY(project_id,version))""")
        self.db.commit()

    def save(self, project_id: str, project: dict[str,Any], *, expected_digest: str | None = None) -> dict[str,Any]:
        pid=str(project_id); now=time.time()
        row=self.db.execute("SELECT version,payload FROM projects WHERE id=?",(pid,)).fetchone()
        if expected_digest is not None:
            if row is None:
                raise RuntimeError("project changed since write began")
            current=json.loads(row["payload"])
            assert_unchanged(current, expected_digest)
        version=int(row["version"])+1 if row else 1
        payload=json.dumps(project,ensure_ascii=False,sort_keys=True)
        self.db.execute("INSERT OR REPLACE INTO projects(id,name,version,updated_at,payload) VALUES(?,?,?,?,?)",
                        (pid,str(project.get("name","")),version,now,payload))
        self.db.execute("INSERT OR REPLACE INTO revisions(project_id,version,created_at,payload) VALUES(?,?,?,?)",
                        (pid,version,now,payload))
        self.db.commit()
        self._cache[pid] = (version, deepcopy(project))
        return {"id":pid,"version":version,"updated_at":now}

    def begin_write(self, project_id: str) -> str:
        row = self.db.execute("SELECT payload FROM projects WHERE id=?", (str(project_id),)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return begin_write(json.loads(row["payload"]))

    def current_digest(self, project_id: str) -> str:
        return self.begin_write(project_id)

    def get(self, project_id: str) -> dict[str,Any] | None:
        pid=str(project_id)
        cached=self._cache.get(pid)
        if cached is not None:
            _, data=cached
            return deepcopy(data)
        row=self.db.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
        if not row: return None
        data=json.loads(row["payload"])
        data["_meta"]={"id":row["id"],"version":row["version"],"updated_at":row["updated_at"]}
        self._cache[pid]=(int(row["version"]), deepcopy(data))
        return data

    def list(self, *, limit: int | None = None, offset: int = 0) -> list[dict[str,Any]]:
        offset=int(offset)
        if offset < 0: raise ValueError("offset must be non-negative")
        params: list[Any]=[]
        query="SELECT id,name,version,updated_at FROM projects ORDER BY updated_at DESC"
        if limit is not None:
            limit=int(limit)
            if limit < 1: raise ValueError("limit must be positive")
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        return [dict(r) for r in self.db.execute(query,params)]

    def get_many(self, project_ids: list[str]) -> list[dict[str,Any]]:
        return [project for pid in project_ids if (project:=self.get(pid)) is not None]

    def revisions(self, project_id: str) -> list[dict[str,Any]]:
        return [{"version":r["version"],"created_at":r["created_at"],"payload":json.loads(r["payload"])}
                for r in self.db.execute("SELECT version,created_at,payload FROM revisions WHERE project_id=? ORDER BY version",(str(project_id),))]

    def integrity_check(self) -> dict[str, Any]:
        from core.recovery.recovery import verify_database
        return verify_database(self.path)

    def backup(self, backup_path: str | Path) -> dict[str, Any]:
        from core.recovery.recovery import backup_database
        return backup_database(self.path, backup_path)

    def close(self):
        self.db.close()
