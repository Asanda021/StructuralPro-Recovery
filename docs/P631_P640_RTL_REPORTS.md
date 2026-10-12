# P631–P640 — Professional Reports / RTL Export

The report boundary is deterministic and preserves explicit values from upstream engines.

## Guarantees
- Persian/RTL marker is explicit.
- Unicode normalization is deterministic.
- Empty reports and empty section titles fail closed.
- No engineering value is generated during rendering.
- Report fingerprint is reproducible.

PDF/Excel and other renderers should consume the same normalized report model rather than duplicate business logic.
