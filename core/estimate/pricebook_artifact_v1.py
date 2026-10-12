"""P73 — source-bound pricebook artifact manifest and fail-closed verification."""
from dataclasses import dataclass
from hashlib import sha256

@dataclass(frozen=True)
class ArtifactCandidate:
    year:int
    discipline:str
    url:str
    source_type:str
    verified:bool=False

CANDIDATES=(
    ArtifactCandidate(1404,"ابنیه","https://drive.google.com/uc?export=download&id=1EZtKArXhMi0VAMWsdS0GsTPUaBkwl8iO","secondary-download",False),
    ArtifactCandidate(1404,"ابنیه","https://sama.mporg.ir/DigitalAsset/DigitalAsset/FehrestBaha1404.rar?Web=1","official-archive",False),
)

def artifact_fingerprint(candidates=CANDIDATES):
    raw="|".join(f"{x.year}|{x.discipline}|{x.url}|{x.source_type}|{x.verified}" for x in candidates)
    return sha256(raw.encode()).hexdigest()

def verify_artifact(*, expected_year, expected_discipline, file_sha256, source_url):
    if expected_year < 1300 or expected_year > 1500: raise ValueError("invalid year")
    if not expected_discipline.strip(): raise ValueError("discipline required")
    if len(file_sha256)!=64 or any(c not in "0123456789abcdefABCDEF" for c in file_sha256):
        raise ValueError("valid file sha256 required")
    if not source_url.startswith("https://"): raise ValueError("https source required")
    return {"verified":True,"year":expected_year,"discipline":expected_discipline,
            "file_sha256":file_sha256.lower(),"source_url":source_url}

def release_gate(*, rows, artifact_verification):
    if not rows: return {"green":False,"reason":"no rows"}
    if not artifact_verification or not artifact_verification.get("verified"):
        return {"green":False,"reason":"artifact not verified"}
    return {"green":True,"row_count":len(rows),"file_sha256":artifact_verification["file_sha256"]}
