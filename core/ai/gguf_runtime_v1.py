"""Fail-closed GGUF production runtime boundary for StructuralPro.
Model weights are external artifacts. This module never downloads models and never treats a missing/unverified artifact as production-ready.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

@dataclass(frozen=True)
class GGUFModelSpec:
    name: str
    path: str
    sha256: str
    license: str
    commercial_use: bool
    architecture: str = "unknown"
    def __post_init__(self):
        if not self.name.strip() or not self.path.strip(): raise ValueError("model name and path are required")
        digest=self.sha256.strip().lower()
        if len(digest)!=64 or any(c not in "0123456789abcdef" for c in digest): raise ValueError("sha256 must be a 64-character hexadecimal digest")
        if not self.license.strip(): raise ValueError("model license is required")
        if not isinstance(self.commercial_use,bool): raise ValueError("commercial_use must be boolean")

@dataclass(frozen=True)
class GGUFVerification:
    ready: bool
    model: GGUFModelSpec
    actual_sha256: str|None
    reason: str

class GGUFProductionRuntime:
    def __init__(self, manifest_path: str|Path, model_root: str|Path|None=None):
        self.manifest_path=Path(manifest_path)
        self.model_root=Path(model_root) if model_root else self.manifest_path.parent

    def load_manifest(self)->GGUFModelSpec:
        data=json.loads(self.manifest_path.read_text(encoding="utf-8"))
        if data.get("format","").lower()!="gguf": raise ValueError("manifest format must be GGUF")
        if data.get("internet_required"): raise ValueError("production local runtime cannot require internet")
        models=data.get("model_files")
        if not isinstance(models,list) or len(models)!=1: raise ValueError("manifest must identify exactly one production model")
        item=models[0]
        if not isinstance(item,dict): raise ValueError("model_files entry must be an object")
        return GGUFModelSpec(
            name=str(item.get("name","")), path=str(item.get("path","")),
            sha256=str(item.get("sha256","")), license=str(item.get("license","")),
            commercial_use=item.get("commercial_use") is True,
            architecture=str(item.get("architecture","unknown")),
        )

    def verify_artifact(self)->GGUFVerification:
        model=self.load_manifest()
        path=self.model_root/model.path
        if not path.is_file(): return GGUFVerification(False,model,None,"model_artifact_missing")
        digest=sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024*1024),b""): digest.update(chunk)
        actual=digest.hexdigest()
        if actual!=model.sha256: return GGUFVerification(False,model,actual,"model_sha256_mismatch")
        if not model.commercial_use: return GGUFVerification(False,model,actual,"commercial_use_not_verified")
        return GGUFVerification(True,model,actual,"verified")

    def create_engine(self, **kwargs:Any):
        verification=self.verify_artifact()
        if not verification.ready: raise RuntimeError(verification.reason)
        try:
            from llama_cpp import Llama
        except Exception as exc:
            raise RuntimeError("llama_cpp_runtime_unavailable") from exc
        return Llama(model_path=str(self.model_root/verification.model.path),verbose=False,**kwargs)
