import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=json.loads((ROOT/"contracts/product-contract.json").read_text())
PHASES=["p%02d"%i for i in range(12,21)]
def load(p): return json.loads((ROOT/"contracts/ervira"/(p+".json")).read_text())
def test_contracts_are_versioned():
    for p in PHASES:
        d=load(p)
        assert d["product_id"]==BASE["product_id"]
        assert d["parent_platform"]=="ERVIRA"
        assert d["version"]==BASE["product"]["current_version"]
        assert d["phase"]==p.upper()
def test_license_and_entitlement_are_server_gated():
    assert load("p13")["license"]["source"]=="ERVIRA"
    assert load("p14")["entitlement"]["source"]=="ERVIRA"
def test_download_is_disabled_without_release():
    d=load("p16")["download"]
    assert d["enabled"] is False
    assert load("p17")["release"]["publication_status"]=="not_published"
def test_e2e_is_not_release_ready():
    d=load("p20")
    assert d["release_ready"] is False
    assert all(v is False for v in d["gates"].values())
