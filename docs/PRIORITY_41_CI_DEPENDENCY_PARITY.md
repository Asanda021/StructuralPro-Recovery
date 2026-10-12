# Priority 41 — CI Dependency Parity

## Goal
Keep CI aligned with the canonical runtime dependency surface instead of maintaining a second, incomplete dependency list.

## Change
The main test, full-test and Windows-smoke workflows install `requirements.txt` and then install pytest explicitly.

This ensures the supported application dependencies (including PySide6/PyMuPDF) are present during CI while optional drawing backends remain optional.

## Acceptance
- All three workflows install the canonical runtime requirements.
- pytest remains explicit as a test-only dependency.
- Full suite and Windows smoke remain green.
