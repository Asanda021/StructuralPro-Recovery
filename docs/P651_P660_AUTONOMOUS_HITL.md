# P651-P660 — Autonomous Workflow + Human-in-the-Loop

The system may propose actions, but execution is gated by an explicit human
approval containing reviewer identity and a reason.

Guarantees:
- proposals begin pending;
- approval/rejection is explicit;
- unknown approvals fail closed;
- rejected or pending proposals cannot execute;
- source provenance remains attached;
- workflow fingerprints are deterministic.

This boundary deliberately prevents AI or automation from silently changing
engineering/quantity results.
