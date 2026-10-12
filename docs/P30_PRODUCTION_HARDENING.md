# P30 — Production Hardening

P30 is the authoritative roadmap phase for production hardening.

## Gate
The phase is evidence-first, deterministic and fail-closed. It composes the
existing production contracts and does not change engineering quantity,
calculation, BOQ or AI decision logic.

## Master coverage
- Performance and bounded execution
- Memory-safe bounded payload handling
- Large-project/PDF/CAD/BIM production boundary
- Concurrency protection
- Error handling
- Crash/recovery boundary
- Redacted rotating logging
- Security and offline/network policy
- Data integrity and tamper fingerprints
- Backup/restore integrity
- Explicit schema migration
- Compatibility/contract determinism

## Acceptance rule
P30 is green only when the dedicated P30 tests pass, CI is successful, the PR
is merged, and post-merge verification on the merge SHA is fully successful.

No customer data is fabricated by this gate. The checks exercise repository
production contracts and deterministic probes only.
