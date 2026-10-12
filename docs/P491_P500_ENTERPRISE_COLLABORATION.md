# P491–P500 — Enterprise Collaboration

## Purpose
Provide a deterministic collaboration boundary for multi-user AEC project work.

## Rules
- Every change retains project identity, actor, role, revision and source evidence.
- Role permissions are explicit; approval requires an approver role.
- Collaboration state transitions are deterministic.
- Missing evidence or invalid identity fails closed.
- This layer does not silently mutate engineering quantities or invent technical values.
- Provider-specific cloud synchronization remains behind the existing offline-first/sync contracts.
