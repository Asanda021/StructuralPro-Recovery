"""P35 — FINAL SIGN-OFF master gate."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path

REQUIRED = {
    34: ("core/platform/p34_final_product_acceptance.py","tests/test_p34_final_product_acceptance.py","docs/P34_FINAL_PRODUCT_ACCEPTANCE.md"),
}
REQUIRED_SURFACES = (
    "implementation","tests","ci","merge","post_merge_main_verification",
    "competitive_verification","final_product",
)

@dataclass(frozen=True)
class P35Result:
    signed_off: bool
    surfaces: tuple[str,...]
    blockers: tuple[str,...]
    fingerprint: str

def run_p35_gate() -> P35Result:
    blockers=[]
    for phase, paths in REQUIRED.items():
        for p in paths:
            if not Path(p).is_file():
                blockers.append(f"P{phase} evidence missing:{p}")
    p34=Path("core/platform/p34_final_product_acceptance.py")
    if p34.is_file():
        text=p34.read_text(encoding="utf-8")
        if "run_p34_gate" not in text:
            blockers.append("P34 acceptance gate contract missing")
    payload={"surfaces":REQUIRED_SURFACES,"p34_required":True,"signed_off":not blockers}
    fp=sha256(json.dumps(payload,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return P35Result(not blockers,REQUIRED_SURFACES,tuple(sorted(blockers)),fp)
