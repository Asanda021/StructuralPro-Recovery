# Phase 4 priorities 1–3 — execution report

Date: 2026-10-24, Asia/Tehran. This is software acceptance with explicit synthetic engineering inputs, not a real building schedule, official pricebook or authenticated human approval.

## Scope and repository
Only WBS/structure (20%), CPM/calendar/Gantt (25%), verified weighted progress (20%). The other 35% of Phase 4 is outside this mission. The eight-phase master roadmap is unchanged. PR23 is Draft, dependent on unchanged PR22 c657f85c. No merge, force push, release, EXE, manual Actions or StructuralBot.

Tested online code 64d73d73499c34e5efdb629d9d0b0b2efa96cbd8; local test commit 020f5b3c2f4ff77c4f3622708068eb2a4706ada8; identical source tree 5e4247bd4062c47a081b73fba24455ba49e0b042. Local commits preserve task-by-task development; the source bundle includes both histories.

## Implemented behavior
1. Existing floors/members and project_schedule_tasks are retained. Commands create blocks, explicit floors/heights/types, zones, disciplines, hierarchical WBS and parent activities. Stable IDs survive moves; activities can span locations. BOQ allocation reconciles existing effective takeoffs and owns (source, operation, unit), with full aggregate-source identity. No quantity is inferred or altered. Quantity/source revisions become stale rather than silently rebasing work.
2. Workday CPM implements FS/SS/FF/SF, signed lag/lead, independent oracle-tested earliest/latest dates, total/free float, multiple critical routes and milestones. Calendar uses explicit weekday/holiday inputs; ISO storage and real Jalali popup/display. Baselines are immutable versions; current date projections update atomically. Gantt renders real bars, dependencies, critical status, baseline, actual progress, zoom and bidirectional row selection. Existing PDF/CAD/IFC identity handoffs support verified location highlighting without a new viewer.
3. Cumulative physical observations have evidence, unique references, independent locally attributed review/approval and superseding corrections. No payment is inferred. Weight versions declare source, method, full coverage, distribution and percentage display policy. Multi-floor shares must sum exactly to one; single-floor shares cannot distort totals. Missing work/weight means unknown. Aggregation retains unique activities and source documents. Dated report snapshots remain immutable; S-curve groups recorded points only. Current-plan percentages are separate from baseline percentages.

## Synthetic five-floor independent acceptance
Fifteen structural/architectural/MEP activities on five explicit floors, manual and PDF BOQ from the previous financial fixture, explicit extra planning quantities, calendar weekdays and a user-fixture holiday. Independent closed-form CPM plus independent day enumeration: baseline duration18 workdays; critical S1,S2,S3,S4,S5,A5,M5. Noncritical A/M float =3×(5−floor); structural float0. Current S5 extension changes current duration to20, preserving baseline and BOQ.

Independent Decimal actual percentages for three observed periods:12.500000,45.000000,75.000000. A formal A1 correction retains the originally issued second report. Final baseline planned100, actual75, variance−25 percentage points; latest-program planned92.5. Project identity, links, baseline, observations, weights, snapshots and SQLite integrity survive reopen.

Twenty PDF/XLSX/DOCX/CSV reports cover WBS, activities, schedule/critical path, weighted progress/variance and S-curve. Gantt and S-curve images are embedded in Office/PDF reports, Excel sheets are RTL, Word tables remain editable. Final figures use one Persian shaping pipeline. Native Office reopen/save/print remains unverified.

## Review and safeguards
Independent read-only review found3 P1 and5 P2 issues. All were reproduced with tests and corrected: orphan BOQ acceptance, multi-quantity takeoff ambiguity, pre-activation raw official records, invalid single-floor shares, status edits invalidating weights, cash fields invalidating quantity basis, calendar compatibility dates, and legacy activity selection. Additional QTest/visual corrections cover native calendar locale, desktop-fit panels, weight-version discovery and report double-Bidi. No old tests removed or weakened.

A broader targeted run was rejected by automatic approval review for possible dependency Microsoft telemetry and is not acceptance evidence. All subsequent acceptance runs use the verified inherited Linux seccomp offline launcher; optional runtime telemetry opt-outs are also set. One incomplete full run was stopped after visual QA found the report-shaping defect. Only a completed final full run will be used in counts; targeted and recovered cases overlap and are not added.

