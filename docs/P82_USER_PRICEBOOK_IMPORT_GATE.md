# P82 — User pricebook import gate

User-supplied Excel/CSV/JSON imports are accepted only after normalization and
provenance validation. The gate enforces one explicit year and discipline,
source file/hash, row identity, and optional all-priced policy. Rejected rows
remain reviewable and are not silently priced.
