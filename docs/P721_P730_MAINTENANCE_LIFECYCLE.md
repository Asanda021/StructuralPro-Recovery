# P721–P730 — Maintenance Lifecycle

A deterministic lifecycle boundary for production maintenance.

- Lifecycle states are explicit: draft, active, maintenance and retired.
- Unsupported states fail closed.
- Invalid transitions are blocked instead of being silently accepted.
- No engineering quantity or calculation result is changed by lifecycle state handling.
