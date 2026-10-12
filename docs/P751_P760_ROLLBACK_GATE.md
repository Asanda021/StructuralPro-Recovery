# P751–P760 — Rollback Gate

A deterministic release rollback decision boundary.

- Requires a known-good target release.
- Requires verified backup and an available migration path.
- Blocks rollback when engineering regression evidence is present.
- Same-version rollback is rejected.
- The gate only decides readiness; it does not mutate project or engineering data.
