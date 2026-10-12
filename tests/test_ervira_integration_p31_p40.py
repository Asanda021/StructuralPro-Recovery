import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
IDS=[f"p{i}" for i in range(31,41)]
def load(i): return json.loads((ROOT/"contracts/ervira"/f"{i}.json").read_text())
def test_identity_governance():
    for i in IDS:
        d=load(i)
        assert d["product_id"]=="structuralpro"
        assert d["parent_platform"]=="ERVIRA"
        assert d["version"]=="0.1.0"
        assert d["runtime_status"]=="not_implemented"
        assert d["release_ready"] is False
def test_identity_authority_is_ervira():
    assert load("p31")["account"]["identity_authority"]=="ERVIRA"
    assert load("p32")["auth"]["provider"]=="ERVIRA"
    assert load("p33")["session"]["owner"]=="ERVIRA"
def test_final_gate_is_closed():
    assert load("p40")["release_ready"] is False
