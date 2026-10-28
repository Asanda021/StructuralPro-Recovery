## Final root followup

E4 native destination/search suite now31PASS, zero fail/error/skip, zero warnings. Full regression exposed current BOQ row-1 despite requested B2. A native SelectColumns table independently reproduces this exact failure (1RED). Commit80ecbaf explicitly sets current cell and ClearAndSelect|Rows in the existing Qt selection model. The table's stored row/quantity/unapproved amount and original project repr remain unchanged; only presentation selection changes. Probes for Ctrl and NoSelection passed and are not claimed as RED. Final local combined workflow449PASS; independent Linux/Windows CI is pinned in parent final-source.json/ci-measured.json. All destination blockers below remain.

---

# E4 canonical drawing-session destination — 2026-10-27

Status: PARTIAL. Code/test commit `2f56a2e`. No push, merge, release, EXE, or main changes.

The existing search engine now indexes the canonical `drawing_sessions` records by their explicit stored ID/source path. The real search Open button can route to the original `GraphicalTakeoffDialog`, restoring the exact stored session, items, current page, revision, and documented CAD units through the existing service loader. The main callback attaches that original view to the existing 2D dock. No second index, quantity engine, geometry mapping, or BOQ recalculation was added.

Navigation requires authorized project access, a positive explicit stored session revision, matching session/record source path and SHA-256, existing nonsymlink PDF/DXF source, current bytes, and the unchanged project digest after loading/rendering. Missing session identity and revoked ACL fail closed. Search retains the original full-snapshot ambiguity checks and stale-result revalidation. The canonical session remains unchanged; this is opening a draft for subsequent original-editor operations, not a new commit authorization.

## Evidence

- `red.log`: newly written real Qt test failed because canonical saved sessions produced zero search results before implementation.
- `targeted.log` / `targeted.xml`: 30 PASS, 0 FAIL/ERROR/SKIP, no pytest warnings. Includes the existing E4 search/UI tests plus three new tests.
- New PDF test clicks the actual search dialog Open button using QTest and reaches the actual original graphical dialog; asserts exact session ID/revision/items, visible table, source identity, unchanged digest/empty BOQ and SQLite reopen equality. A changed source and missing ID are rejected.
- New DXF test uses a synthetic explicit `$INSUNITS=6` drawing. It opens the canonical session in the original viewer, checks metres and SHA, clicks the original Find Handle button with the source entity's explicit handle, and asserts that exact original scene item is selected. This proves the existing handle callback on the verified destination; search targets the session, not a newly invented element mapping.
- New stale/permission test changes the real SQLite project between search and Open and revokes the real ACL; both are blocked without invoking navigation.
- `full.log` / `full.xml`: bare repository pytest attempted; 15 collection errors from historic release/workflow guards and 1 fitz FutureWarning. All error module names and tracebacks are preserved. Whole-repository green is not claimed. No historic guard was weakened.
- Offscreen Linux Qt only. Native Windows/physical UAT is not claimed; root owns subsequent CI.

Commands (Python executable `/workspace/StructuralPro-Recovery/.venv/bin/python`; `QT_QPA_PLATFORM=offscreen`):

```text
python -m pytest tests/test_phase6_p5_e4_sessions.py -q                # initial RED
python -m pytest tests/test_phase6_p5_e4_search.py tests/test_phase6_p5_e4_ui.py tests/test_phase6_p5_e4_sessions.py -q --junitxml=docs/acceptance/phase6_p5/verification-20261027-three-gates/e4/targeted.xml
python -m pytest -q --junitxml=docs/acceptance/phase6_p5/verification-20261027-three-gates/e4/full.xml
git diff --check
```

## Destination matrix

| Destination | Exact current behavior | Remaining limitation |
|---|---|---|
| Project/floor/member | Existing original Inspector identity selection, ambiguity guards preserved | IFC geometric selection separately requires reviewed bridge |
| PDF document | Existing explicit document ID, SHA and revision opens original viewer | No guessed page/region from title |
| PDF saved session | NEW exact canonical session/revision/items/current page restored | Does not infer geometry or approve quantities |
| DXF document/session | Existing document route; NEW canonical session restoration and existing native handle callback tested | Search selects the saved session; it does not claim a member-to-handle crosswalk |
| DWG session | BLOCKED explicitly before opening | No converter/provenance fixture; no fabricated DWG support |
| IFC member | Existing independent reviewed four-way bridge unchanged | No guessed GlobalId; complex IFC acceptance still open |
| IFC saved session | BLOCKED in this new route | Existing reviewed member route must remain the geometric authority |
| BOQ | Existing exact persisted row selection, no financial recalculation | Existing identity guards retained |
| Manual formula | Existing exact stored row in original manual editor | Family text is not a specialist draft identity |
| WBS/activity | Existing canonical project_wbs/project_schedule_tasks original controls selection | Legacy generic arrays may lack a canonical destination |
| Beam | BLOCKED for specialist search handoff | Original BeamDetailPanel load requires project/floor/beam and drawing/source context; member title/kind does not establish exact stored beam draft/source identity |
| Column/MEP | BLOCKED for specialist search handoff | Existing graphical editor closures require explicit stored draft/context; no verified search contract from generic member result |
| Roof/architecture | BLOCKED for specialist search handoff | Existing modal editors require kind/floor/system context and explicit load; generic member identity is insufficient. Editors were not changed |
| Generic takeoff/report | Read-only original SQLite record; specialized destination BLOCKED | No safe stored-record-to-editor/report artifact contract; no guessed path or regenerated report |

The broad E4 gate remains PARTIAL. These blockers are not converted into successful editor navigation or inferred identities. The new tests use synthetic source fixtures, not owner-approved engineering buildings. There are no monkeypatched dialog exec methods.