## Explicit contracts and limitations
- Duration: integer project workdays. Computation uses [ES,EF); displayed finish is the last occupied workday; milestones occupy one boundary. Lag uses the same explicit calendar. Roots are warnings, cycles/unknown references fail closed.
- Planned progress is at the beginning of the selected report date. Linear workday or milestone-finish distribution is explicitly chosen. Raw quantities/weights use Decimal strings; percentage precision and rounding are explicit per approved weight version. No implicit clipping of actual overrun.
- Aggregate BOQ rows are assigned whole; partial source allocation is blocked. A basis with approved physical work is not silently replaced: use documented corrections or a separate explicitly reviewed scope. Local names attribute responsibility; they do not authenticate a person or legal signature.
- Historical absolute evidence paths are retained. Restore validates original hashes, readback and new fixtures without rewriting approved provenance. Source bundle is not an installer and contains no paid service dependency.
- Windows, PowerShell, native Office and Acrylic are NOT VERIFIED here. Prior engineering/real-project/owner acceptance gaps remain separate. No priorities4–6 of Phase4 or later phase execution starts.

## Verification and recovery
Final targeted:86 PASS,0 FAIL/ERROR/SKIP,34.96s. Final complete full regression:7847 PASS,0 FAIL/ERROR,5 unchanged PowerShell SKIP,412.07s. All86 targeted cases are included in7852 unique full cases, not added. Three warnings: one upstream fitz deprecation and two existing JUnit record_property warnings. Compileall, pip check and diff check passed.

Host-local performance receipts:1000 activities, CPM .010135s, UI render .149480s, event gap .114039s <.5s. CAD100000 entities retained with500000m independent oracle and event gap .164517s <.5s. No threshold relaxed. LibreOffice curve DOCX rendered and all3 pages inspected; native Microsoft Office remains NOT VERIFIED.

Cloud recovery completed:86 PASS,0 FAIL/ERROR/SKIP,36.95s on the recovered checkout. These are repeat overlapping cases, not additional unique tests.

## Backup and verified recovery
[New Drive backup](https://drive.google.com/file/d/1PbzTN3WeJx7iVw5wsh8VXeq2mSY_kHWi/view):17,922,743 bytes; SHA256 `0fa98b06a835b7df03544678804225dce098805708a44a65420d95ed8c73bbaf`. All63 Manifest file hashes match after redownload and remain unchanged after recovery. Git fsck and exact code HEAD/tree pass, both remote and local development histories are referenced. SQLite integrity,15 activities,5 floors, baseline18/current20, all3 report percentages and source evidence hashes pass. Twelve reports regenerated without changing project data.

Important recovery boundary: the first independent read correctly failed closed when historical evidence paths were unavailable. Original synthetic files were then quarantined and historical paths temporarily mapped to the verified restored copies. No approved JSON path, quantity, source hash or record was rewritten; the mapping was removed and originals restored afterwards. A moved real project must explicitly restore or verify its evidence locations. Fresh recovered-code fixtures and drawing-highlight tests additionally passed independently.

[Cloud recovery receipt](https://drive.google.com/file/d/1XRt-KBO2FIrqG638Qg2sKJZOobOAUo5T/view). The immutable source ZIP necessarily predates its own cloud recovery receipt; this final evidence commit accompanies it. Prior backups were not deleted or replaced.

## Final scoped acceptance
|Priority|Weight of Phase4|Non-Windows status|
|---|---:|---|
|1 WBS and structure|20%|COMPLETE|
|2 CPM/calendar/Gantt|25%|COMPLETE|
|3 verified physical/weighted progress|20%|COMPLETE|
|4–6|35% combined|OUT OF THIS MISSION; not started here|

Exactly65% of Phase4 allocated weight has verified non-Windows evidence. This is not100% of Phase4, not overall product completion and not Windows/Office acceptance. No known critical defect remains in the supported documented scope. Task ledger records the decisions and reproduced/fixed failures. No deferred independent-review blocker remains.

## Eight-phase status and handoff
Phase1: prior independent engineering/real-building/owner acceptance gaps remain open. Phase2: existing accepted source baseline preserved and regression-tested; model-based AI and Windows acceptance are separate. Phase3: prior six-priority non-Windows evidence preserved by full regression, owner/native acceptance pending. Phase4: priorities1–3 scoped complete65%;4–6 remain outside scope. Phases5–8 retain their original roadmap criteria and are not declared complete by this work.

Next work is limited to separately authorized priorities4–6 of Phase4 and previous open engineering/Windows/Office/owner acceptances. Do not invent their detailed titles or weights from this brief. Keep all PRs Draft/unmerged until explicit owner authorization. This mission stops here.
