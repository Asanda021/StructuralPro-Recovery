"""P79 — deterministic audit of downloaded official pricebook artifacts."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import zipfile

@dataclass(frozen=True)
class ArtifactAudit:
    path:str
    sha256:str
    bytes:int
    archive:bool
    file_count:int

def audit(path):
    p=Path(path); data=p.read_bytes()
    if not data: raise ValueError("empty artifact")
    is_archive=zipfile.is_zipfile(p)
    count=len(zipfile.ZipFile(p).namelist()) if is_archive else 1
    return ArtifactAudit(str(p),sha256(data).hexdigest(),len(data),is_archive,count)

def audit_manifest(paths):
    audits=[audit(p) for p in paths]
    if not audits: raise ValueError("no artifacts")
    return {"artifacts":[a.__dict__ for a in audits],
            "total_bytes":sum(a.bytes for a in audits),
            "total_files":sum(a.file_count for a in audits)}
