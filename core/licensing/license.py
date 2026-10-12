"""Offline product license token validation."""
from __future__ import annotations
import base64,hashlib,hmac,json,time
class LicenseManager:
    def __init__(self,secret): self.secret=str(secret).encode()
    def issue(self,customer,expires_at,device=""):
        p={"customer":str(customer),"expires_at":int(expires_at),"device":str(device)}
        raw=json.dumps(p,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()
        sig=hmac.new(self.secret,raw,hashlib.sha256).hexdigest()
        return base64.urlsafe_b64encode(raw).decode()+"."+sig
    def validate(self,token,device=""):
        try:
            enc,sig=token.split(".",1); raw=base64.urlsafe_b64decode(enc)
            if not hmac.compare_digest(sig,hmac.new(self.secret,raw,hashlib.sha256).hexdigest()): return {"valid":False,"reason":"signature"}
            p=json.loads(raw)
            if int(p["expires_at"])<int(time.time()): return {"valid":False,"reason":"expired"}
            if p.get("device") and p["device"]!=str(device): return {"valid":False,"reason":"device"}
            return {"valid":True,"payload":p}
        except Exception:return {"valid":False,"reason":"format"}
