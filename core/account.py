"""Local account registry and stable device identity; no mandatory cloud service."""
from __future__ import annotations
import hashlib,secrets,json
from dataclasses import dataclass,asdict
from pathlib import Path
@dataclass(frozen=True)
class Account:
    account_id:str; display_name:str; created_at:str
@dataclass(frozen=True)
class DeviceIdentity:
    device_id:str; platform:str
def make_account(display_name,account_id=None,created_at=""):
    return Account(account_id or "acct_"+secrets.token_hex(8),display_name,created_at)
def device_identity(platform="desktop",seed=None):
    raw=(seed or secrets.token_hex(16)).encode()
    return DeviceIdentity("dev_"+hashlib.sha256(raw).hexdigest()[:16],platform)
class LocalAccountStore:
    """Tiny local registry for offline account/device state."""
    def __init__(self,path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def save(self,account,device):
        data={"account":asdict(account),"device":asdict(device)}
        self.path.write_text(json.dumps(data,ensure_ascii=False,sort_keys=True),encoding="utf-8")
    def load(self):
        if not self.path.exists(): return None
        d=json.loads(self.path.read_text(encoding="utf-8"))
        return Account(**d["account"]),DeviceIdentity(**d["device"])
