# Backup and Restore Guide

## Backup policy

Create a backup before:
- importing a large drawing set;
- bulk price/catalog changes;
- project migration;
- application upgrade;
- major revision;
- restoring another backup.

Keep more than one independent backup for important projects.

## Backup validation

A backup is not considered operationally trusted until:
1. the backup can be read;
2. its integrity/tamper checks pass where applicable;
3. restore completes without validation errors;
4. project integrity checks pass;
5. key quantities and totals are spot-checked.

## Restore procedure

1. Stop editing the affected project.
2. Preserve the current project state if it may be needed for forensic comparison.
3. Select the intended backup.
4. Restore into the supported project/storage boundary.
5. Run integrity validation.
6. Review audit/history/revision state.
7. Check takeoff quantities, BOQ, estimates and relevant finance totals.
8. Create a new revision after accepting the restored state.

## Recovery principle

Restore must fail safely when a backup is invalid, tampered with or incompatible. Never silently accept corrupted project data.

## Operational record

For formal project work, record:
- backup date/time;
- source project/revision;
- backup identifier;
- restore operator;
- validation result;
- resulting revision.
