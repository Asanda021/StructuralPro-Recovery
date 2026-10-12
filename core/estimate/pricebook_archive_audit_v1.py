"""P98 — auditable multi-file archive ingestion; no silent skips."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from hashlib import sha256
import json, tempfile, os

SUPPORTED={".xlsx",".xls",".csv",".json"}

@dataclass(frozen=True)
class ArchiveEntry:
    name:str
    size:int
    sha256:str
    status:str
    rows:int
    error:str=""

def audit_archive(path,year,currency="IRR"):
    from core.estimate.pricebook_ingestion_v1 import load_supported
    p=Path(path); entries=[]; parsed=[]
    opener=None
    if p.suffix.lower()==".zip":
        import zipfile; opener=zipfile.ZipFile(p)
    else:
        import rarfile; opener=rarfile.RarFile(p)
    with opener as archive:
        for name in archive.namelist():
            ext=Path(name).suffix.lower()
            if ext not in SUPPORTED:
                continue
            raw=archive.read(name); digest=sha256(raw).hexdigest()
            fd,tmp_name=tempfile.mkstemp(prefix="pb_",suffix=ext)
            os.close(fd)
            tmp=Path(tmp_name)
            try:
                tmp.write_bytes(raw)
                rows=load_supported(tmp,year,currency)
                parsed.extend(rows)
                entries.append(ArchiveEntry(name,len(raw),digest,"parsed",len(rows)))
            except Exception as exc:
                entries.append(ArchiveEntry(name,len(raw),digest,"error",0,type(exc).__name__+": "+str(exc)))
            finally:
                tmp.unlink(missing_ok=True)
    if not entries: raise ValueError("archive contains no supported pricebook files")
    errors=[e for e in entries if e.status=="error"]
    if errors: raise ValueError("archive audit failed: "+json.dumps([e.__dict__ for e in errors],ensure_ascii=False))
    if not parsed: raise ValueError("archive contains no parseable pricebook rows")
    return tuple(parsed), tuple(entries)
