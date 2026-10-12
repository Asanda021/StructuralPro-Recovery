import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
BASE = json.loads((ROOT / "contracts/product-contract.json").read_text())
PHASES = ["p%02d" % i for i in range(2,12)]
def test_ervira_integration_phase_contracts():
    for phase in PHASES:
        data = json.loads((ROOT / "contracts/ervira" / (phase + ".json")).read_text())
        assert data["product_id"] == BASE["product_id"]
        assert data["parent_platform"] == BASE["parent_platform"]
        assert data["version"] == BASE["product"]["current_version"]
        assert data["phase"] == ("P" + str(int(phase[1:])))
def test_p2_capabilities_match_canonical():
    data = json.loads((ROOT / "contracts/ervira/p02.json").read_text())
    canonical = {x["id"]: x["status"] for x in BASE["capabilities"]}
    mirrored = {x["id"]: x["status"] for x in data["capabilities"]}
    assert mirrored == canonical
def test_release_download_is_hard_gated():
    data = json.loads((ROOT / "contracts/ervira/p04.json").read_text())
    assert data["release"]["download_enabled"] is False
    assert data["release"]["artifact"] is None
    assert data["release"]["sha256"] is None
def test_editions_are_not_marketed_before_release():
    data = json.loads((ROOT / "contracts/ervira/p03.json").read_text())
    assert {x["status"] for x in data["editions"]} == {"planned"}
