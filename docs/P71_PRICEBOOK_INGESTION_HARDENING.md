# P71 — Pricebook ingestion hardening

This phase makes the pricebook pipeline ready to receive official artifacts without fabricating rows.

- XLSX/XLS/CSV/JSON ingestion
- ZIP/RAR archive ingestion
- deterministic evidence coverage and fingerprint
- fail-closed on unsupported archives or empty datasets
- preserves source/year evidence

The official 1404 SAMA archive is recorded in the source registry, but raw bytes must still be retrieved and hashed before they can be treated as an imported official dataset.
