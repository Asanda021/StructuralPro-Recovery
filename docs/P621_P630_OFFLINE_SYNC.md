# P621–P630 — Offline Sync / Conflict / E2E

Offline changes are represented as explicit immutable envelopes. A client may queue work locally, but it may not silently overwrite newer server state.

## Conflict rule
If the client's base revision differs from the server revision, the result is conflict. The system returns the evidence/fingerprint and requires an explicit reconciliation path. No automatic engineering-value merge is performed.

## Security boundary
Transport encryption/authentication belongs to the production transport adapter; this contract itself never stores credentials or secrets.
