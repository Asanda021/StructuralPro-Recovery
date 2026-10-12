from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class CADEntity:
    kind: str
    layer: str
    handle: str | None
    data: dict[str, Any]

class CADAdapter:
    def read_dxf(self, path: str | Path) -> list[CADEntity]:
        p=Path(path)
        if not p.exists(): raise FileNotFoundError(p)
        try: import ezdxf
        except ImportError as exc: raise RuntimeError("Install ezdxf to read DXF offline") from exc
        doc=ezdxf.readfile(str(p)); entities=[]
        for e in doc.modelspace():
            data={}
            for attr in ("start","end","center","radius","text","insert"):
                if hasattr(e,attr):
                    value=getattr(e,attr)
                    try: data[attr]=tuple(value)
                    except TypeError: data[attr]=value
            entities.append(CADEntity(e.dxftype().lower(),e.dxf.layer,e.dxf.handle,data))
        return entities
    @staticmethod
    def summarize(entities: list[CADEntity]) -> dict[str,int]:
        out={}
        for e in entities: out[e.kind]=out.get(e.kind,0)+1
        return out
