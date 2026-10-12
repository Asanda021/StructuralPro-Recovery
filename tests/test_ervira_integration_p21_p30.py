import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=json.loads((ROOT/"contracts/product-contract.json").read_text())
PHASES=["p%02d"%i for i in range(21,31)]
def load(p): return json.loads((ROOT/"contracts/ervira"/(p+".json")).read_text())
def test_contract_identity_and_version():
    for p in PHASES:
        d=load(p)
        assert d["product_id"]==BASE["product_id"]
        assert d["parent_platform"]=="ERVIRA"
        assert d["version"]==BASE["product"]["current_version"]
        assert d["phase"]==p.upper()
def test_download_integrity_gate():
    d=load("p26")["integrity"]
    assert d["algorithm"]=="SHA-256"
    assert d["artifact_required"] and d["checksum_required"] and d["verification_required"]
    assert d["download_enabled"] is False
def test_governance_is_blocking():
    d=load("p30")["governance"]
    assert d["release_ready"] is False
    assert "version_mismatch" in d["blocking"]
    assert "fake_available_capability" in d["blocking"]
