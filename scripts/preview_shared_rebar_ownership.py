"""Read-only synthetic/real sourced ledger preview; no SQLite / no BOQ commit."""
import argparse
import json
import sys
from pathlib import Path

if __package__ in (None,""):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.takeoff.shared_rebar_ownership_chat import reconcile

def main():
    p=argparse.ArgumentParser(description="Read-only rebar ownership preflight")
    p.add_argument("input",type=Path,help="Validated physical claims JSON; no guessed lengths")
    p.add_argument("--project",type=Path,help="Optional read-only project JSON for partial legacy inspection")
    p.add_argument("--source-document",type=Path,help="Optional real evidence file; required to verify source SHA-256")
    a=p.parse_args()
    obj=json.loads(a.input.read_text(encoding="utf-8"))
    project=json.loads(a.project.read_text(encoding="utf-8")) if a.project else None
    evidence=a.source_document.read_bytes() if a.source_document else None
    print(json.dumps(reconcile(obj,project,source_document=evidence),ensure_ascii=False,indent=2))

if __name__=="__main__":main()
