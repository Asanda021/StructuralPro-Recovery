# P120 — BIM/IFC Production Acceptance

P120 establishes the production gate for BIM/IFC quantity interoperability.

Covered: canonical BIM identity/classification, explicit IFC quantity extraction, BIM-to-takeoff bridge, BIM/drawing discrepancy detection, IFC4 interchange identity, deterministic fingerprint/round-trip verification, and manifest digest verification.

Native IFC parsing remains optional and fail-closed when the ifcopenshell runtime is unavailable. The acceptance gate uses deterministic in-memory BIM entities and does not fabricate geometry.

Completion requires implementation, acceptance, regression, merge, and main verification.
