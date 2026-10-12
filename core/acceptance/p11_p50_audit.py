"""Evidence inventory for the ten-priority phases 2-5 (P11-P50).

This module records historical implementation evidence only; it never upgrades
historical evidence to a current Green status without current CI verification.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class PriorityEvidence:
    priority: int
    title: str
    evidence_commit: str

EVIDENCE = {
    11: PriorityEvidence(11, "Commercial license lifecycle", "e870304108835dfc68f5968ce52cd5bd7174995d"),
    12: PriorityEvidence(12, "Real user workflow", "dc707a23a339fb58b988879f923c2f8b66d5bd93"),
    13: PriorityEvidence(13, "Drawing & Takeoff UX", "136741def12faa70999453bd0ad3b90ceb3efca2"),
    14: PriorityEvidence(14, "Real Data Validation", "11aa01e4e7277a23de60048ed96bccded269d4e0"),
    15: PriorityEvidence(15, "Engineering Libraries", "fd0ad37e8895eefc6db2b27daa721033cb4d7f55"),
    16: PriorityEvidence(16, "BOQ / Estimate Professionalization", "0e81aaa22755fdeee44de231eb786b23b1480e6e"),
    17: PriorityEvidence(17, "Reports / Excel / PDF Professionalization", "88005f59cf248601cdd750ab3fa78f21baea021b"),
    18: PriorityEvidence(18, "Project Management Depth", "1495e75a6d395a948938206fa57aaabb89df5be5"),
    19: PriorityEvidence(19, "Finance & Payment Depth", "9dda26e356009a81851fb78a6d81ce1c8f202cc0"),
    20: PriorityEvidence(20, "BIM CAD Deep Integration", "171f840cb0719c16ab42dc230badbaa04fe06704"),
    21: PriorityEvidence(21, "AI Engineering Assistant", "e05416129beacfc91d6fde7e1efeee10e2dec860"),
    22: PriorityEvidence(22, "Performance & Large Projects", "341d1692440ca29054fe5b6581ab009eb4a2d03e"),
    23: PriorityEvidence(23, "Reliability & Recovery", "ddca260d24971e205f935faf6dcee95d2b409a17"),
    24: PriorityEvidence(24, "UX Polish", "f15b976540dc14ffaf5202125c2560e32055f1d0"),
    25: PriorityEvidence(25, "Installer / Update / Activation UX", "b4df766a874d363264317bf278678f6329ef24be"),
    26: PriorityEvidence(26, "Documentation / Help", "21f15c5eb067691c2d40e5624a46a7b01c7d9ddf"),
    27: PriorityEvidence(27, "Golden Projects / Benchmark", "5225231e7523398131ec363413a2490895ebe007"),
    28: PriorityEvidence(28, "Beta Release Readiness", "25dbe4d9dab69f2fb3b81470b634203829022606"),
    29: PriorityEvidence(29, "Real User Validation", "c34c4cdf3feea9506d3e891806b0d94569c930b9"),
    30: PriorityEvidence(30, "Production Hardening", "8a0f0bfc313aa362dd9b61a54328b9477b5c10e7"),
    31: PriorityEvidence(31, "Deep System Testing", "6c00daf6ca9bec14d351e0905f1c7a7711a72ecb"),
    32: PriorityEvidence(32, "Integration and Regression Testing", "0d74413de33fb84f1cd3dd95281f0c583c4b03e1"),
    33: PriorityEvidence(33, "Edge Cases and Failure Testing", "3d93391d5322bdc1595dc5014dba986dbf012e01"),
    34: PriorityEvidence(34, "Windows Validation and Smoke CI", "4dae82b477443b165225531b69308d620e8a8b7d"),
    35: PriorityEvidence(35, "Real-world Golden Scenarios", "db82f9f097f21358523a63d398454765f9da704f"),
    36: PriorityEvidence(36, "Full QA Audit", "df155e5dfcd9a49ef4f19c3c3a6089396062711c"),
    37: PriorityEvidence(37, "Bug Fix and Stabilization Cycle", "6801558e3b067ddf7effa193ffc33e072ec330e5"),
    38: PriorityEvidence(38, "Final Pre-release Freeze", "7a0361849c7003a16da817c66eeae82a34abd5b3"),
    39: PriorityEvidence(39, "Post-merge Windows Smoke Verification", "1cbdc07ada7cbde2a3b0d5f6e701a4d95bc3ea0a"),
    40: PriorityEvidence(40, "Cross-platform Version and Capability Contract", "db69e928aff28b8a21ec4d4b7e032b3c2383ae14"),
    41: PriorityEvidence(41, "CI Dependency Parity", "04c1eb57c8efb9fd029ad1249e768b64f2866a00"),
    42: PriorityEvidence(42, "Windows Runtime Smoke", "10fd1b23ec6e283b571d934b858f3af90f206f76"),
    43: PriorityEvidence(43, "Release Artifact Integrity", "d15f939a8b343c9ad69dc172558bdc82198154b0"),
    44: PriorityEvidence(44, "Deep Application Runtime Audit", "d308a62fd18c48dc7e157d95775e62bd503887d0"),
    45: PriorityEvidence(45, "Data Integrity and Persistence Audit", "f3bc566aa6d358521ded5d6a556c8d741ac5b329"),
    46: PriorityEvidence(46, "Calculation and Quantity Engine Audit", "dda429c34722b427ac986ae17f17365cdea53002"),
    47: PriorityEvidence(47, "UI/UX Functional Audit", "c1568435b73c5beb3d6c93d6a27bbec8e997e5a2"),
    48: PriorityEvidence(48, "Reporting and Export Audit", "7188c42002d9e048375f5618191977bc4c3931be"),
    49: PriorityEvidence(49, "Windows Installer E2E Acceptance", "1c55a7a46a7667dace8a97bf3df9d7a8a8dedfbc"),
    50: PriorityEvidence(50, "Production Status Reconciliation", "8c2ab4852a6d0e92efb81aefd4b55213e3eeefe9"),
}

PHASES = {
    2: tuple(range(11, 21)),
    3: tuple(range(21, 31)),
    4: tuple(range(31, 41)),
    5: tuple(range(41, 51)),
}

def phase_priorities(phase: int) -> tuple[int, ...]:
    if phase not in PHASES: raise ValueError("phase must be 2, 3, 4 or 5")
    return PHASES[phase]

def audit_summary() -> dict:
    return {
        "phases": 4,
        "priorities": 40,
        "evidence_records": len(EVIDENCE),
        "all_historical_evidence_present": len(EVIDENCE) == 40 and all(len(x.evidence_commit) == 40 for x in EVIDENCE.values()),
        "current_green": False,
        "reason": "Current CI, regression, QA, Windows and post-merge verification are separate gates.",
    }
