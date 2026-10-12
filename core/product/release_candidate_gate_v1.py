"""P93/P94/P95 — final product release gate."""
from __future__ import annotations
from hashlib import sha256
import json
from core.windows.product_v3 import release_manifest
from core.cloud.collaboration_v4 import Event, validate_event

def cloud_event_gate(event):
    validate_event(event)
    return {"ready":True,"project_id":event.project_id,"revision":event.revision}

def release_candidate(pricebook, benchmark, windows_release, workspace, collaboration_event):
    if not pricebook.get("complete"):
        raise ValueError("pricebook coverage is incomplete")
    if not benchmark.get("green2"):
        raise ValueError("benchmark is not green2")
    windows=release_manifest(windows_release,workspace)
    cloud=cloud_event_gate(collaboration_event)
    payload={"pricebook":pricebook,"benchmark":benchmark,"windows":windows,"cloud":cloud}
    payload["fingerprint"]=sha256(json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return payload
