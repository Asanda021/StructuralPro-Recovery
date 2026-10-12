# P281-P290 — Backup / Restore Integrity

## Repository-derived scope
The repository's Backup/Restore documentation requires readable backups, integrity/tamper validation, safe restore, project integrity checks, audit/revision review and an operational restore record. This phase adds a deterministic contract at the platform boundary; it does not invent a storage engine or cloud backup service.

## Priority mapping
- P281 Backup identity/evidence contract
- P282 Source revision binding
- P283 Backup payload fingerprint
- P284 Restore operator/evidence contract
- P285 Project integrity evidence
- P286 Backup/restore identity matching
- P287 Fail-closed restore decision
- P288 Resulting revision binding
- P289 Deterministic integrity fingerprint
- P290 Dedicated regression gate

## Boundary
The implementation is offline-first and deterministic. It does not claim encrypted storage, cloud backup, proprietary project storage, or automatic forensic recovery infrastructure.
