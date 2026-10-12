from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.request import Request, urlopen
@dataclass(frozen=True)
class MaterializedArtifact:
    year:int; discipline:str; url:str; path:str; sha256:str; size:int
def materialize(year:int,discipline:str,url:str,destination:Path,expected_extensions=(".xlsx",".xls",".zip",".rar")):
    if not url.startswith("https:"): raise ValueError("official artifact URL must use https")
    req=Request(url,headers={"User-Agent":"StructuralPro/1.0 pricebook-materializer"})
    with urlopen(req,timeout=120) as response:
        data=response.read(); content_type=(response.headers.get("Content-Type") or "").lower()
    if not data: raise ValueError("empty official artifact")
    sample=data[:512].lstrip().lower()
    if b"<html" in sample or b"<!doctype" in sample or "text/html" in content_type: raise ValueError("official artifact resolved to HTML")
    if destination.suffix.lower() not in expected_extensions: raise ValueError("unsupported destination extension")
    destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(data)
    return MaterializedArtifact(year,discipline,url,str(destination),sha256(data).hexdigest(),len(data))
