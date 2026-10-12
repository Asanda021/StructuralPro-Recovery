# StructuralPro phases 1–5 — implementation and verification record

## Product scope
Windows-first Persian/RTL AEC quantity takeoff across architecture, structure, MEP, and renovation. Measurements must be traceable to the source drawing; no guessed scale, units, geometry, or quantities.

## Phase 1 — Calculation audit
- Hardened numeric validation against non-finite values and invalid deductions.
- Merged to `main` in PR #433.
- Post-merge CI verification must inspect all pages of checks; the initial page did not expose every check.

## Phase 2 — Professional manual takeoff
- Project/floor-bound manual takeoff reuses the deterministic takeoff engine.
- Incomplete entries remain drafts; saved rows have source IDs and retry protection.
- UI controls added for clipboard paste, pending-row edit/re-entry, copy, copy-to-floor, reversible deletion, undo/redo, and a bounded project audit timeline.
- Saved rows are protected against destructive editing from this dialog; this is intentional until a persisted-record revision flow can update all downstream BOQ/estimate references safely.
- P100 archive sync remains a separate publication gate: extraction/validation is not equivalent to publishing data to main.

## Phase 3 — Drawing viewer
- PDF uses PyMuPDF rendering; DXF/DWG are opened through the existing CAD import boundary.
- Page navigation and source identity are retained.
- Missing rendering/import dependencies and unsupported/invalid drawings fail with visible errors.

## Phase 4 — Zoom, selection, measurement
- Zoom in/out, fit-to-view, zoom-window, region selection/highlight, and cancel/escape/right-click handling.
- Selected regions can be converted to area takeoff only after explicit scale calibration and user confirmation.
- Calibration and measurement are traceable to page/source.

## Phase 5 — Persian CAD/DWG/DXF text
- CAD TEXT/MTEXT normalization decodes common Unicode escapes and formatting controls.
- RTL text direction is selected for Persian/Arabic text.
- DXF import uses the real `ezdxf` parser. Native DWG is not falsely represented as a built-in decoder: it requires a configured authorized provider/conversion path and fails closed if unavailable.

## Verification gate
A phase is not release-complete until dedicated tests and the relevant full regression pass, required GitHub Actions checks are green, the PR is merged, and post-merge main checks are verified. Open PRs or queued checks are implementation-in-progress, not completion.
