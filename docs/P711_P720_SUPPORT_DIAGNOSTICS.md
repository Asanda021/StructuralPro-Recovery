# P711–P720 — Privacy-Safe Support Diagnostics

A deterministic support-evidence boundary.

- Diagnostic snapshots are JSON and stable.
- Secret-like fields are redacted before evidence is produced.
- The implementation is local/offline and does not transmit diagnostics.
- Redaction is applied recursively to nested mappings and sequences.
