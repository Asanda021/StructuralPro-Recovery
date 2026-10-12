from __future__ import annotations
import hashlib
from pathlib import Path
from core.windows.product_v3 import WindowsRelease,WindowsWorkspace,release_manifest
def verify_windows_artifacts(release:WindowsRelease,workspace:WindowsWorkspace)->dict:
    manifest=release_manifest(release,workspace)
    for name in (release.installer,release.executable):
        p=Path(name)
        if not p.is_file() or p.stat().st_size<=0: raise FileNotFoundError(str(p))
    actual=hashlib.sha256(Path(release.installer).read_bytes()).hexdigest()
    if actual.lower()!=release.sha256.lower(): raise ValueError("installer SHA-256 mismatch")
    return {"valid":True,"manifest":manifest}
