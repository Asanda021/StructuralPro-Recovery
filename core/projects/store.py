"""Offline-first project persistence with SQLite, revisions and backups."""
from __future__ import annotations
import json, sqlite3, time
from copy import deepcopy
from pathlib import Path
from typing import Any
from core.platform.concurrency import assert_unchanged, begin_write

def _contract_basis(project: dict[str, Any]) -> str:
    """Canonical payable BOQ and approved pricebook backing a financial estimate.

    Current/previous period work quantities are deliberately not part of a
    *contract* revision; changing a unit price, source, item, or amount is.
    """
    pricebook = project.get("user_pricebook_review") or {}
    keys = ("item_code", "quantity", "unit", "source_ids", "source_id",
            "price_code", "unit_price", "effective_quantity", "factor", "total")
    return json.dumps({
        "boq": [{key: row.get(key) for key in keys if key in row}
                for row in (project.get("boq") or [])],
        "pricebook": {key: pricebook.get(key) for key in
                      ("status", "sha256", "approved_by", "path", "rows_by_code")},
    }, ensure_ascii=False, sort_keys=True, allow_nan=False)


class ProjectStore:
    @staticmethod
    def _parent_identities(path: Path) -> tuple[tuple[int, int], ...]:
        """Snapshot every parent directory from db/ through the filesystem root.

        A replacement directory may expose a *hardlink to the same DB inode*.
        Checking the database file alone cannot detect that the SQLite journal
        and sidecar paths have been moved to a different directory.
        """
        identities = []
        parent = path.parent
        while True:
            info = parent.stat()
            identities.append((info.st_dev, info.st_ino))
            if parent == parent.parent:
                break
            parent = parent.parent
        return tuple(identities)

    def __init__(self, path: str | Path):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        existing = self.path.exists()
        before_open = self.path.stat() if existing else None
        # Pin the directory chain *before* opening SQLite. A directory may be
        # replaced while connect() is returning without changing the file inode.
        self._directory_identities = self._parent_identities(self.path)
        if before_open is not None and (not self.path.is_file() or before_open.st_size == 0):
            raise RuntimeError("SQLite integrity check failed: existing project database is empty or not a regular file")
        self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self._identity_failed=False
        self._cache: dict[str, tuple[int, dict[str, Any]]] = {}
        try:
            # A pathname may be replaced during sqlite3.connect(). Never
            # pin the *replacement* inode to an older live connection.
            try:
                opened=self.path.stat()
            except OSError as exc:
                raise RuntimeError("database identity changed during open; recover only from verified evidence") from exc
            self._file_identity=(opened.st_dev, opened.st_ino)
            if before_open is not None and self._file_identity != (before_open.st_dev, before_open.st_ino):
                self._identity_failed=True
            self._assert_database_identity()
            # Fail closed on a damaged existing database before any schema write.
            if existing:
                try:
                    result = self.db.execute("PRAGMA quick_check").fetchall()
                    if len(result) != 1 or result[0][0] != "ok":
                        raise RuntimeError("SQLite integrity check failed: project database is corrupt; restore only from verified evidence")
                    from core.recovery.recovery import require_project_history_consistency
                    require_project_history_consistency(self.db,allow_empty_schema=True)
                except sqlite3.DatabaseError as exc:
                    raise RuntimeError("SQLite integrity check failed: project database could not be read") from exc
            # The file can also change during integrity/schema initialization.
            self._assert_database_identity()
            self.db.execute("""CREATE TABLE IF NOT EXISTS projects(
                id TEXT PRIMARY KEY, name TEXT NOT NULL, version INTEGER NOT NULL DEFAULT 1,
                updated_at REAL NOT NULL, payload TEXT NOT NULL)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS revisions(
                project_id TEXT NOT NULL, version INTEGER NOT NULL, created_at REAL NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(project_id,version))""")
            self._assert_database_identity()
            self.db.commit()
            self._assert_database_identity()
        except Exception:
            self.db.close()
            raise

    def _assert_database_identity(self):
        """Fail closed if the pathname no longer denotes this store's file.

        Never reconnect implicitly: the displaced connection may contain a newer
        committed revision than the replacement. Preserve both for recovery.
        """
        try:
            current=self.path.stat()
            matches=(
                (current.st_dev,current.st_ino)==self._file_identity
                and self._parent_identities(self.path)==self._directory_identities
            )
        except OSError:
            matches=False
        if self._identity_failed or not matches:
            self._identity_failed=True
            self._cache.clear()
            raise RuntimeError("database identity changed; save outcome may be uncertain; close and recover only from verified evidence")

    def save(self, project_id: str, project: dict[str,Any], *, expected_digest: str | None = None, amendment_command: dict | None = None, financial_request_command: dict | None = None, manual_formula_command: dict | None = None, structural_handoff_command: dict | None = None, ifc_command: dict | None = None, phase3_command: dict | None = None, project_control_command: dict | None = None) -> dict[str,Any]:
        """Version-check and write project + revision in one SQLite transaction.

        BEGIN IMMEDIATE acquires the write reservation *before* the comparison.
        A competing connection cannot validate against a stale version and then
        overwrite the current row.
        """
        self._assert_database_identity()
        pid=str(project_id); now=time.time()
        clean_project=deepcopy(project)
        clean_project.pop("_meta",None)
        payload=json.dumps(clean_project,ensure_ascii=False,sort_keys=True,allow_nan=False)
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row=self.db.execute("SELECT version,payload FROM projects WHERE id=?",(pid,)).fetchone()
            incoming_version=(project.get("_meta") or {}).get("version")
            if row is not None and incoming_version is not None and incoming_version != int(row["version"]):
                raise RuntimeError("project changed since write began")
            if row is not None and expected_digest is None and pid in self._cache:
                cached=deepcopy(self._cache[pid][1]);cached.pop("_meta",None)
                assert_unchanged(json.loads(row["payload"]), begin_write(cached))
            if expected_digest is not None:
                if row is None:
                    raise RuntimeError("project changed since write began")
                current=json.loads(row["payload"])
                assert_unchanged(current, expected_digest)
            if row is not None:
                previous = json.loads(row["payload"])
                issued = previous.get("statement_periods") or []
                if issued and previous.get('statement_workflow_terms') and previous.get('factor_review')!=clean_project.get('factor_review'):
                    raise ValueError('تغییر ضرایب پس از صدور رسمی نیازمند الحاقیه مستقل است')
                if issued:
                    next_periods = clean_project.get("statement_periods") or []
                    if not isinstance(next_periods, list) or next_periods[:len(issued)] != issued:
                        raise ValueError("تغییر یا حذف صورت‌وضعیت صادرشده نیازمند اصلاحیه رسمی است")
                    for family in ("takeoffs", "takeoff_assemblies"):
                        if (previous.get(family) or []) != (clean_project.get(family) or []):
                            raise ValueError("تغییر مبنای متره صورت‌وضعیت صادرشده نیازمند اصلاحیه رسمی است")
                if (previous.get("estimate") or previous.get("statement_periods")) and \
                        _contract_basis(previous) != _contract_basis(clean_project):
                    if previous.get("statement_periods"):
                        raise ValueError("پس از صدور صورت‌وضعیت، تغییر مبنای BOQ یا فهرست‌بها نیازمند گردش اصلاحیه رسمی است")
                    # An old estimate must never masquerade as current after a
                    # quantity, approved pricebook or payable-unit change.
                    clean_project.pop("estimate", None)
                    payload=json.dumps(clean_project,ensure_ascii=False,sort_keys=True,allow_nan=False)
            from core.projects.controls import guard as project_control_guard
            project_control_guard(json.loads(row['payload']) if row else {},clean_project,project_control_command)
            from core.commercial.financial_ledger import ledger_guard
            ledger_guard(json.loads(row["payload"]) if row else {}, clean_project, phase3_command)
            from core.commercial.statement import workflow_guard
            workflow_guard(json.loads(row['payload']) if row else {}, clean_project, phase3_command)
            from core.drawings.ifc_pipeline import identity_guard
            identity_guard(json.loads(row['payload']) if row else {},clean_project,ifc_command)
            from core.takeoff.structural_handoff_work import guard as handoff_guard
            handoff_guard(json.loads(row["payload"]) if row else {},clean_project,structural_handoff_command)
            from core.takeoff.manual_formula_amendments import guard as manual_guard
            manual_guard(json.loads(row['payload']) if row else {},clean_project,manual_formula_command)
            from core.commercial.statement_amendment import guard_change
            guard_change(json.loads(row["payload"]) if row else {}, clean_project, amendment_command)
            from core.commercial.contract_requests import guard
            guard(json.loads(row["payload"]) if row else {}, clean_project, financial_request_command)
            from core.commercial.financial_ledger import settlement_guard
            settlement_guard(clean_project)
            version=int(row["version"])+1 if row else 1
            self.db.execute("INSERT OR REPLACE INTO projects(id,name,version,updated_at,payload) VALUES(?,?,?,?,?)",
                            (pid,str(clean_project.get("name","")),version,now,payload))
            self.db.execute("INSERT OR REPLACE INTO revisions(project_id,version,created_at,payload) VALUES(?,?,?,?)",
                            (pid,version,now,payload))
            self._assert_database_identity()
            self.db.commit()
            self._assert_database_identity()
        except Exception as exc:
            # SQLite can report an observed DBMOVED even when the pathname was
            # immediately restored to its former inode. An inode-only recheck
            # would then incorrectly re-enable this uncertain connection.
            if (isinstance(exc, sqlite3.DatabaseError)
                    and getattr(exc, "sqlite_errorcode", None) == sqlite3.SQLITE_READONLY_DBMOVED):
                self._identity_failed=True
                self._cache.clear()
            try:
                self.db.rollback()
            except sqlite3.DatabaseError as rollback_exc:
                if getattr(rollback_exc, "sqlite_errorcode", None) == sqlite3.SQLITE_READONLY_DBMOVED:
                    self._identity_failed=True
                    self._cache.clear()
                if not self._identity_failed:
                    raise
            raise
        # Cache the same JSON representation committed to SQLite. Coordinates
        # may arrive as tuples; a cache hit must equal a reopened snapshot.
        cached=json.loads(payload)
        cached["_meta"]={"id":pid,"version":version,"updated_at":now}
        self._cache[pid] = (version,cached)
        return {"id":pid,"version":version,"updated_at":now}

    def begin_write(self, project_id: str) -> str:
        self._assert_database_identity()
        row = self.db.execute("SELECT payload FROM projects WHERE id=?", (str(project_id),)).fetchone()
        if row is None:
            raise KeyError(project_id)
        return begin_write(json.loads(row["payload"]))

    def current_digest(self, project_id: str) -> str:
        return self.begin_write(project_id)

    def get(self, project_id: str) -> dict[str,Any] | None:
        self._assert_database_identity()
        pid=str(project_id)
        # Check the small SQLite version column before fetching a large payload.
        # This prevents stale reads without deserializing drawings/BOQ on every UI hit.
        version_row=self.db.execute("SELECT version FROM projects WHERE id=?",(pid,)).fetchone()
        if not version_row:
            self._cache.pop(pid,None)
            return None
        cached=self._cache.get(pid)
        if cached is not None and cached[0] == int(version_row["version"]):
            return deepcopy(cached[1])
        row=self.db.execute("SELECT * FROM projects WHERE id=?",(pid,)).fetchone()
        if not row:
            self._cache.pop(pid,None)
            return None
        data=json.loads(row["payload"])
        data["_meta"]={"id":row["id"],"version":row["version"],"updated_at":row["updated_at"]}
        self._cache[pid]=(int(row["version"]), deepcopy(data))
        return deepcopy(data)

    def list(self, *, limit: int | None = None, offset: int = 0) -> list[dict[str,Any]]:
        self._assert_database_identity()
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
        self._assert_database_identity()
        return [{"version":r["version"],"created_at":r["created_at"],"payload":json.loads(r["payload"])}
                for r in self.db.execute("SELECT version,created_at,payload FROM revisions WHERE project_id=? ORDER BY version",(str(project_id),))]

    def integrity_check(self) -> dict[str, Any]:
        self._assert_database_identity()
        from core.recovery.recovery import verify_database
        return verify_database(self.path)

    def backup(self, backup_path: str | Path) -> dict[str, Any]:
        self._assert_database_identity()
        from core.recovery.recovery import backup_database
        return backup_database(self.path, backup_path)

    def close(self):
        self.db.close()
