"""Phase-one acceptance is not silently upgraded by test coverage or missing documents."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.validate_phase1_37_family_triage import FILES, validate_documents

ROOT = Path(__file__).resolve().parents[1]


def _sources():
    return {name: json.loads((ROOT / filename).read_text(encoding="utf-8"))
            for name, filename in FILES.items()}


def _errors(docs):
    return validate_documents(docs["source"], docs["triage"], docs["matrix"],
                              docs["inventory"], docs["ledger"])


def test_entire_37_family_triage_is_consistent_but_keeps_engineering_open():
    docs = _sources()
    assert _errors(docs) == []
    assert len(docs["triage"]["families"]) == 37
    assert all(not row["full_family_engineering_accepted"]
               and row["independent_evidence_status"] == "missing"
               and row["record_status"] == "blocked_engineering_dependency"
               for row in docs["triage"]["families"])
    assert docs["ledger"]["acceptance"]["phase_one_closed"] is False


@pytest.mark.parametrize("tamper", [
    "fake_accepted",
    "fake_new_evidence",
    "missing_external_doc",
    "changed_reviewer",
    "duplicate_family",
    "missing_family",
    "invented_family",
    "ledger_closed",
])
def test_triage_rejects_missing_or_fabricated_engineering_evidence(tamper):
    docs = deepcopy(_sources())
    rows = docs["triage"]["families"]
    if tamper == "fake_accepted":
        rows[0]["full_family_engineering_accepted"] = True
    elif tamper == "fake_new_evidence":
        rows[0]["independent_evidence_status"] = "verified"
    elif tamper == "missing_external_doc":
        rows[0]["external_required_documents"] = []
    elif tamper == "changed_reviewer":
        rows[0]["external_provider_reviewer"] = "بررسی نشده"
    elif tamper == "duplicate_family":
        rows[1]["code"] = rows[0]["code"]
    elif tamper == "missing_family":
        rows.pop()
    elif tamper == "invented_family":
        rows[0]["code"] = "NOT-IN-SOURCE"
    elif tamper == "ledger_closed":
        docs["ledger"]["acceptance"]["phase_one_closed"] = True
    assert _errors(docs), "A fabricated or incomplete acceptance must never pass the triage gate"


def test_cli_does_not_confuse_integrity_with_specialist_approval():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_phase1_37_family_triage.py"),
         "--root", str(ROOT)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "37 externally blocked" in completed.stdout
    assert "Phase 1 remains OPEN" in completed.stdout
