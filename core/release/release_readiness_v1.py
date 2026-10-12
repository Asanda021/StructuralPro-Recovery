from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class ReleaseArtifact:
    name: str
    version: str
    sha256: str
    platform: str
    observed_at: str

@dataclass(frozen=True)
class InstallCheck:
    artifact_name: str
    platform: str
    status: str
    evidence: str

@dataclass(frozen=True)
class ReleaseReadiness:
    artifact_count: int
    install_check_count: int
    decision: str
    fingerprint: str

def validate_release(artifacts, checks):
    if not artifacts or not checks:
        raise ValueError("release readiness requires explicit artifact and installation evidence")
    names=set()
    for a in artifacts:
        if not all((a.name.strip(),a.version.strip(),a.sha256.strip(),a.platform.strip(),a.observed_at.strip())):
            raise ValueError("incomplete release artifact evidence")
        if len(a.sha256)!=64 or any(c not in "0123456789abcdefABCDEF" for c in a.sha256):
            raise ValueError("invalid artifact sha256")
        names.add((a.name,a.platform))
    for c in checks:
        if not all((c.artifact_name.strip(),c.platform.strip(),c.status.strip(),c.evidence.strip())):
            raise ValueError("incomplete installation evidence")
        if (c.artifact_name,c.platform) not in names:
            raise ValueError("installation check has no matching artifact")

def assess_release(artifacts, checks):
    validate_release(artifacts,checks)
    statuses={c.status for c in checks}
    decision="no_go" if "fail" in statuses else ("needs_evidence" if "needs_evidence" in statuses else ("go" if statuses=={"pass"} else "needs_evidence"))
    payload="|".join(sorted(f"{a.name}|{a.version}|{a.sha256}|{a.platform}|{a.observed_at}" for a in artifacts))
    payload+="||"+"|".join(sorted(f"{c.artifact_name}|{c.platform}|{c.status}|{c.evidence}" for c in checks))
    return ReleaseReadiness(len(artifacts),len(checks),decision,sha256(payload.encode()).hexdigest())
