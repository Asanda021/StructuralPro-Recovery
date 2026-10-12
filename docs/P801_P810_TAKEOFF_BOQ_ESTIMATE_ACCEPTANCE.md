# P801-P810 — Takeoff → BOQ → Estimate Acceptance

This stage closes one explicit production path: takeoff rows are resolved to supplied, provenance-bearing Iranian price records, then passed to the existing BOQ/estimate engine. Missing price provenance or invalid rows fail closed.

No price is fabricated, converted silently, or substituted. Quantity values supplied by takeoff are preserved into BOQ; pricing is attached explicitly as a separate concern.
