# P641-P650 — Technical Office Advanced Automation

This phase composes the existing drawing → takeoff → BOQ → estimate → report
surfaces into one deterministic plan. It does not invent quantities, prices or
engineering decisions.

Guarantees:
- every item has explicit source identity;
- ordering is deterministic;
- review-required items cannot become approved implicitly;
- rejected/missing provenance fails closed;
- the plan fingerprint is reproducible;
- existing deterministic calculation engines remain authoritative.

The automation is an orchestration layer, not a replacement for engineering
calculation or quantity logic.
