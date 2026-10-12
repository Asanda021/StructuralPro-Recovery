from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Mapping
import hashlib
import json

REQUIRED = ("customer_artifact","entitlement_authorization","installation_evidence","pricebook_provenance","third_party_licenses")
OPTIONAL = ("code_signing","bundled_gguf","dwg_runtime_terms")

@dataclass(frozen=True)
class Evidence:
    key: str
    required: bool
    present: bool
    path: str
    sha256: str
    note: str

@dataclass(frozen=True)
class ProductionReadiness:
    evidence: tuple[Evidence, ...]
    @property
    def ready(self) -> bool:
        return all(item.present for item in self.evidence if item.required)
    @property
    def status(self) -> str:
        return "ready" if self.ready else "blocked"
    def manifest(self) -> dict:
        return {"status": self.status, "release_ready": self.ready, "fail_closed": True, "evidence": [asdict(x) for x in self.evidence]}

def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def evaluate_evidence(root: str | Path, evidence: Mapping[str, str | None]) -> ProductionReadiness:
    root_path = Path(root)
    items = []
    for key in REQUIRED + OPTIONAL:
        relative = str(evidence.get(key) or "")
        path = root_path / relative if relative else None
        present = bool(path and path.is_file() and path.stat().st_size > 0)
        items.append(Evidence(key, key in REQUIRED, present, relative, _sha256(path) if present else "", "verified file evidence" if present else "missing real-world evidence"))
    return ProductionReadiness(tuple(items))

def write_manifest(result: ProductionReadiness, output: str | Path) -> None:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result.manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
