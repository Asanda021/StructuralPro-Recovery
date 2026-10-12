"""P76 — remotely retrievable 1404 building pricebook artifacts."""
from dataclasses import dataclass
from hashlib import sha256
from urllib.request import Request, urlopen

@dataclass(frozen=True)
class RemoteArtifact:
    discipline:str
    year:int
    url:str
    expected_extension:str

ARTIFACTS_1404=(
    RemoteArtifact("ابنیه",1404,"https://drive.google.com/uc?export=download&id=1EZtKArXhMi0VAMWsdS0GsTPUaBkwl8iO",".xlsx"),
    RemoteArtifact("تاسیسات مکانیکی",1404,"https://drive.google.com/uc?export=download&id=1xz37RKCV54XYiBzO-OqdrmtvDdfdiDxe",".xlsx"),
    RemoteArtifact("تاسیسات برقی",1404,"https://drive.google.com/uc?export=download&id=1FZWScOv8PwT2WbGo9bTrl59x2RU4toZ-",".xlsx"),
    RemoteArtifact("مرمت بناهای تاریخی",1404,"https://drive.google.com/uc?export=download&id=1EEifLJ5cJ86W0CGeMWTSQWNwLhJBvvK3",".xlsx"),
)

def manifest():
    return [{"discipline":a.discipline,"year":a.year,"url":a.url,"expected_extension":a.expected_extension} for a in ARTIFACTS_1404]

def fetch_artifact(artifact:RemoteArtifact, timeout=60):
    req=Request(artifact.url,headers={"User-Agent":"StructuralPro-pricebook-fetch/1.0"})
    with urlopen(req,timeout=timeout) as response:
        data=response.read()
    if not data: raise ValueError("empty artifact")
    return data, sha256(data).hexdigest()
