# P501–P510 — Mobile / Field

## Purpose
Provide an offline-first, evidence-bound field packet contract for future mobile/field clients.

## Rules
- Every packet retains project, device, revision and source evidence.
- Field capture is queued locally before synchronization.
- Conflicted packets cannot silently become synced.
- Payload identity is represented by a deterministic hash.
- This contract does not perform engineering calculations or invent quantities.
- Android/mobile UI and provider-specific transport remain client/runtime concerns behind this shared contract.
