import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
C=ROOT/"contracts/ervira"
def load(n): return json.loads((C/f"p{n:02d}.json").read_text(encoding="utf-8"))
def test_final_block_complete():
    assert [load(n)["name"] for n in range(76,81)]==["Final Product Parity","Commercial Integration Sign-off","Windows Release Sign-off","Security and SEO Sign-off","Final Integration / Sign-off"]
def test_final_signoff_is_fail_closed():
    c=load(80)
    assert c["status"]=="implemented"
    assert c["runtime_status"]=="implemented"
    assert c["release_ready"] is False
    assert c["signoff_state"]=="engineering-complete"
def test_private_surfaces_are_non_indexable():
    for p in ["app/main.py","website/index.html"]:
        text=(ROOT/p).read_text(encoding="utf-8").lower()
        assert text
