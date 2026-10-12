import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"contracts/ervira"
def load(n): return json.loads((C/f"p{n:02d}.json").read_text(encoding="utf-8"))
def test_contracts_complete():
    assert [load(n)["name"] for n in range(71,76)]==["Documentation Registry","User Guide Synchronization","API / Integration Documentation","Release Documentation Synchronization","Documentation E2E Verification Gate"]
def test_guides_are_nonempty():
    for p in [ROOT/"docs/USER_GUIDE_FA.md",ROOT/"docs/USER_GUIDE_EN.md",ROOT/"docs/API_INTEGRATION.md"]:
        assert p.exists() and p.stat().st_size>100
def test_no_production_secrets():
    for p in [ROOT/"docs/USER_GUIDE_FA.md",ROOT/"docs/USER_GUIDE_EN.md",ROOT/"docs/API_INTEGRATION.md"]:
        s=p.read_text(encoding="utf-8").lower()
        assert "sk_live_" not in s and "password=" not in s
