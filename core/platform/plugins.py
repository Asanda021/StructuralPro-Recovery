"""Stable extension/plugin contract for StructuralPro."""
from __future__ import annotations
from dataclasses import dataclass, asdict
import hashlib, json, re

_API_RE = re.compile(r"^v\d+$")
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{1,63}$")

@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    name: str
    version: str
    api_version: str = "v1"
    capabilities: tuple[str, ...] = ()
    entrypoint: str = ""
    publisher: str = ""
    license: str = ""

    def validate(self) -> list[str]:
        e=[]
        if not _ID_RE.fullmatch(self.plugin_id): e.append("invalid plugin_id")
        if not self.name.strip(): e.append("name is required")
        if not self.version.strip(): e.append("version is required")
        if not _API_RE.fullmatch(self.api_version): e.append("unsupported api_version")
        if not self.publisher.strip(): e.append("publisher is required")
        if not self.license.strip(): e.append("license is required")
        if not self.capabilities: e.append("at least one capability is required")
        if any(not c.strip() for c in self.capabilities): e.append("capabilities must be non-empty")
        return e

def build_plugin_registry(manifests: list[PluginManifest]) -> dict:
    errors=[]; seen=set(); entries=[]
    for m in manifests:
        key=m.plugin_id.casefold()
        if key in seen: errors.append(f"duplicate plugin_id: {m.plugin_id}")
        seen.add(key); errors.extend(f"{m.plugin_id}: {x}" for x in m.validate()); entries.append(asdict(m))
    entries.sort(key=lambda x:x["plugin_id"])
    canonical=json.dumps(entries,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
    return {"api_version":"v1","plugins":entries,"valid":not errors,"errors":errors,
            "sha256":hashlib.sha256(canonical).hexdigest()}

def discover_plugins(manifests: list[PluginManifest], capability: str | None = None):
    registry=build_plugin_registry(manifests)
    if not registry["valid"]: return []
    return [p for p in registry["plugins"] if capability is None or capability in p["capabilities"]]
