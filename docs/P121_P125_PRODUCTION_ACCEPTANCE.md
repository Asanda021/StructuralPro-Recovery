# P121-P125 Production Acceptance

## Scope
- P121: multi-trade quantity/takeoff normalization and deterministic trade summaries.
- P122: collaboration revisions, optimistic concurrency and append-only audit events.
- P123: bounded deterministic batch aggregation.
- P124: path traversal protection, secret redaction and safe filename handling.
- P125: RTL-friendly action contract, deterministic ordering and input validation.

## Completion gate
Implementation + dedicated acceptance + regression + merge + main verification are required.
The acceptance layer fails closed on invalid quantities, stale revisions, unsafe paths,
duplicate action IDs and invalid required input. No hidden guessing or fabricated data is used.
