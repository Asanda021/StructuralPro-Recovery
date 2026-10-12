"""P62 — Windows-first production product contract."""
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class WindowsProductContract:
    version:str
    installer_artifact:str
    executable:str
    offline_workspace:bool
    project_backup:bool
    file_associations:tuple[str,...]
    update_channel:str

def validate_product(contract:WindowsProductContract)->None:
    if not contract.version or not contract.installer_artifact or not contract.executable:
        raise ValueError("Windows product identity is incomplete")
    if not contract.offline_workspace or not contract.project_backup:
        raise ValueError("Windows product must support offline workspace and backup")
    if contract.update_channel not in {"stable","beta"}:
        raise ValueError("invalid update channel")
    if not contract.file_associations:
        raise ValueError("at least one project file association is required")

def installer_manifest(contract:WindowsProductContract)->dict[str,object]:
    validate_product(contract)
    return {
        "platform":"windows",
        "version":contract.version,
        "installer":contract.installer_artifact,
        "executable":contract.executable,
        "offline_workspace":True,
        "project_backup":True,
        "file_associations":list(contract.file_associations),
        "update_channel":contract.update_channel,
    }
