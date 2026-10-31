#!/usr/bin/env python3
"""Auditable Git blob comparison of PR30, PR32 and PR33 vs selected P8 line.

No semantic parity claim for changed/absent files. No merge operation.
Run in a full-depth checkout with all branch objects available.
"""
import json
import subprocess
import sys
from pathlib import Path

FORKS = {
 "30": ("6646d07d1130676fe60193756e94d00f9e4b73ef", {
  "app/graphical_takeoff.py":"DIFFERENT",
  "app/verified_selection_panel.py":"DIFFERENT",
  "core/drawings/project_selection_bridge.py":"DIFFERENT",
  "core/drawings/verified_selection.py":"SAME",
  "tests/test_phase6_p3_full_verified_boq.py":"DIFFERENT",
  "tests/test_phase6_p3_real_project_bridge.py":"DIFFERENT",
  "tests/test_phase6_p3_selection_panel.py":"SAME",
  "tests/test_phase6_p3_verified_selection.py":"SAME"}),
 "32": ("0a5af74123411ee0cb350e7490ba5a042da5bf25", {
  "app/contextual_takeoff_p6.py":"CANONICAL_ABSENT",
  "app/graphical_takeoff.py":"DIFFERENT",
  "app/manual_takeoff.py":"DIFFERENT",
  "core/ai/contextual_takeoff_p6.py":"CANONICAL_ABSENT",
  "tests/test_phase6_p4_w1_a2_core.py":"CANONICAL_ABSENT",
  "tests/test_phase6_p4_w1_a2_qt.py":"CANONICAL_ABSENT"}),
 "33": ("c859cebccf83a43e456e73377bb2dea764e00823", {
  "app/architecture_detail_editor.py":"SAME",
  "app/beam_detail_panel.py":"SAME",
  "app/contextual_takeoff_panel.py":"SAME",
  "app/graphical_takeoff.py":"DIFFERENT",
  "app/reviewed_aec_manual_editor.py":"SAME",
  "app/reviewed_structural_manual_editor.py":"SAME",
  "app/roof_detail_editor.py":"DIFFERENT",
  "core/ai/contextual_takeoff.py":"SAME",
  "core/ai/gguf_runtime_v1.py":"SAME"}),
}

def git(*args, missing_ok=False):
 p=subprocess.run(["git",*args],capture_output=True,text=True,check=False)
 if p.returncode:
  if missing_ok and p.returncode==128:return None
  raise RuntimeError("git "+ " ".join(args)+" failed: "+p.stderr.strip()[:160])
 return p.stdout.strip()

def audit():
 head=git("rev-parse","HEAD")
 results=[]
 for pr,(sha,paths) in FORKS.items():
  git("cat-file","-e",sha+"^{commit}")
  common=git("merge-base",sha,head)
  if common in (head,sha):raise ValueError("Unexpected PR ancestry: "+pr)
  for path,expected in paths.items():
   old=git("rev-parse",sha+":"+path,missing_ok=True)
   new=git("rev-parse",head+":"+path,missing_ok=True)
   if old is None:raise ValueError("Historical file missing: "+path)
   status="CANONICAL_ABSENT" if new is None else "SAME" if new==old else "DIFFERENT"
   if status!=expected:raise ValueError(f"PR {pr} {path}: {status} != {expected}")
   results.append({"pr":int(pr),"path":path,"status":status,"fork_blob":old,"canonical_blob":new,"semantically_equivalent":status=="SAME"})
 report={"phase":8,"priority":2,"canonical_sha":head,
  "fixed_fork_shas":{pr:v[0] for pr,v in FORKS.items()},
  "scope":"source-file-blob-only",
  "counts":{k:sum(r["status"]==k for r in results) for k in ("SAME","DIFFERENT","CANONICAL_ABSENT")},
  "PR32_ALTERNATE_BEHAVIOR":"NOT_VERIFIED",
  "PR30_33_CHANGED_BEHAVIOR":"TEST_PENDING",
  "release":"NO_GO","merge_permitted":False,"files":results}
 Path("phase8-p2-fork-audit.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
 print(json.dumps({k:report[k] for k in ("canonical_sha","counts","PR32_ALTERNATE_BEHAVIOR","release")},ensure_ascii=False))
 return 0

if __name__=="__main__":
 try:sys.exit(audit())
 except (OSError,ValueError,RuntimeError) as e:
  print("PHASE8_P2_FORK_AUDIT_FAIL",e,file=sys.stderr)
  sys.exit(1)
