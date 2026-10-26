"""Offline-first project persistence with SQLite, revisions and backups."""
from __future__ import annotations
import json, sqlite3, time
from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from typing import Any
from core.platform.concurrency import assert_unchanged, begin_write
from core.platform.audit_integrity import GENESIS, event_digest, verify_chain
from core.platform.identity import OperatingSystemIdentity, SystemIdentityProvider
from core.security_hardening_v2 import ALLOWED_ROLES, SecurityPrincipal

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
    _DIRECT_PRIVILEGED_FIELDS = frozenset({
        "financial_documents", "financial_budget", "commitment_entries",
        "cost_entries", "payment_entries", "receipt_entries",
        "payment_allocations", "financial_records", "financial_reversals",
        "statement_periods", "statement_workflow_terms", "statement_workflow",
        "statement_amendments", "factor_review", "user_pricebook_review",
    })
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

    def __init__(self, path: str | Path, *, identity_provider=None):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self._identity_provider = identity_provider or SystemIdentityProvider()
        existing = self.path.exists()
        before_open = self.path.stat() if existing else None
        # Pin the directory chain *before* opening SQLite. A directory may be
        # replaced while connect() is returning without changing the file inode.
        self._directory_identities = self._parent_identities(self.path)
        if before_open is not None and (not self.path.is_file() or before_open.st_size == 0):
            raise RuntimeError("SQLite integrity check failed: existing project database is empty or not a regular file")
        self.db=sqlite3.connect(self.path); self.db.row_factory=sqlite3.Row
        self._identity_failed=False
        self._transaction_uncertain=False
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
            self.db.execute("""CREATE TABLE IF NOT EXISTS project_acl(
                project_id TEXT NOT NULL, subject_id TEXT NOT NULL, role TEXT NOT NULL,
                granted_at REAL NOT NULL, granted_by TEXT NOT NULL, source TEXT NOT NULL,
                PRIMARY KEY(project_id,subject_id),
                CHECK(role IN ('owner','admin','editor','reviewer','viewer')))""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS security_audit(
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL, timestamp TEXT NOT NULL,
                action TEXT NOT NULL, entity TEXT NOT NULL, entity_id TEXT NOT NULL,
                actor TEXT NOT NULL, actor_role TEXT NOT NULL,
                revision_before INTEGER, revision_after INTEGER,
                reference TEXT NOT NULL, status TEXT NOT NULL,
                event_json TEXT NOT NULL, previous_hash TEXT NOT NULL, hash TEXT NOT NULL)""")
            self.db.execute("""CREATE TABLE IF NOT EXISTS security_audit_heads(
                project_id TEXT PRIMARY KEY, last_sequence INTEGER NOT NULL,
                last_hash TEXT NOT NULL, event_count INTEGER NOT NULL)""")
            self.db.execute("""CREATE TRIGGER IF NOT EXISTS security_audit_no_update
                BEFORE UPDATE ON security_audit BEGIN
                SELECT RAISE(ABORT, 'security audit is append-only'); END""")
            self.db.execute("""CREATE TRIGGER IF NOT EXISTS security_audit_no_delete
                BEFORE DELETE ON security_audit BEGIN
                SELECT RAISE(ABORT, 'security audit is append-only'); END""")
            if existing:
                self._migrate_owned_legacy_projects()
            self._assert_audit_integrity()
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
        if self._transaction_uncertain:
            self._cache.clear()
            raise RuntimeError(
                "database connection quarantined; save outcome may be uncertain; "
                "close and reconcile only from verified evidence"
            )
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

    def _identity(self) -> OperatingSystemIdentity:
        identity = self._identity_provider.current()
        if not isinstance(identity, OperatingSystemIdentity) or not identity.authenticated:
            raise PermissionError("valid operating-system principal is required")
        return identity

    def _legacy_claim_allowed(self, identity: OperatingSystemIdentity) -> bool:
        if not getattr(self._identity_provider, "trusted_for_legacy_claim", False):
            return False
        try:
            return bool(self._identity_provider.owns_path(identity, self.path))
        except (OSError, RuntimeError):
            return False

    def _migrate_owned_legacy_projects(self) -> None:
        identity = self._identity()
        if not self._legacy_claim_allowed(identity):
            return
        rows = self.db.execute("""SELECT p.id,p.version FROM projects p
            WHERE NOT EXISTS(SELECT 1 FROM project_acl a WHERE a.project_id=p.id)""").fetchall()
        for row in rows:
            pid = str(row["id"])
            revision = int(row["version"])
            self.db.execute("""INSERT INTO project_acl(project_id,subject_id,role,granted_at,granted_by,source)
                VALUES(?,?,?,?,?,?)""",
                (pid, identity.subject_id, "owner", time.time(), identity.subject_id, "legacy-file-owner"))
            self._append_audit(
                project_id=pid, identity=identity, role="owner", action="authorize",
                entity="project_acl", revision_before=revision, revision_after=revision,
                reference="migration:legacy-file-owner", status="success",
            )

    def _role(self, project_id: str, identity: OperatingSystemIdentity) -> str | None:
        row = self.db.execute(
            "SELECT role FROM project_acl WHERE project_id=? AND subject_id=?",
            (str(project_id), identity.subject_id),
        ).fetchone()
        return str(row["role"]) if row else None

    def _principal(self, project_id: str, required_roles: tuple[str, ...]) -> SecurityPrincipal:
        identity = self._identity()
        role = self._role(project_id, identity)
        if role not in required_roles:
            raise PermissionError("role is not authorized for this project operation")
        return SecurityPrincipal(identity.subject_id, str(project_id), role)

    def current_principal(self, project_id: str) -> SecurityPrincipal:
        return self._principal(str(project_id), tuple(ALLOWED_ROLES))

    def _append_audit(self, *, project_id: str, identity: OperatingSystemIdentity,
                      role: str | None, action: str, entity: str,
                      revision_before: int | None, revision_after: int | None,
                      reference: str, status: str,
                      before: object = None, after: object = None) -> dict[str, Any]:
        from datetime import datetime, timezone

        head = self.db.execute(
            "SELECT last_sequence,last_hash,event_count FROM security_audit_heads WHERE project_id=?",
            (project_id,),
        ).fetchone()
        previous = str(head["last_hash"]) if head else GENESIS
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "entity": entity,
            "entity_id": project_id,
            "before": deepcopy(before),
            "after": deepcopy(after),
            "actor": identity.subject_id,
            "actor_role": role or "unassigned",
            "project_id": project_id,
            "revision_before": revision_before,
            "revision_after": revision_after,
            "reference": reference,
            "status": status,
        }
        digest = event_digest(event, previous)
        encoded = json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False)
        cursor = self.db.execute("""INSERT INTO security_audit(
            project_id,timestamp,action,entity,entity_id,actor,actor_role,
            revision_before,revision_after,reference,status,event_json,previous_hash,hash)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            project_id, event["timestamp"], action, entity, project_id,
            identity.subject_id, role or "unassigned", revision_before,
            revision_after, reference, status, encoded, previous, digest,
        ))
        count = int(head["event_count"]) + 1 if head else 1
        self.db.execute("""INSERT INTO security_audit_heads(project_id,last_sequence,last_hash,event_count)
            VALUES(?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET
            last_sequence=excluded.last_sequence,last_hash=excluded.last_hash,event_count=excluded.event_count""",
            (project_id, int(cursor.lastrowid), digest, count))
        event["previous_hash"] = previous
        event["hash"] = digest
        return event

    def _assert_audit_integrity(self) -> None:
        project_ids = {str(row["id"]) for row in self.db.execute("SELECT id FROM projects")}
        audited_ids = {str(row["project_id"]) for row in self.db.execute(
            "SELECT DISTINCT project_id FROM security_audit"
        )}
        head_ids = {str(row["project_id"]) for row in self.db.execute(
            "SELECT project_id FROM security_audit_heads"
        )}
        if audited_ids != project_ids or head_ids != project_ids:
            raise RuntimeError("security audit integrity check failed: project/audit coverage mismatch")
        columns = (
            "timestamp", "action", "entity", "entity_id", "actor", "actor_role",
            "revision_before", "revision_after", "reference", "status",
        )
        for pid in project_ids:
            rows = self.db.execute(
                "SELECT * FROM security_audit WHERE project_id=? ORDER BY sequence", (pid,)
            ).fetchall()
            events = []
            for row in rows:
                event = json.loads(row["event_json"])
                if any(event.get(key) != row[key] for key in columns):
                    raise RuntimeError("security audit integrity check failed: event columns diverged")
                event["previous_hash"] = row["previous_hash"]
                event["hash"] = row["hash"]
                events.append(event)
            head = self.db.execute(
                "SELECT last_sequence,last_hash,event_count FROM security_audit_heads WHERE project_id=?",
                (pid,),
            ).fetchone()
            if not events or head is None or not verify_chain(events):
                raise RuntimeError("security audit integrity check failed: hash chain is invalid")
            if (int(head["event_count"]) != len(events)
                    or int(head["last_sequence"]) != int(rows[-1]["sequence"])
                    or str(head["last_hash"]) != str(rows[-1]["hash"])):
                raise RuntimeError("security audit integrity check failed: chain head mismatch")

    def _record_denied(self, project_id: str, identity: OperatingSystemIdentity,
                       role: str | None, action: str, revision: int | None,
                       reference: str) -> None:
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self._append_audit(
                project_id=project_id, identity=identity, role=role,
                action=action, entity="project", revision_before=revision,
                revision_after=None, reference=reference, status="failure",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def grant_role(self, project_id: str, subject_id: str, role: str, *, reference: str) -> None:
        pid = str(project_id)
        identity = self._identity()
        if role not in ALLOWED_ROLES or not str(subject_id).strip() or not str(reference).strip():
            raise ValueError("valid project role, subject and audit reference are required")
        self.db.execute("BEGIN IMMEDIATE")
        current_role = self._role(pid, identity)
        row = self.db.execute("SELECT version FROM projects WHERE id=?", (pid,)).fetchone()
        revision = int(row["version"]) if row else None
        allowed = current_role == "owner" or (current_role == "admin" and role not in {"owner", "admin"})
        if not allowed:
            self.db.rollback()
            self._record_denied(pid, identity, current_role, "authorize", revision, reference)
            raise PermissionError("role is not authorized for this project operation")
        try:
            self.db.execute("""INSERT INTO project_acl(project_id,subject_id,role,granted_at,granted_by,source)
                VALUES(?,?,?,?,?,?) ON CONFLICT(project_id,subject_id) DO UPDATE SET
                role=excluded.role,granted_at=excluded.granted_at,
                granted_by=excluded.granted_by,source=excluded.source""",
                (pid, str(subject_id), role, time.time(), identity.subject_id, "trusted-principal"))
            self._append_audit(
                project_id=pid, identity=identity, role=current_role,
                action="authorize", entity="project_acl", revision_before=revision,
                revision_after=revision, reference=reference, status="success",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def audit_events(self, project_id: str) -> list[dict[str, Any]]:
        pid = str(project_id)
        self._principal(pid, tuple(ALLOWED_ROLES))
        events = []
        for row in self.db.execute(
            "SELECT event_json,previous_hash,hash FROM security_audit WHERE project_id=? ORDER BY sequence",
            (pid,),
        ):
            event = json.loads(row["event_json"])
            event["previous_hash"] = row["previous_hash"]
            event["hash"] = row["hash"]
            events.append(event)
        return events

    def verify_audit(self, project_id: str) -> bool:
        pid = str(project_id)
        events = self.audit_events(pid)
        head = self.db.execute(
            "SELECT last_sequence,last_hash,event_count FROM security_audit_heads WHERE project_id=?",
            (pid,),
        ).fetchone()
        if not events or head is None:
            return False
        last = self.db.execute(
            "SELECT sequence,hash FROM security_audit WHERE project_id=? ORDER BY sequence DESC LIMIT 1",
            (pid,),
        ).fetchone()
        return bool(
            verify_chain(events)
            and int(head["event_count"]) == len(events)
            and int(head["last_sequence"]) == int(last["sequence"])
            and str(head["last_hash"]) == str(last["hash"])
        )

    @staticmethod
    def _mutation_policy(*, amendment_command=None, financial_request_command=None,
                         manual_formula_command=None, phase3_command=None,
                         project_control_command=None) -> tuple[set[str], str]:
        command = next((item for item in (
            amendment_command, financial_request_command, manual_formula_command,
            phase3_command, project_control_command,
        ) if item), None)
        if not command:
            return {"owner", "admin", "editor"}, "project-store:save"
        operation = str(command.get("op") or command.get("action") or "update").lower()
        reference = f"project-store:{operation}"
        if "approve" in operation:
            return {"owner", "admin"}, reference
        if "review" in operation:
            return {"owner", "admin", "reviewer"}, reference
        if any(token in operation for token in ("post", "apply", "reverse", "settle", "commit")):
            return {"owner", "admin"}, reference
        return {"owner", "admin", "editor"}, reference

    @classmethod
    def _direct_privileged_change(cls, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        keys = cls._DIRECT_PRIVILEGED_FIELDS | {
            key for key in set(previous) | set(current)
            if "approved" in key.casefold() or "reviewed" in key.casefold()
        }
        return any(previous.get(key) != current.get(key) for key in keys)

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
        required_roles, audit_reference = self._mutation_policy(
            amendment_command=amendment_command,
            financial_request_command=financial_request_command,
            manual_formula_command=manual_formula_command,
            phase3_command=phase3_command,
            project_control_command=project_control_command,
        )
        identity = None
        role = None
        row = None
        try:
            self.db.execute("BEGIN IMMEDIATE")
            row=self.db.execute("SELECT version,payload FROM projects WHERE id=?",(pid,)).fetchone()
            identity = self._identity()
            role = self._role(pid, identity)
            if row is None:
                role = "owner"
                self.db.execute("""INSERT INTO project_acl(project_id,subject_id,role,granted_at,granted_by,source)
                    VALUES(?,?,?,?,?,?)""",
                    (pid, identity.subject_id, role, now, identity.subject_id, "project-creation"))
            elif role is None and not self.db.execute(
                    "SELECT 1 FROM project_acl WHERE project_id=?", (pid,)).fetchone() \
                    and self._legacy_claim_allowed(identity):
                role = "owner"
                self.db.execute("""INSERT INTO project_acl(project_id,subject_id,role,granted_at,granted_by,source)
                    VALUES(?,?,?,?,?,?)""",
                    (pid, identity.subject_id, role, now, identity.subject_id, "legacy-file-owner"))
            previous_payload = json.loads(row["payload"]) if row else {}
            if audit_reference == "project-store:save" and self._direct_privileged_change(
                    previous_payload, clean_project):
                required_roles = {"owner", "admin"}
            if role not in required_roles:
                revision = int(row["version"]) if row else None
                self.db.rollback()
                self._record_denied(pid, identity, role, "update" if row else "create", revision, audit_reference)
                raise PermissionError("role is not authorized for this project operation")
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
            self._append_audit(
                project_id=pid, identity=identity, role=role,
                action="update" if row else "create", entity="project",
                revision_before=int(row["version"]) if row else None,
                revision_after=version, reference=audit_reference, status="success",
                after={"payload_sha256": sha256(payload.encode("utf-8")).hexdigest()},
            )
            self._assert_database_identity()
            try:
                self.db.commit()
            except Exception:
                # Once COMMIT has been attempted, an exception cannot prove
                # whether SQLite durably committed before acknowledgement was
                # lost. Never reuse this connection or claim a later save.
                self._transaction_uncertain=True
                self._cache.clear()
                raise
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
                self._transaction_uncertain=True
                self._cache.clear()
                if getattr(rollback_exc, "sqlite_errorcode", None) == sqlite3.SQLITE_READONLY_DBMOVED:
                    self._identity_failed=True
                    self._cache.clear()
                if not self._identity_failed:
                    raise
            # Authorization denials are recorded at the authorization boundary
            # above.  Domain-validation failures deliberately remain complete
            # no-ops, preserving the long-standing invariant that malformed
            # engineering input changes neither project data nor SQLite state.
            raise
        # Cache the same JSON representation committed to SQLite. Coordinates
        # may arrive as tuples; a cache hit must equal a reopened snapshot.
        cached=json.loads(payload)
        cached["_meta"]={"id":pid,"version":version,"updated_at":now}
        self._cache[pid] = (version,cached)
        return {"id":pid,"version":version,"updated_at":now}

    def begin_write(self, project_id: str) -> str:
        self._assert_database_identity()
        pid = str(project_id)
        row = self.db.execute("SELECT payload FROM projects WHERE id=?", (pid,)).fetchone()
        if row is None:
            raise KeyError(project_id)
        self._principal(pid, tuple(ALLOWED_ROLES))
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
        identity = self._identity()
        role = self._role(pid, identity)
        if role not in ALLOWED_ROLES:
            self._record_denied(pid, identity, role, "open", int(version_row["version"]), "project-store:get")
            raise PermissionError("role is not authorized for this project operation")
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
        identity = self._identity()
        query="""SELECT p.id,p.name,p.version,p.updated_at FROM projects p
            JOIN project_acl a ON a.project_id=p.id AND a.subject_id=?
            ORDER BY p.updated_at DESC"""
        params.append(identity.subject_id)
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
        self._principal(str(project_id), tuple(ALLOWED_ROLES))
        return [{"version":r["version"],"created_at":r["created_at"],"payload":json.loads(r["payload"])}
                for r in self.db.execute("SELECT version,created_at,payload FROM revisions WHERE project_id=? ORDER BY version",(str(project_id),))]

    def integrity_check(self) -> dict[str, Any]:
        self._assert_database_identity()
        from core.recovery.recovery import verify_database
        return verify_database(self.path)

    def backup(self, backup_path: str | Path) -> dict[str, Any]:
        self._assert_database_identity()
        identity = self._identity()
        projects = self.db.execute("SELECT id,version FROM projects ORDER BY id").fetchall()
        roles = {}
        for row in projects:
            role = self._role(str(row["id"]), identity)
            roles[str(row["id"])] = role
            if role not in {"owner", "admin"}:
                self._record_denied(
                    str(row["id"]), identity, role, "export", int(row["version"]),
                    "project-store:database-backup",
                )
                raise PermissionError("role is not authorized for this project operation")
        from core.recovery.recovery import backup_database
        result = backup_database(self.path, backup_path)
        target = Path(result["path"])
        try:
            digest = sha256(target.read_bytes()).hexdigest()
            self.db.execute("BEGIN IMMEDIATE")
            for row in projects:
                pid = str(row["id"])
                self._append_audit(
                    project_id=pid, identity=identity, role=roles[pid],
                    action="export", entity="database_backup",
                    revision_before=int(row["version"]), revision_after=int(row["version"]),
                    reference="project-store:database-backup", status="success",
                    after={"backup_sha256": digest, "size": int(result["size"])},
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            target.unlink(missing_ok=True)
            raise
        return result

    def close(self):
        self.db.close()
